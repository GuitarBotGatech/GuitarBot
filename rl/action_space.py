"""
action_space.py - Action and observation space definitions for GuitarBot RL

Defines Gymnasium-compatible action and observation spaces for reinforcement
learning on the GuitarBot. Supports both discrete and continuous control modes.

Action Space Options:
1. Discrete: fret_target (0-9), press (bool), pluck (bool)
2. Continuous: delta_slider, delta_torque, pluck_trigger
3. Hybrid: fret_target (discrete) + force_level (continuous) + pluck (discrete)

Observation Space:
- Motor positions (15 values)
- String/fret states (6 strings)
- Audio features from last pluck (RMS, spectral flatness, fundamental freq, onset time)
"""

import numpy as np
from gymnasium import spaces
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
import tune as tu


# =============================================================================
# Motor Parameter Limits (from tune.py)
# =============================================================================

# Slider position limits (encoder ticks)
SLIDER_MIN = -60000
SLIDER_MAX = 60000

# Presser torque limits
TORQUE_MIN = tu.LH_PRESSER_UNPRESSED_POS  # -650 (unpressed)
TORQUE_MAX = tu.LH_PRESSER_PRESSED_POS    # 500 (full press)

# Picker position limits (encoder ticks, approximate)
PICKER_LIMITS = {
    0: {'min': 400, 'max': 900},   # E string picker
    1: {'min': 400, 'max': 1200},  # D string picker  
    2: {'min': 500, 'max': 1300},  # B string picker
}

# Fret limits
MAX_FRET = len(tu.SLIDER_MM_PER_FRET)  # 9 frets available

# Force scaling (0.0-1.0 maps to TORQUE_MIN-TORQUE_MAX)
FORCE_MIN = 0.0
FORCE_MAX = 1.0

# Audio feature ranges
AUDIO_RMS_MIN = -80.0  # dBFS
AUDIO_RMS_MAX = 0.0
AUDIO_FLATNESS_MIN = 0.0
AUDIO_FLATNESS_MAX = 1.0
AUDIO_FREQ_MIN = 80.0   # Hz (below low E)
AUDIO_FREQ_MAX = 1000.0  # Hz (above high frets)
AUDIO_ONSET_MIN = 0.0
AUDIO_ONSET_MAX = 0.5   # seconds


# =============================================================================
# Action Space Definitions
# =============================================================================

def create_discrete_action_space(num_strings=1):
    """
    Create discrete action space for fret/press/pluck control.
    
    For single string:
        - fret: 0-9 (10 positions)
        - press: 0=released, 1=pressed
        - pluck: 0=no pluck, 1=pluck
    
    Args:
        num_strings: Number of strings to control (1, 3, or 6)
        
    Returns:
        gymnasium.spaces.Dict with discrete action components
    """
    return spaces.Dict({
        'fret': spaces.MultiDiscrete([MAX_FRET + 1] * num_strings),  # Frets 0-9
        'press': spaces.MultiBinary(num_strings),
        'pluck': spaces.MultiBinary(min(num_strings, 3)),  # Max 3 pickers
    })


def create_continuous_action_space(num_strings=1):
    """
    Create continuous action space for delta-based control.
    
    For single string:
        - delta_slider: Change in slider position (encoder ticks)
        - delta_torque: Change in presser torque
        - pluck: 0=no pluck, 1=pluck (still discrete)
    
    Args:
        num_strings: Number of strings to control
        
    Returns:
        gymnasium.spaces.Dict with continuous action components
    """
    return spaces.Dict({
        'delta_slider': spaces.Box(
            low=-5000, high=5000, 
            shape=(num_strings,), dtype=np.float32
        ),
        'delta_torque': spaces.Box(
            low=-200, high=200,
            shape=(num_strings,), dtype=np.float32
        ),
        'pluck': spaces.MultiBinary(min(num_strings, 3)),
    })


def create_hybrid_action_space(num_strings=1):
    """
    Create hybrid action space: discrete fret + continuous force + discrete pluck.
    
    This is the recommended starting point for RL training:
        - fret: Discrete target fret (0-9)
        - force: Continuous force level (0.0-1.0)
        - pluck: Discrete pluck trigger
    
    Args:
        num_strings: Number of strings to control
        
    Returns:
        gymnasium.spaces.Dict with hybrid action components
    """
    return spaces.Dict({
        'fret': spaces.MultiDiscrete([MAX_FRET + 1] * num_strings),
        'force': spaces.Box(
            low=FORCE_MIN, high=FORCE_MAX,
            shape=(num_strings,), dtype=np.float32
        ),
        'pluck': spaces.MultiBinary(min(num_strings, 3)),
    })


