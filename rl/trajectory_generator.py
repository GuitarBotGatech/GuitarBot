"""
trajectory_generator.py - Convert RL actions to robot trajectories

This module provides low-level trajectory generation for the GuitarBot,
converting high-level RL actions into smooth, executable motor trajectories.

Key responsibilities:
1. Convert target positions to time-indexed arrays
2. Apply smooth interpolation with blend curves
3. Coordinate multi-motor synchronization
4. Respect timing constraints and safety limits
5. Generate pluck trajectories with proper timing

The TrajectoryGenerator wraps the existing interp_with_blend function
from GuitarBotParser and adds RL-specific features.
"""

import numpy as np
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import tune as tu
from GuitarBotParser import GuitarBotParser


# =============================================================================
# Timing Constants
# =============================================================================

# Trajectory timing (seconds)
TIME_STEP = tu.TIME_STEP  # 0.005s = 5ms

# Phase durations for standard RL step
UNPRESS_DURATION = 0.050    # 50ms to release pressure
SLIDE_DURATION = 0.150      # 150ms for slider motion
PRESS_DURATION = 0.050      # 50ms to apply pressure
REST_DURATION = 0.100       # 100ms hold before pluck
PLUCK_DURATION = 0.050      # 50ms for pluck motion
POST_PLUCK_DURATION = 0.200 # 200ms for note to ring

# Point counts (duration / TIME_STEP)
UNPRESS_POINTS = int(UNPRESS_DURATION / TIME_STEP)
SLIDE_POINTS = int(SLIDE_DURATION / TIME_STEP)
PRESS_POINTS = int(PRESS_DURATION / TIME_STEP)
REST_POINTS = int(REST_DURATION / TIME_STEP)
PLUCK_POINTS = int(PLUCK_DURATION / TIME_STEP)
POST_PLUCK_POINTS = int(POST_PLUCK_DURATION / TIME_STEP)

# Blend percentage for smooth starts/stops
BLEND_PERCENT = tu.TRAJECTORY_BLEND_PERCENT  # 0.4

# Total points per RL step (no pluck)
MOVE_TOTAL_POINTS = UNPRESS_POINTS + SLIDE_POINTS + PRESS_POINTS + REST_POINTS

# Total points per RL step (with pluck)
PLUCK_TOTAL_POINTS = MOVE_TOTAL_POINTS + PLUCK_POINTS + POST_PLUCK_POINTS


# =============================================================================
# TrajectoryGenerator Class
# =============================================================================

