"""
guitar_bot_env.py - Gymnasium Environment for GuitarBot RL

This module defines a Gymnasium environment for training reinforcement learning
agents to control the GuitarBot. It supports:

- Configurable action spaces (discrete, continuous, hybrid)
- Audio-based reward computation
- Simulated or real robot execution
- Single or multi-string control

Episode Structure:
1. Agent selects action (fret, force, pluck)
2. Environment converts action to trajectory
3. Robot executes trajectory (~500-1000ms)
4. Audio is captured and analyzed
5. Reward computed from audio quality
6. New observation returned

Usage:
    env = GuitarBotEnv(num_strings=1, mode='simulation')
    obs, info = env.reset()
    for _ in range(100):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
"""

import numpy as np
import time
import gymnasium as gym
from gymnasium import spaces
from typing import Optional, Tuple, Dict, Any
import sys
from pathlib import Path
import tempfile
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rl.action_space import (
    create_discrete_action_space,
    create_continuous_action_space, 
    create_hybrid_action_space,
    create_observation_space,
    force_to_torque,
    fret_to_slider_position,
    slider_position_to_fret,
    clip_action,
    validate_motor_state,
    SLIDER_MIN, SLIDER_MAX,
    TORQUE_MIN, TORQUE_MAX,
    MAX_FRET,
    NUM_AUDIO_CLASSES,
    AUDIO_CLASS_NAMES,
    AUDIO_CLASS_HARMONIC,
    AUDIO_CLASS_DEAD_NOTE,
    AUDIO_CLASS_GENERAL_NOTE,
)
from rl.trajectory_generator import TrajectoryGenerator