# =============================================================================
# Observation Space Definitions
# =============================================================================

def create_observation_space(num_strings=1, include_audio=True):
    """
    Create observation space for GuitarBot state.
    
    Motor state:
        - slider_positions: Current slider encoder positions
        - presser_torques: Current presser torque values
        - picker_positions: Current picker encoder positions
    
    Semantic state:
        - fret_positions: Current fret number per string (derived)
        - pressed_state: Whether each string is pressed
        
    Audio features (optional):
        - peak_rms_db: Peak RMS energy in dB
        - spectral_flatness: 0=tonal, 1=noisy
        - fundamental_freq: Detected pitch in Hz
        - onset_time: Time to onset in seconds
    
    Args:
        num_strings: Number of strings being controlled
        include_audio: Whether to include audio features
        
    Returns:
        gymnasium.spaces.Dict with observation components
    """
    obs_dict = {
        # Motor positions (raw encoder values)
        'slider_positions': spaces.Box(
            low=SLIDER_MIN, high=SLIDER_MAX,
            shape=(num_strings,), dtype=np.float32
        ),
        'presser_torques': spaces.Box(
            low=TORQUE_MIN, high=TORQUE_MAX,
            shape=(num_strings,), dtype=np.float32
        ),
        'picker_positions': spaces.Box(
            low=0, high=1500,
            shape=(min(num_strings, 3),), dtype=np.float32
        ),
        
        # Semantic state (derived from motor positions)
        'fret_positions': spaces.MultiDiscrete([MAX_FRET + 1] * num_strings),
        'pressed_state': spaces.MultiBinary(num_strings),
        'picker_state': spaces.MultiBinary(min(num_strings, 3)),  # 0=down, 1=up
    }
    
    if include_audio:
        obs_dict.update({
            'peak_rms_db': spaces.Box(
                low=AUDIO_RMS_MIN, high=AUDIO_RMS_MAX,
                shape=(1,), dtype=np.float32
            ),
            'spectral_flatness': spaces.Box(
                low=AUDIO_FLATNESS_MIN, high=AUDIO_FLATNESS_MAX,
                shape=(1,), dtype=np.float32
            ),
            'fundamental_freq': spaces.Box(
                low=AUDIO_FREQ_MIN, high=AUDIO_FREQ_MAX,
                shape=(1,), dtype=np.float32
            ),
            'onset_time': spaces.Box(
                low=AUDIO_ONSET_MIN, high=AUDIO_ONSET_MAX,
                shape=(1,), dtype=np.float32
            ),
        })
    
    return spaces.Dict(obs_dict)


# =============================================================================
# Action Conversion Utilities
# =============================================================================

def force_to_torque(force_level):
    """
    Convert force level (0.0-1.0) to presser torque value.
    
    Args:
        force_level: Float 0.0 (no force) to 1.0 (max force)
        
    Returns:
        Torque value in range [TORQUE_MIN, TORQUE_MAX]
    """
    force_level = np.clip(force_level, FORCE_MIN, FORCE_MAX)
    # Map 0.0 -> -650 (unpressed), 1.0 -> 500 (full press)
    # Note: 0.0 means unpressed, not zero torque
    return TORQUE_MIN + force_level * (TORQUE_MAX - TORQUE_MIN)


def torque_to_force(torque):
    """
    Convert presser torque to force level (0.0-1.0).
    
    Args:
        torque: Torque value in range [TORQUE_MIN, TORQUE_MAX]
        
    Returns:
        Force level 0.0 (unpressed) to 1.0 (max force)
    """
    torque = np.clip(torque, TORQUE_MIN, TORQUE_MAX)
    return (torque - TORQUE_MIN) / (TORQUE_MAX - TORQUE_MIN)


def fret_to_slider_position(string_id, fret_num):
    """
    Convert fret number to slider encoder position.
    Uses the same formula as LeftHandParser.string_fret_to_slider_position()
    
    Args:
        string_id: String index (0-5)
        fret_num: Fret number (0=open, 1-9=frets)
        
    Returns:
        Slider position in encoder ticks
    """
    if fret_num == 0:
        return 0
    
    if fret_num > len(tu.SLIDER_MM_PER_FRET):
        fret_num = len(tu.SLIDER_MM_PER_FRET)
    
    fret_mm = tu.SLIDER_MM_PER_FRET[fret_num - 1]
    direction = tu.SLIDER_MOTOR_DIRECTION[string_id]
    
    position = ((fret_mm * 2048) / tu.MM_TO_ENCODER_CONVERSION_FACTOR + 
                tu.SLIDER_ENCODER_OFFSET) * direction
    
    return int(position)