class TrajectoryGenerator:
    """
    Generates smooth motor trajectories for RL actions.
    
    This class converts high-level motor commands (target positions, torques)
    into time-indexed trajectory arrays suitable for the RobotController.
    
    Attributes:
        num_strings: Number of strings to control
        num_motors: Total motor count (sliders + pressers + pickers)
    """
    
    def __init__(self, num_strings: int = 1):
        """
        Initialize trajectory generator.
        
        Args:
            num_strings: Number of strings to control (1, 3, or 6)
        """
        self.num_strings = num_strings
        self.num_motors = 15  # 6 sliders + 6 pressers + 3 pickers
        
        # Track last trajectory endpoint for continuity
        self.last_endpoint = None
        
    def get_duration(self, with_pluck: bool = False) -> float:
        """
        Get the duration of a single RL step trajectory.
        
        Args:
            with_pluck: Whether the step includes a pluck
            
        Returns:
            Duration in seconds
        """
        if with_pluck:
            return PLUCK_TOTAL_POINTS * TIME_STEP
        else:
            return MOVE_TOTAL_POINTS * TIME_STEP
    
    def get_num_points(self, with_pluck: bool = False) -> int:
        """
        Get the number of trajectory points for a single RL step.
        
        Args:
            with_pluck: Whether the step includes a pluck
            
        Returns:
            Number of trajectory points
        """
        return PLUCK_TOTAL_POINTS if with_pluck else MOVE_TOTAL_POINTS
    
    def generate(
        self,
        current_state: Dict[str, np.ndarray],
        target_commands: Dict[str, np.ndarray],
        pluck: bool = False,
    ) -> np.ndarray:
        """
        Generate a complete trajectory for an RL step.
        
        The trajectory follows this sequence:
        1. UNPRESS: Release presser torque (if changing fret)
        2. SLIDE: Move slider to target position
        3. PRESS: Apply target presser torque
        4. REST: Hold position briefly
        5. PLUCK (optional): Execute pluck motion
        6. POST_PLUCK (optional): Let note ring
        
        Args:
            current_state: Dict with current motor positions:
                - 'slider_positions': Current slider positions
                - 'presser_torques': Current presser torques
            target_commands: Dict with target motor values:
                - 'slider_targets': Target slider positions
                - 'presser_targets': Target presser torques
                - 'picker_triggers': Which pickers to activate
            pluck: Whether to include pluck at end
            
        Returns:
            np.ndarray of shape (num_points, 15) with trajectory
        """
        # Get current positions
        curr_sliders = np.array(current_state.get('slider_positions', 
                                np.zeros(self.num_strings)))
        curr_pressers = np.array(current_state.get('presser_torques',
                                 np.full(self.num_strings, tu.LH_PRESSER_UNPRESSED_POS)))
        
        # Get targets
        target_sliders = np.array(target_commands.get('slider_targets',
                                  curr_sliders))
        target_pressers = np.array(target_commands.get('presser_targets',
                                   curr_pressers))
        picker_triggers = np.array(target_commands.get('picker_triggers',
                                   np.zeros(min(self.num_strings, 3))))
        
        # Build trajectory phases
        trajectories = []
        
        # --- Phase 1: UNPRESS ---
        phase1_sliders = self._interpolate_hold(curr_sliders, UNPRESS_POINTS)
        phase1_pressers = self._interpolate_move(
            curr_pressers, 
            np.full(self.num_strings, tu.LH_PRESSER_UNPRESSED_POS),
            UNPRESS_POINTS
        )
        phase1_pickers = self._interpolate_hold(
            np.zeros(3),  # Pickers at rest
            UNPRESS_POINTS
        )
        trajectories.append(self._combine_phases(
            phase1_sliders, phase1_pressers, phase1_pickers
        ))
        
        # --- Phase 2: SLIDE ---
        phase2_sliders = self._interpolate_move(
            curr_sliders, target_sliders, SLIDE_POINTS
        )
        phase2_pressers = self._interpolate_hold(
            np.full(self.num_strings, tu.LH_PRESSER_UNPRESSED_POS),
            SLIDE_POINTS
        )
        phase2_pickers = self._interpolate_hold(np.zeros(3), SLIDE_POINTS)
        trajectories.append(self._combine_phases(
            phase2_sliders, phase2_pressers, phase2_pickers
        ))
        
        # --- Phase 3: PRESS ---
        phase3_sliders = self._interpolate_hold(target_sliders, PRESS_POINTS)
        phase3_pressers = self._interpolate_move(
            np.full(self.num_strings, tu.LH_PRESSER_UNPRESSED_POS),
            target_pressers,
            PRESS_POINTS
        )
        phase3_pickers = self._interpolate_hold(np.zeros(3), PRESS_POINTS)
        trajectories.append(self._combine_phases(
            phase3_sliders, phase3_pressers, phase3_pickers
        ))
        
        # --- Phase 4: REST ---
        phase4_sliders = self._interpolate_hold(target_sliders, REST_POINTS)
        phase4_pressers = self._interpolate_hold(target_pressers, REST_POINTS)
        phase4_pickers = self._interpolate_hold(np.zeros(3), REST_POINTS)
        trajectories.append(self._combine_phases(
            phase4_sliders, phase4_pressers, phase4_pickers
        ))
        
        # --- Phase 5 & 6: PLUCK (optional) ---
        if pluck and any(picker_triggers):
            pluck_traj = self._generate_pluck_trajectory(
                target_sliders, target_pressers, picker_triggers
            )
            trajectories.append(pluck_traj)
        
        # Concatenate all phases
        full_trajectory = np.vstack(trajectories)
        
        # Store endpoint for next trajectory
        self.last_endpoint = full_trajectory[-1, :].copy()
        
        return full_trajectory
    
    def _interpolate_move(
        self, 
        start: np.ndarray, 
        end: np.ndarray, 
        num_points: int
    ) -> np.ndarray:
        """
        Interpolate from start to end with blend curves.
        
        Args:
            start: Starting values (per motor)
            end: Ending values (per motor)
            num_points: Number of trajectory points
            
        Returns:
            Array of shape (num_points, len(start))
        """
        result = []
        for i in range(len(start)):
            interp = GuitarBotParser.interp_with_blend(
                start[i], end[i], num_points, BLEND_PERCENT
            )
            result.append(interp)
        return np.array(result).T  # Transpose to (num_points, num_motors)
    
    def _interpolate_hold(
        self,
        values: np.ndarray,
        num_points: int
    ) -> np.ndarray:
        """
        Hold constant values for a number of points.
        
        Args:
            values: Values to hold (per motor)
            num_points: Number of trajectory points
            
        Returns:
            Array of shape (num_points, len(values))
        """
        return np.tile(values, (num_points, 1))
    
    def _combine_phases(
        self,
        sliders: np.ndarray,
        pressers: np.ndarray,
        pickers: np.ndarray,
    ) -> np.ndarray:
        """
        Combine slider, presser, and picker trajectories into full 15-motor array.
        
        Args:
            sliders: Slider trajectory (num_points, num_strings)
            pressers: Presser trajectory (num_points, num_strings)
            pickers: Picker trajectory (num_points, 3)
            
        Returns:
            Combined trajectory (num_points, 15)
        """
        num_points = sliders.shape[0]
        
        # Create full 15-motor trajectory
        full = np.zeros((num_points, 15))
        
        # Fill sliders (motors 0-5)
        for i in range(min(self.num_strings, 6)):
            full[:, i] = sliders[:, i] if sliders.shape[1] > i else 0
        
        # Fill pressers (motors 6-11)
        for i in range(min(self.num_strings, 6)):
            full[:, 6 + i] = pressers[:, i] if pressers.shape[1] > i else tu.LH_PRESSER_UNPRESSED_POS
        
        # Fill pickers (motors 12-14)
        for i in range(3):
            full[:, 12 + i] = pickers[:, i] if pickers.shape[1] > i else 0
        
        return full
    
    def _generate_pluck_trajectory(
        self,
        slider_positions: np.ndarray,
        presser_torques: np.ndarray,
        picker_triggers: np.ndarray,
    ) -> np.ndarray:
        """
        Generate pluck trajectory for triggered pickers.
        
        Pluck motion:
        1. Move picker to pluck position (PLUCK_POINTS)
        2. Hold for note to ring (POST_PLUCK_POINTS)
        
        Args:
            slider_positions: Current slider positions (held constant)
            presser_torques: Current presser torques (held constant)
            picker_triggers: Binary array of which pickers to trigger
            
        Returns:
            Pluck trajectory (PLUCK_POINTS + POST_PLUCK_POINTS, 15)
        """
        total_points = PLUCK_POINTS + POST_PLUCK_POINTS
        
        # Hold sliders and pressers constant
        sliders = self._interpolate_hold(slider_positions, total_points)
        pressers = self._interpolate_hold(presser_torques, total_points)
        
        # Generate picker motions
        picker_positions = []
        for i in range(3):
            if i < len(picker_triggers) and picker_triggers[i]:
                # Pluck: move from rest to pluck position, then back
                rest_pos = tu.PICKER_MOTOR_REST_POS
                pluck_pos = tu.PICKER_MOTOR_PLUCK_POS
                
                # Move to pluck
                pluck_motion = GuitarBotParser.interp_with_blend(
                    rest_pos, pluck_pos, PLUCK_POINTS, BLEND_PERCENT
                )
                # Return to rest
                return_motion = GuitarBotParser.interp_with_blend(
                    pluck_pos, rest_pos, POST_PLUCK_POINTS, BLEND_PERCENT
                )
                picker_positions.append(
                    np.concatenate([pluck_motion, return_motion])
                )
            else:
                # No pluck: hold at rest
                picker_positions.append(
                    np.full(total_points, tu.PICKER_MOTOR_REST_POS)
                )
        
        pickers = np.array(picker_positions).T
        
        return self._combine_phases(sliders, pressers, pickers)
    
    def generate_reset(
        self,
        current_positions: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Generate trajectory to reset robot to home position.
        
        Args:
            current_positions: Current motor positions (15,).
                              If None, uses last_endpoint.
                              
        Returns:
            Reset trajectory (num_points, 15)
        """
        if current_positions is None:
            if self.last_endpoint is not None:
                current_positions = self.last_endpoint
            else:
                # Assume default positions
                current_positions = np.zeros(15)
                current_positions[6:12] = tu.LH_PRESSER_UNPRESSED_POS
        
        # Home positions
        home = np.zeros(15)
        home[6:12] = tu.LH_PRESSER_UNPRESSED_POS  # Pressers released
        home[12:15] = tu.PICKER_MOTOR_REST_POS    # Pickers at rest
        
        # Use longer duration for reset
        reset_points = int(0.5 / TIME_STEP)  # 500ms
        
        # Interpolate each motor
        trajectory = []
        for i in range(15):
            interp = GuitarBotParser.interp_with_blend(
                current_positions[i], home[i], reset_points, BLEND_PERCENT
            )
            trajectory.append(interp)
        
        return np.array(trajectory).T
    
    def generate_from_action(
        self,
        action: Dict,
        current_state: Dict[str, np.ndarray],
        action_type: str = 'hybrid',
    ) -> np.ndarray:
        """
        Convenience method to generate trajectory directly from RL action.
        
        This is a higher-level wrapper that handles action interpretation.
        
        Args:
            action: RL action dict
            current_state: Current motor state
            action_type: 'discrete', 'continuous', or 'hybrid'
            
        Returns:
            Trajectory array
        """
        from rl.action_space import (
            force_to_torque, fret_to_slider_position
        )
        
        # Convert action to motor commands
        commands = {
            'slider_targets': np.zeros(self.num_strings),
            'presser_targets': np.zeros(self.num_strings),
            'picker_triggers': np.zeros(min(self.num_strings, 3)),
        }
        
        curr_sliders = current_state.get('slider_positions',
                                          np.zeros(self.num_strings))
        curr_pressers = current_state.get('presser_torques',
                                           np.full(self.num_strings, 
                                                   tu.LH_PRESSER_UNPRESSED_POS))
        
        if action_type == 'discrete':
            for i in range(self.num_strings):
                fret = action['fret'][i]
                commands['slider_targets'][i] = fret_to_slider_position(i, fret)
                pressed = action.get('press', [0])[i] if i < len(action.get('press', [])) else 0
                commands['presser_targets'][i] = (
                    tu.LH_PRESSER_PRESSED_POS if pressed else tu.LH_PRESSER_UNPRESSED_POS
                )
                
        elif action_type == 'continuous':
            for i in range(self.num_strings):
                delta_slider = action.get('delta_slider', [0])[i]
                delta_torque = action.get('delta_torque', [0])[i]
                commands['slider_targets'][i] = curr_sliders[i] + delta_slider
                commands['presser_targets'][i] = np.clip(
                    curr_pressers[i] + delta_torque,
                    tu.LH_PRESSER_UNPRESSED_POS, tu.LH_PRESSER_PRESSED_POS
                )
                
        else:  # hybrid
            for i in range(self.num_strings):
                fret = action['fret'][i]
                force = action.get('force', [0.0])[i]
                commands['slider_targets'][i] = fret_to_slider_position(i, fret)
                commands['presser_targets'][i] = force_to_torque(force)
        
        # Handle pluck triggers
        pluck_triggers = action.get('pluck', np.zeros(3))
        for i in range(min(len(pluck_triggers), 3)):
            commands['picker_triggers'][i] = pluck_triggers[i]
        
        pluck = any(commands['picker_triggers'])
        
        return self.generate(current_state, commands, pluck=pluck)


# =============================================================================
# Utility Functions
# =============================================================================

def estimate_trajectory_duration(
    start_positions: np.ndarray,
    target_positions: np.ndarray,
    with_pluck: bool = False,
) -> float:
    """
    Estimate how long a trajectory will take.
    
    Args:
        start_positions: Starting positions
        target_positions: Target positions
        with_pluck: Whether pluck is included
        
    Returns:
        Estimated duration in seconds
    """
    # Base duration from constants
    base_duration = TrajectoryGenerator().get_duration(with_pluck)
    
    # Could adjust based on distance, but for now use fixed timing
    return base_duration


def validate_trajectory(trajectory: np.ndarray) -> Tuple[bool, List[str]]:
    """
    Validate a trajectory for safety.
    
    Checks:
    - Position limits
    - Velocity limits (between consecutive points)
    - No NaN or Inf values
    
    Args:
        trajectory: Trajectory array (num_points, 15)
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    if trajectory is None or trajectory.size == 0:
        return False, ["Empty trajectory"]
    
    if np.any(np.isnan(trajectory)):
        errors.append("Trajectory contains NaN values")
    
    if np.any(np.isinf(trajectory)):
        errors.append("Trajectory contains Inf values")
    
    # Check slider limits (motors 0-5)
    for i in range(6):
        if np.any(trajectory[:, i] < -70000) or np.any(trajectory[:, i] > 70000):
            errors.append(f"Slider {i} exceeds position limits")
    
    # Check presser limits (motors 6-11)
    for i in range(6, 12):
        if np.any(trajectory[:, i] < -700) or np.any(trajectory[:, i] > 600):
            errors.append(f"Presser {i-6} exceeds torque limits")
    
    # Check picker limits (motors 12-14)
    for i in range(12, 15):
        if np.any(trajectory[:, i] < 0) or np.any(trajectory[:, i] > 2000):
            errors.append(f"Picker {i-12} exceeds position limits")
    
    # Check velocity limits (position change per step)
    max_slider_vel = 500  # encoder ticks per 5ms
    for i in range(6):
        velocities = np.abs(np.diff(trajectory[:, i]))
        if np.any(velocities > max_slider_vel):
            errors.append(f"Slider {i} exceeds velocity limit")
    
    return len(errors) == 0, errors


# =============================================================================
# Test Code
# =============================================================================

if __name__ == "__main__":
    print("=== Trajectory Generator Test ===\n")
    
    # Create generator
    gen = TrajectoryGenerator(num_strings=1)
    
    # Test basic trajectory
    print("1. Basic move trajectory (no pluck):")
    current_state = {
        'slider_positions': np.array([0]),
        'presser_torques': np.array([tu.LH_PRESSER_UNPRESSED_POS]),
    }
    target_commands = {
        'slider_targets': np.array([-28284]),  # Fret 5
        'presser_targets': np.array([tu.LH_PRESSER_PRESSED_POS]),
        'picker_triggers': np.array([0]),
    }
    
    traj = gen.generate(current_state, target_commands, pluck=False)
    print(f"   Shape: {traj.shape}")
    print(f"   Duration: {gen.get_duration(False):.3f}s")
    print(f"   Start slider: {traj[0, 0]}, End slider: {traj[-1, 0]}")
    print(f"   Start presser: {traj[0, 6]}, End presser: {traj[-1, 6]}")
    
    is_valid, errors = validate_trajectory(traj)
    print(f"   Valid: {is_valid}")
    if errors:
        for e in errors:
            print(f"   Error: {e}")
    
    # Test with pluck
    print("\n2. Move + pluck trajectory:")
    target_commands['picker_triggers'] = np.array([1])
    traj_pluck = gen.generate(current_state, target_commands, pluck=True)
    print(f"   Shape: {traj_pluck.shape}")
    print(f"   Duration: {gen.get_duration(True):.3f}s")
    print(f"   Picker start: {traj_pluck[0, 12]}, Picker max: {np.max(traj_pluck[:, 12])}")
    
    # Test reset
    print("\n3. Reset trajectory:")
    reset_traj = gen.generate_reset(traj_pluck[-1, :])
    print(f"   Shape: {reset_traj.shape}")
    print(f"   Final positions: sliders={reset_traj[-1, :6]}, pressers={reset_traj[-1, 6:12]}")
    
    # Test from action
    print("\n4. Generate from hybrid action:")
    action = {
        'fret': np.array([3]),
        'force': np.array([0.7]),
        'pluck': np.array([1]),
    }
    action_traj = gen.generate_from_action(action, current_state, 'hybrid')
    print(f"   Shape: {action_traj.shape}")
    
    print("\n=== Test Complete ===")
