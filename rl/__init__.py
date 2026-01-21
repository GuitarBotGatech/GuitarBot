"""
GuitarBot Reinforcement Learning Module

This package provides a Gymnasium-compatible environment for training
reinforcement learning agents to control the GuitarBot musical robot.

Quick Start:
    from rl import GuitarBotEnv
    
    env = GuitarBotEnv(num_strings=1, mode='simulation')
    obs, info = env.reset()
    
    for _ in range(100):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)

Modules:
    - action_space: Action and observation space definitions
    - guitar_bot_env: Main Gymnasium environment
    - trajectory_generator: Low-level trajectory generation

Configuration:
    The environment supports three action space types:
    - 'discrete': Fret position (0-9), press (bool), pluck (bool)
    - 'continuous': Delta slider, delta torque, pluck trigger
    - 'hybrid': Discrete fret + continuous force + discrete pluck
    
    And three execution modes:
    - 'simulation': No hardware, instant state updates
    - 'hardware': Real robot execution with audio feedback
    - 'hybrid_sim': Simulated with physics-based audio model
"""

from rl.action_space import (
    create_discrete_action_space,
    create_continuous_action_space,
    create_hybrid_action_space,
    create_observation_space,
    force_to_torque,
    torque_to_force,
    fret_to_slider_position,
    slider_position_to_fret,
    clip_action,
    validate_motor_state,
)

from rl.guitar_bot_env import GuitarBotEnv, register_guitarbot_envs
from rl.trajectory_generator import TrajectoryGenerator

__all__ = [
    # Environment
    'GuitarBotEnv',
    'register_guitarbot_envs',
    
    # Action spaces
    'create_discrete_action_space',
    'create_continuous_action_space', 
    'create_hybrid_action_space',
    'create_observation_space',
    
    # Utilities
    'force_to_torque',
    'torque_to_force',
    'fret_to_slider_position',
    'slider_position_to_fret',
    'clip_action',
    'validate_motor_state',
    
    # Trajectory
    'TrajectoryGenerator',
]

__version__ = '0.1.0'