def slider_position_to_fret(string_id, slider_position):
    """
    Convert slider encoder position to approximate fret number.
    Inverse of fret_to_slider_position().
    
    Args:
        string_id: String index (0-5)
        slider_position: Slider encoder position
        
    Returns:
        Approximate fret number (0-9)
    """
    if abs(slider_position) < 1000:  # Near open position
        return 0
    
    direction = tu.SLIDER_MOTOR_DIRECTION[string_id]
    
    # Reverse the formula
    pos_corrected = slider_position / direction
    fret_mm = ((pos_corrected - tu.SLIDER_ENCODER_OFFSET) * 
               tu.MM_TO_ENCODER_CONVERSION_FACTOR) / 2048
    
    # Find closest fret
    best_fret = 0
    min_diff = float('inf')
    for i, mm in enumerate(tu.SLIDER_MM_PER_FRET):
        diff = abs(mm - fret_mm)
        if diff < min_diff:
            min_diff = diff
            best_fret = i + 1
    
    return best_fret


def clip_action(action, action_space_type='hybrid'):
    """
    Clip action values to valid ranges.
    
    Args:
        action: Dict with action components
        action_space_type: 'discrete', 'continuous', or 'hybrid'
        
    Returns:
        Clipped action dict
    """
    clipped = {}
    
    if 'fret' in action:
        clipped['fret'] = np.clip(action['fret'], 0, MAX_FRET).astype(int)
    
    if 'force' in action:
        clipped['force'] = np.clip(action['force'], FORCE_MIN, FORCE_MAX)
    
    if 'delta_slider' in action:
        clipped['delta_slider'] = np.clip(action['delta_slider'], -5000, 5000)
    
    if 'delta_torque' in action:
        clipped['delta_torque'] = np.clip(action['delta_torque'], -200, 200)
    
    if 'press' in action:
        clipped['press'] = np.clip(action['press'], 0, 1).astype(int)
    
    if 'pluck' in action:
        clipped['pluck'] = np.clip(action['pluck'], 0, 1).astype(int)
    
    return clipped


# =============================================================================
# State Validation
# =============================================================================

def validate_motor_state(slider_positions, presser_torques, picker_positions):
    """
    Check if motor state is within safe limits.
    
    Args:
        slider_positions: Array of slider positions
        presser_torques: Array of presser torques
        picker_positions: Array of picker positions
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Check sliders
    for i, pos in enumerate(slider_positions):
        if pos < SLIDER_MIN or pos > SLIDER_MAX:
            errors.append(f"Slider {i} out of range: {pos}")
    
    # Check pressers
    for i, torque in enumerate(presser_torques):
        if torque < TORQUE_MIN or torque > TORQUE_MAX:
            errors.append(f"Presser {i} torque out of range: {torque}")
    
    # Check pickers
    for i, pos in enumerate(picker_positions):
        limits = PICKER_LIMITS.get(i, {'min': 0, 'max': 1500})
        if pos < limits['min'] or pos > limits['max']:
            errors.append(f"Picker {i} out of range: {pos}")
    
    return len(errors) == 0, errors


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=== GuitarBot RL Action Space Test ===\n")
    
    # Test discrete action space
    print("Discrete Action Space (single string):")
    discrete_space = create_discrete_action_space(num_strings=1)
    print(f"  {discrete_space}")
    print(f"  Sample: {discrete_space.sample()}\n")
    
    # Test continuous action space
    print("Continuous Action Space (single string):")
    continuous_space = create_continuous_action_space(num_strings=1)
    print(f"  {continuous_space}")
    print(f"  Sample: {continuous_space.sample()}\n")
    
    # Test hybrid action space
    print("Hybrid Action Space (single string):")
    hybrid_space = create_hybrid_action_space(num_strings=1)
    print(f"  {hybrid_space}")
    print(f"  Sample: {hybrid_space.sample()}\n")
    
    # Test observation space
    print("Observation Space (with audio):")
    obs_space = create_observation_space(num_strings=1, include_audio=True)
    print(f"  {obs_space}")
    print(f"  Sample: {obs_space.sample()}\n")
    
    # Test conversions
    print("Conversion Tests:")
    print(f"  force_to_torque(0.0) = {force_to_torque(0.0)}")
    print(f"  force_to_torque(0.5) = {force_to_torque(0.5)}")
    print(f"  force_to_torque(1.0) = {force_to_torque(1.0)}")
    print(f"  fret_to_slider_position(0, 5) = {fret_to_slider_position(0, 5)}")
    print(f"  slider_position_to_fret(0, -28284) = {slider_position_to_fret(0, -28284)}")
    
    print("\n=== Test Complete ===")