class GuitarBotEnv(gym.Env):
    """
    Gymnasium environment for GuitarBot reinforcement learning.
    
    This environment wraps the GuitarBot hardware (or simulator) and provides
    a standard Gym interface for RL training.
    
    Attributes:
        num_strings: Number of strings to control (1, 3, or 6)
        action_space_type: 'discrete', 'continuous', or 'hybrid'
        mode: 'simulation', 'hardware', or 'hybrid_sim'
        step_timeout: Maximum time for trajectory execution (seconds)
        
    Action Space:
        Depends on action_space_type. See action_space.py for details.
        
    Observation Space:
        Motor positions, semantic state, and audio features.
    """
    
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}
    
    def __init__(
        self,
        num_strings: int = 1,
        action_space_type: str = 'hybrid',
        mode: str = 'simulation',
        step_timeout: float = 2.0,
        include_audio: bool = True,
        target_note: Optional[int] = None,
        render_mode: Optional[str] = None,
    ):
        """
        Initialize the GuitarBot environment.
        
        Args:
            num_strings: Number of strings to control (1, 3, or 6)
            action_space_type: 'discrete', 'continuous', or 'hybrid'
            mode: 'simulation' (no hardware), 'hardware' (real robot),
                  or 'hybrid_sim' (simulated audio with real physics model)
            step_timeout: Maximum time for a single step (seconds)
            include_audio: Whether to include audio in observations
            target_note: MIDI note number for target pitch (for pitch-matching tasks)
            render_mode: 'human' or 'rgb_array' for visualization
        """
        super().__init__()
        
        self.num_strings = num_strings
        self.action_space_type = action_space_type
        self.mode = mode
        self.step_timeout = step_timeout
        self.include_audio = include_audio
        self.target_note = target_note
        self.render_mode = render_mode
        
        # Create action space
        if action_space_type == 'discrete':
            self.action_space = create_discrete_action_space(num_strings)
        elif action_space_type == 'continuous':
            self.action_space = create_continuous_action_space(num_strings)
        else:  # hybrid
            self.action_space = create_hybrid_action_space(num_strings)
        
        # Create observation space
        self.observation_space = create_observation_space(
            num_strings, include_audio=include_audio
        )
        
        # Initialize state
        self._init_state()
        
        # Trajectory generator for action->trajectory conversion
        self.trajectory_generator = TrajectoryGenerator(num_strings=num_strings)
        
        # Hardware controllers (lazily initialized)
        self._robot_controller = None
        self._audio_analyzer = None
        
        # Audio classifier (lazily initialized)
        self._audio_classifier = None
        self._classifier_device = None
        self._classifier_model_path = None
        
        # Episode tracking
        self.step_count = 0
        self.max_steps = 100
        self.episode_reward = 0.0
        
        # History for temporal rewards
        self.action_history = []
        self.state_history = []
        self.audio_history = []
        
    def _init_state(self):
        """Initialize motor and audio state to default values."""
        self.slider_positions = np.zeros(self.num_strings, dtype=np.float32)
        self.presser_torques = np.full(
            self.num_strings, TORQUE_MIN, dtype=np.float32
        )
        self.picker_positions = np.zeros(
            min(self.num_strings, 3), dtype=np.float32
        )
        
        # Semantic state
        self.fret_positions = np.zeros(self.num_strings, dtype=np.int32)
        self.pressed_state = np.zeros(self.num_strings, dtype=np.int8)
        self.picker_state = np.zeros(min(self.num_strings, 3), dtype=np.int8)
        
        # Audio features
        self.audio_features = {
            'peak_rms_db': np.array([-80.0], dtype=np.float32),
            'spectral_flatness': np.array([0.5], dtype=np.float32),
            'fundamental_freq': np.array([0.0], dtype=np.float32),
            'onset_time': np.array([0.0], dtype=np.float32),
            # Classifier outputs
            'audio_class': 2,  # Default to general_note
            'audio_class_probs': np.array([0.0, 0.0, 1.0], dtype=np.float32),
            'audio_class_confidence': np.array([1.0], dtype=np.float32),
        }
        
    def _get_obs(self) -> Dict[str, np.ndarray]:
        """Build observation dict from current state."""
        obs = {
            'slider_positions': self.slider_positions.copy(),
            'presser_torques': self.presser_torques.copy(),
            'picker_positions': self.picker_positions.copy(),
            'fret_positions': self.fret_positions.copy(),
            'pressed_state': self.pressed_state.copy(),
            'picker_state': self.picker_state.copy(),
        }
        
        if self.include_audio:
            obs.update(self.audio_features)
        
        return obs
    
    def _get_info(self) -> Dict[str, Any]:
        """Build info dict with diagnostic data."""
        return {
            'step_count': self.step_count,
            'episode_reward': self.episode_reward,
            'mode': self.mode,
            'target_note': self.target_note,
            'action_history_len': len(self.action_history),
        }
    
    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[dict] = None,
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
        """
        Reset the environment to initial state.
        
        Args:
            seed: Random seed for reproducibility
            options: Additional reset options (e.g., initial_fret, target_note)
            
        Returns:
            Tuple of (observation, info)
        """
        super().reset(seed=seed)
        
        # Reset state
        self._init_state()
        
        # Reset episode tracking
        self.step_count = 0
        self.episode_reward = 0.0
        self.action_history = []
        self.state_history = []
        self.audio_history = []
        
        # Handle options
        if options:
            if 'target_note' in options:
                self.target_note = options['target_note']
            if 'initial_fret' in options:
                for i in range(self.num_strings):
                    self.fret_positions[i] = options['initial_fret']
                    self.slider_positions[i] = fret_to_slider_position(
                        i, options['initial_fret']
                    )
        
        # Reset hardware if in hardware mode
        if self.mode == 'hardware' and self._robot_controller is not None:
            self._reset_hardware()
        
        observation = self._get_obs()
        info = self._get_info()
        
        return observation, info
    
    def step(
        self, action: Dict[str, np.ndarray]
    ) -> Tuple[Dict[str, np.ndarray], float, bool, bool, Dict[str, Any]]:
        """
        Execute one environment step.
        
        Args:
            action: Action dict matching the action space
            
        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        self.step_count += 1
        
        # Validate and clip action
        action = clip_action(action, self.action_space_type)
        self.action_history.append(action)
        
        # Convert action to motor commands
        motor_commands = self._action_to_motor_commands(action)
        
        # Execute action (simulation or hardware)
        pluck_triggered = any(action.get('pluck', [0]))
        
        if self.mode == 'simulation':
            self._simulate_step(motor_commands, pluck_triggered)
        elif self.mode == 'hardware':
            self._hardware_step(motor_commands, pluck_triggered)
        else:  # hybrid_sim
            self._hybrid_sim_step(motor_commands, pluck_triggered)
        
        # Compute reward
        reward = self._compute_reward(action, pluck_triggered)
        self.episode_reward += reward
        
        # Check termination
        terminated = self._check_terminated()
        truncated = self.step_count >= self.max_steps
        
        # Build observation and info
        observation = self._get_obs()
        info = self._get_info()
        info['motor_commands'] = motor_commands
        info['pluck_triggered'] = pluck_triggered
        
        # Store state history
        self.state_history.append(observation.copy())
        
        return observation, reward, terminated, truncated, info
    
    def _action_to_motor_commands(self, action: Dict) -> Dict:
        """
        Convert high-level action to motor commands.
        
        Args:
            action: Action dict from agent
            
        Returns:
            Dict with target motor positions/torques
        """
        commands = {
            'slider_targets': np.zeros(self.num_strings),
            'presser_targets': np.zeros(self.num_strings),
            'picker_triggers': np.zeros(min(self.num_strings, 3)),
        }
        
        if self.action_space_type == 'discrete':
            # Discrete: fret (0-9), press (0/1), pluck (0/1)
            for i in range(self.num_strings):
                fret = action['fret'][i]
                commands['slider_targets'][i] = fret_to_slider_position(i, fret)
                commands['presser_targets'][i] = (
                    TORQUE_MAX if action['press'][i] else TORQUE_MIN
                )
            for i in range(min(self.num_strings, 3)):
                commands['picker_triggers'][i] = action['pluck'][i]
                
        elif self.action_space_type == 'continuous':
            # Continuous: delta_slider, delta_torque, pluck
            for i in range(self.num_strings):
                commands['slider_targets'][i] = (
                    self.slider_positions[i] + action['delta_slider'][i]
                )
                commands['presser_targets'][i] = np.clip(
                    self.presser_torques[i] + action['delta_torque'][i],
                    TORQUE_MIN, TORQUE_MAX
                )
            for i in range(min(self.num_strings, 3)):
                commands['picker_triggers'][i] = action['pluck'][i]
                
        else:  # hybrid
            # Hybrid: fret (discrete), force (continuous), pluck (discrete)
            for i in range(self.num_strings):
                fret = action['fret'][i]
                commands['slider_targets'][i] = fret_to_slider_position(i, fret)
                commands['presser_targets'][i] = force_to_torque(
                    action['force'][i]
                )
            for i in range(min(self.num_strings, 3)):
                commands['picker_triggers'][i] = action['pluck'][i]
        
        return commands
    
    def _simulate_step(self, motor_commands: Dict, pluck_triggered: bool):
        """
        Simulate motor state changes (no hardware).
        
        Updates internal state to target values instantly.
        Simulates basic audio response if pluck triggered.
        """
        for i in range(self.num_strings):
            self.slider_positions[i] = motor_commands['slider_targets'][i]
            self.presser_torques[i] = motor_commands['presser_targets'][i]
            self.fret_positions[i] = slider_position_to_fret(
                i, self.slider_positions[i]
            )
            self.pressed_state[i] = (
                1 if self.presser_torques[i] > (TORQUE_MIN + TORQUE_MAX) / 2 
                else 0
            )
        
        for i in range(min(self.num_strings, 3)):
            self.picker_state[i] = int(motor_commands['picker_triggers'][i])
        
        # Simulate audio features
        if pluck_triggered and self.include_audio:
            self._simulate_audio()
    
    def _simulate_audio(self):
        """Simulate audio features based on current state."""
        # Simple simulation: pressed strings produce cleaner notes
        is_pressed = any(self.pressed_state)
        
        if is_pressed:
            # Clear note with good pitch
            self.audio_features['peak_rms_db'] = np.array(
                [-20.0 + np.random.normal(0, 3)], dtype=np.float32
            )
            self.audio_features['spectral_flatness'] = np.array(
                [0.1 + np.random.uniform(0, 0.1)], dtype=np.float32
            )
            # Simulated pitch based on fret position
            base_freq = 82.41  # Low E
            fret = self.fret_positions[0] if len(self.fret_positions) > 0 else 0
            freq = base_freq * (2 ** (fret / 12.0))
            self.audio_features['fundamental_freq'] = np.array(
                [freq + np.random.normal(0, 2)], dtype=np.float32
            )
            self.audio_features['onset_time'] = np.array(
                [0.05 + np.random.uniform(0, 0.02)], dtype=np.float32
            )
            
            # Simulate classification: pressed = general_note (90%), harmonic (10%)
            if np.random.random() < 0.1:
                # Rare harmonic
                self.audio_features['audio_class'] = AUDIO_CLASS_HARMONIC
                self.audio_features['audio_class_probs'] = np.array(
                    [0.7, 0.1, 0.2], dtype=np.float32
                )
                self.audio_features['audio_class_confidence'] = np.array(
                    [0.7], dtype=np.float32
                )
            else:
                # Normal general note
                self.audio_features['audio_class'] = AUDIO_CLASS_GENERAL_NOTE
                self.audio_features['audio_class_probs'] = np.array(
                    [0.1, 0.1, 0.8], dtype=np.float32
                )
                self.audio_features['audio_class_confidence'] = np.array(
                    [0.8], dtype=np.float32
                )
        else:
            # Muted/buzzy sound
            self.audio_features['peak_rms_db'] = np.array(
                [-40.0 + np.random.normal(0, 5)], dtype=np.float32
            )
            self.audio_features['spectral_flatness'] = np.array(
                [0.5 + np.random.uniform(0, 0.3)], dtype=np.float32
            )
            self.audio_features['fundamental_freq'] = np.array(
                [0.0], dtype=np.float32
            )
            self.audio_features['onset_time'] = np.array(
                [0.1 + np.random.uniform(0, 0.1)], dtype=np.float32
            )
            
            # Simulate classification: unpressed = dead_note (70%), general (30%)
            if np.random.random() < 0.7:
                self.audio_features['audio_class'] = AUDIO_CLASS_DEAD_NOTE
                self.audio_features['audio_class_probs'] = np.array(
                    [0.1, 0.7, 0.2], dtype=np.float32
                )
                self.audio_features['audio_class_confidence'] = np.array(
                    [0.7], dtype=np.float32
                )
            else:
                self.audio_features['audio_class'] = AUDIO_CLASS_GENERAL_NOTE
                self.audio_features['audio_class_probs'] = np.array(
                    [0.15, 0.35, 0.5], dtype=np.float32
                )
                self.audio_features['audio_class_confidence'] = np.array(
                    [0.5], dtype=np.float32
                )
    
    def _hardware_step(self, motor_commands: Dict, pluck_triggered: bool):
        """
        Execute step on real hardware.
        
        Generates trajectory and sends to robot controller.
        Captures and analyzes audio response.
        """
        if self._robot_controller is None:
            self._init_hardware()
        
        # Generate trajectory
        trajectory = self.trajectory_generator.generate(
            current_state={
                'slider_positions': self.slider_positions,
                'presser_torques': self.presser_torques,
            },
            target_commands=motor_commands,
            pluck=pluck_triggered,
        )
        
        # Send trajectory to robot
        self._robot_controller.send_trajectory(trajectory)
        
        # Wait for execution
        time.sleep(self.trajectory_generator.get_duration())
        
        # Capture audio if pluck triggered
        if pluck_triggered and self.include_audio:
            self._capture_and_analyze_audio()
        
        # Update state from trajectory endpoints
        for i in range(self.num_strings):
            self.slider_positions[i] = motor_commands['slider_targets'][i]
            self.presser_torques[i] = motor_commands['presser_targets'][i]
            self.fret_positions[i] = slider_position_to_fret(
                i, self.slider_positions[i]
            )
            self.pressed_state[i] = (
                1 if self.presser_torques[i] > (TORQUE_MIN + TORQUE_MAX) / 2
                else 0
            )
    
    def _hybrid_sim_step(self, motor_commands: Dict, pluck_triggered: bool):
        """
        Hybrid simulation with physics-based audio model.
        
        Uses simulated motors but models audio response based on
        physical guitar properties.
        """
        # Update motor state (simulated)
        self._simulate_step(motor_commands, pluck_triggered)
        
        # TODO: Add physics-based audio synthesis model
        # For now, uses same simulation as _simulate_step
    
    def _compute_reward(self, action: Dict, pluck_triggered: bool) -> float:
        """
        Compute reward for the current step.
        
        Reward components:
        1. Audio quality (if pluck triggered)
        2. Pitch accuracy (if target_note specified)
        3. Action smoothness penalty
        4. Safety penalties
        
        Args:
            action: The action taken
            pluck_triggered: Whether a pluck was triggered
            
        Returns:
            Total reward for this step
        """
        reward = 0.0
        
        if pluck_triggered:
            # Base reward for attempting to pluck
            reward += 0.1
            
            # Audio quality reward
            rms = self.audio_features['peak_rms_db'][0]
            flatness = self.audio_features['spectral_flatness'][0]
            
            # Reward louder, cleaner notes
            if rms > -60:  # Audible
                reward += 0.2
            if rms > -40:  # Good volume
                reward += 0.3
            if flatness < 0.3:  # Tonal (not buzzy)
                reward += 0.3
            
            # Pitch accuracy reward (if target specified)
            if self.target_note is not None:
                target_freq = 440.0 * (2 ** ((self.target_note - 69) / 12.0))
                detected_freq = self.audio_features['fundamental_freq'][0]
                
                if detected_freq > 0:
                    # Cents deviation
                    cents = 1200 * np.log2(detected_freq / target_freq)
                    cents_error = abs(cents)
                    
                    if cents_error < 10:  # Within 10 cents
                        reward += 1.0
                    elif cents_error < 25:  # Within quarter-tone
                        reward += 0.5
                    elif cents_error < 50:  # Within half-step
                        reward += 0.1
        
        # Action smoothness penalty
        if len(self.action_history) >= 2:
            prev_action = self.action_history[-2]
            if 'fret' in action and 'fret' in prev_action:
                fret_change = np.abs(
                    np.array(action['fret']) - np.array(prev_action['fret'])
                ).sum()
                # Penalize large jumps
                if fret_change > 4:
                    reward -= 0.1 * (fret_change - 4)
        
        # Safety penalty: invalid states
        is_valid, errors = validate_motor_state(
            self.slider_positions, 
            self.presser_torques,
            self.picker_positions
        )
        if not is_valid:
            reward -= 1.0  # Significant penalty for unsafe states
        
        return reward
    
    def _check_terminated(self) -> bool:
        """Check if episode should terminate early."""
        # Terminate on safety violations
        is_valid, _ = validate_motor_state(
            self.slider_positions,
            self.presser_torques, 
            self.picker_positions
        )
        if not is_valid:
            return True
        
        # No early termination by default
        return False
    
    def _init_hardware(self):
        """Initialize hardware connections."""
        try:
            from RobotController import RobotController
            from Recording.AudioAnalyzer import AudioAnalyzer
            
            self._robot_controller = RobotController()
            self._audio_analyzer = AudioAnalyzer()
            print("[GuitarBotEnv] Hardware initialized")
        except ImportError as e:
            print(f"[GuitarBotEnv] Warning: Could not import hardware: {e}")
            print("[GuitarBotEnv] Falling back to simulation mode")
            self.mode = 'simulation'
    
    def _reset_hardware(self):
        """Reset robot to home position."""
        if self._robot_controller is not None:
            # Generate reset trajectory
            reset_traj = self.trajectory_generator.generate_reset()
            self._robot_controller.send_trajectory(reset_traj)
            time.sleep(2.0)  # Wait for reset
    
    def _capture_and_analyze_audio(self):
        """Capture audio and extract features."""
        if self._audio_analyzer is None:
            return
        
        try:
            # Capture ~500ms of audio
            audio_data = self._audio_analyzer.capture(duration=0.5)
            features = self._audio_analyzer.analyze(audio_data)
            
            self.audio_features['peak_rms_db'] = np.array(
                [features.get('rms_db', -80)], dtype=np.float32
            )
            self.audio_features['spectral_flatness'] = np.array(
                [features.get('spectral_flatness', 0.5)], dtype=np.float32
            )
            self.audio_features['fundamental_freq'] = np.array(
                [features.get('f0', 0)], dtype=np.float32
            )
            self.audio_features['onset_time'] = np.array(
                [features.get('onset_time', 0)], dtype=np.float32
            )
            
            self.audio_history.append(features)
        except Exception as e:
            print(f"[GuitarBotEnv] Audio capture error: {e}")
    
    def _init_classifier(self, model_path: Optional[str] = None):
        """
        Initialize the audio classifier model.
        
        Args:
            model_path: Path to the trained model .pt file.
                       If None, looks for default at ../HarmonicsClassifier/models/best_model.pt
        """
        try:
            import torch
            
            # Add HarmonicsClassifier to path
            classifier_path = Path(__file__).parent.parent.parent / "HarmonicsClassifier"
            if classifier_path.exists():
                sys.path.insert(0, str(classifier_path))
            
            from inference import HarmonicsCNN, load_model
            
            # Determine device
            self._classifier_device = torch.device(
                'cuda' if torch.cuda.is_available() else 'cpu'
            )
            
            # Find model path
            if model_path is None:
                # Try default locations
                default_paths = [
                    classifier_path / "models" / "best_model.pt",
                    Path(__file__).parent / "models" / "harmonics_classifier.pt",
                ]
                for p in default_paths:
                    if p.exists():
                        model_path = str(p)
                        break
            
            if model_path is None or not Path(model_path).exists():
                print(f"[GuitarBotEnv] Warning: Classifier model not found")
                return
            
            self._classifier_model_path = model_path
            self._audio_classifier, _ = load_model(model_path, self._classifier_device)
            print(f"[GuitarBotEnv] Audio classifier loaded from {model_path}")
            print(f"[GuitarBotEnv] Using device: {self._classifier_device}")
            
        except ImportError as e:
            print(f"[GuitarBotEnv] Warning: Could not import classifier: {e}")
            self._audio_classifier = None
        except Exception as e:
            print(f"[GuitarBotEnv] Warning: Classifier init error: {e}")
            self._audio_classifier = None
    
    def classify_audio(
        self, 
        audio_path: Optional[str] = None,
        audio_data: Optional[np.ndarray] = None,
        sample_rate: int = 22050,
        duration: float = 3.0,
    ) -> Dict[str, Any]:
        """
        Classify audio using the harmonics classifier.
        
        Args:
            audio_path: Path to audio file (wav, mp3, etc.)
            audio_data: Raw audio samples as numpy array (alternative to audio_path)
            sample_rate: Sample rate of audio_data (default 22050)
            duration: Duration in seconds to analyze (default 3.0)
            
        Returns:
            Dict with:
                - 'class': Predicted class index (0=harmonic, 1=dead_note, 2=general_note)
                - 'class_name': String name of predicted class
                - 'confidence': Confidence of prediction (0.0-1.0)
                - 'probabilities': Array of probabilities for each class
        """
        # Initialize classifier if needed
        if self._audio_classifier is None:
            self._init_classifier()
        
        if self._audio_classifier is None:
            # Return default (general_note) if classifier unavailable
            return {
                'class': AUDIO_CLASS_GENERAL_NOTE,
                'class_name': AUDIO_CLASS_NAMES[AUDIO_CLASS_GENERAL_NOTE],
                'confidence': 0.0,
                'probabilities': np.array([0.33, 0.33, 0.34], dtype=np.float32),
            }
        
        try:
            import torch
            from inference import preprocess_audio, predict
            
            # Handle audio_data by saving to temp file if needed
            temp_file = None
            if audio_data is not None and audio_path is None:
                import soundfile as sf
                temp_file = tempfile.NamedTemporaryFile(
                    suffix='.wav', delete=False
                )
                sf.write(temp_file.name, audio_data, sample_rate)
                audio_path = temp_file.name
            
            if audio_path is None:
                raise ValueError("Either audio_path or audio_data must be provided")
            
            # Preprocess and classify
            audio_tensor = preprocess_audio(audio_path, duration=duration)
            predicted_class, confidence, probabilities = predict(
                self._audio_classifier, audio_tensor, self._classifier_device
            )
            
            # Cleanup temp file
            if temp_file is not None:
                os.unlink(temp_file.name)
            
            # Update audio features with classification
            self.audio_features['audio_class'] = predicted_class
            self.audio_features['audio_class_probs'] = probabilities.astype(np.float32)
            self.audio_features['audio_class_confidence'] = np.array(
                [confidence], dtype=np.float32
            )
            
            return {
                'class': predicted_class,
                'class_name': AUDIO_CLASS_NAMES[predicted_class],
                'confidence': confidence,
                'probabilities': probabilities,
            }
            
        except Exception as e:
            print(f"[GuitarBotEnv] Classification error: {e}")
            return {
                'class': AUDIO_CLASS_GENERAL_NOTE,
                'class_name': AUDIO_CLASS_NAMES[AUDIO_CLASS_GENERAL_NOTE],
                'confidence': 0.0,
                'probabilities': np.array([0.33, 0.33, 0.34], dtype=np.float32),
            }
    
    def classify_audio_from_capture(self, duration: float = 0.5) -> Dict[str, Any]:
        """
        Capture audio from the hardware and classify it.
        
        This is a convenience method that captures audio from the audio analyzer
        and immediately classifies it.
        
        Args:
            duration: Duration to capture in seconds
            
        Returns:
            Classification result dict (see classify_audio)
        """
        if self._audio_analyzer is None:
            print("[GuitarBotEnv] Warning: No audio analyzer initialized")
            return self.classify_audio(audio_data=None)
        
        try:
            # Capture audio
            audio_data = self._audio_analyzer.capture(duration=duration)
            sample_rate = getattr(self._audio_analyzer, 'sample_rate', 22050)
            
            # Classify
            return self.classify_audio(
                audio_data=audio_data,
                sample_rate=sample_rate,
                duration=duration
            )
        except Exception as e:
            print(f"[GuitarBotEnv] Capture and classify error: {e}")
            return self.classify_audio(audio_data=None)
    
    def get_audio_class_reward(self, target_class: int = AUDIO_CLASS_GENERAL_NOTE) -> float:
        """
        Compute reward based on audio classification.
        
        Args:
            target_class: Target class index (0=harmonic, 1=dead_note, 2=general_note)
            
        Returns:
            Reward value:
                +1.0 if predicted class matches target
                -0.5 if dead_note when target is general_note
                +0.5 if harmonic when target is general_note (bonus for harmonics)
                0.0 otherwise
        """
        predicted_class = self.audio_features.get('audio_class', AUDIO_CLASS_GENERAL_NOTE)
        confidence = self.audio_features.get('audio_class_confidence', np.array([0.0]))[0]
        
        if predicted_class == target_class:
            return 1.0 * confidence
        
        # Special cases
        if target_class == AUDIO_CLASS_GENERAL_NOTE:
            if predicted_class == AUDIO_CLASS_DEAD_NOTE:
                return -0.5 * confidence  # Penalize dead notes
            elif predicted_class == AUDIO_CLASS_HARMONIC:
                return 0.5 * confidence  # Bonus for harmonics
        
        if target_class == AUDIO_CLASS_HARMONIC:
            if predicted_class == AUDIO_CLASS_DEAD_NOTE:
                return -1.0 * confidence  # Strong penalty
        
        return 0.0
    
    def render(self):
        """Render current state."""
        if self.render_mode == "human":
            self._render_text()
        elif self.render_mode == "rgb_array":
            return self._render_image()
        return None
    
    def _render_text(self):
        """Print text representation of state."""
        print(f"\n=== Step {self.step_count} ===")
        print(f"Frets: {self.fret_positions}")
        print(f"Pressed: {self.pressed_state}")
        print(f"Episode Reward: {self.episode_reward:.2f}")
        if self.include_audio:
            print(f"RMS: {self.audio_features['peak_rms_db'][0]:.1f} dB")
            print(f"Freq: {self.audio_features['fundamental_freq'][0]:.1f} Hz")
            # Show classification
            audio_class = self.audio_features.get('audio_class', 2)
            confidence = self.audio_features.get('audio_class_confidence', np.array([0.0]))[0]
            class_name = AUDIO_CLASS_NAMES[audio_class] if audio_class < len(AUDIO_CLASS_NAMES) else 'unknown'
            print(f"Class: {class_name} ({confidence*100:.1f}% confidence)")
    
    def _render_image(self) -> np.ndarray:
        """Generate RGB image of state."""
        # Simple visualization: 100x200 RGB image
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        
        # Draw fretboard lines
        for i in range(10):
            x = 20 + i * 18
            img[10:90, x:x+2] = [100, 100, 100]
        
        # Draw string
        img[45:55, 10:190] = [150, 100, 50]
        
        # Draw fret position
        if len(self.fret_positions) > 0:
            fret = self.fret_positions[0]
            if fret > 0:
                x = 20 + (fret - 1) * 18 + 9
                img[40:60, x-5:x+5] = [255, 0, 0]  # Red dot
        
        return img
    
    def close(self):
        """Cleanup resources."""
        if self._robot_controller is not None:
            self._reset_hardware()
        self._robot_controller = None
        self._audio_analyzer = None


# =============================================================================
# Registered Environment
# =============================================================================

def register_guitarbot_envs():
    """Register GuitarBot environments with Gymnasium."""
    try:
        gym.register(
            id='GuitarBot-v0',
            entry_point='rl.guitar_bot_env:GuitarBotEnv',
            kwargs={'num_strings': 1, 'mode': 'simulation'},
        )
        gym.register(
            id='GuitarBot-Hardware-v0',
            entry_point='rl.guitar_bot_env:GuitarBotEnv',
            kwargs={'num_strings': 1, 'mode': 'hardware'},
        )
        print("Registered GuitarBot-v0 and GuitarBot-Hardware-v0")
    except Exception as e:
        print(f"Environment registration error: {e}")


# =============================================================================
# Test Code
# =============================================================================

if __name__ == "__main__":
    print("=== GuitarBot Environment Test ===\n")
    
    # Create environment in simulation mode
    env = GuitarBotEnv(
        num_strings=1,
        action_space_type='hybrid',
        mode='simulation',
        include_audio=True,
        target_note=64,  # E4
        render_mode='human',
    )
    
    print(f"Action Space: {env.action_space}")
    print(f"Observation Space: {env.observation_space}\n")
    
    # Reset environment
    obs, info = env.reset()
    print(f"Initial observation: {obs}")
    print(f"Info: {info}\n")
    
    # Run a few steps
    total_reward = 0
    for step in range(5):
        # Sample random action
        action = env.action_space.sample()
        # Force a pluck on some steps
        if step % 2 == 0:
            action['pluck'] = np.array([1])
        
        print(f"\nStep {step + 1}: Action = {action}")
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        
        env.render()
        print(f"Reward: {reward:.2f}")
        
        if terminated or truncated:
            print("Episode ended!")
            break
    
    print(f"\n=== Total Reward: {total_reward:.2f} ===")
    
    env.close()
    print("\nTest complete!")
