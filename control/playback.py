"""Plan guitar arrangements and send trajectories to OpenCR.

Play path: UI JSON → notation Events → planner rows → plan → send.
"""

from __future__ import annotations

import threading
from typing import Any

import numpy as np

from tuning import tune as tu
from control import send
from control.plan import GuitarBotParser
from notation.events import SongArrangement

UNPRESS_POINTS = 400
HOME_POINTS = 200
NUM_MOTORS = 18


def _robot_payloads(
    song_dict: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> tuple[list[list[Any]], list[list[Any]]]:
    """UI JSON → Events → (chords, pluck) rows for GuitarBotParser."""
    return SongArrangement.from_dict(song_dict, config=config).to_planner_rows()


def build_reset_trajectory(
    current_position: np.ndarray | list[float] | None = None,
    target_position: np.ndarray | list[float] | None = None,
) -> np.ndarray:
    """Unpress pressers, then home sliders and pickers."""
    target = np.asarray(
        tu.initial_point if target_position is None else target_position,
        dtype=float,
    )
    current = np.asarray(
        tu.initial_point if current_position is None else current_position,
        dtype=float,
    )
    if current.size < target.size:
        current = np.concatenate([current, target[current.size :]])
    elif current.size > target.size:
        current = current[: target.size]

    num_motors = int(target.size)
    unpress_trajectory = np.zeros((UNPRESS_POINTS, num_motors))
    for motor in range(num_motors):
        q0 = current[motor]
        qf = tu.LH_PRESSER_UNPRESSED_POS if 6 <= motor <= 11 else q0
        unpress_trajectory[:, motor] = GuitarBotParser.interp_with_blend(
            q0, qf, UNPRESS_POINTS, tu.TRAJECTORY_BLEND_PERCENT
        )

    home_trajectory = np.zeros((HOME_POINTS, num_motors))
    phase1_end = unpress_trajectory[-1, :]
    for motor in range(num_motors):
        home_trajectory[:, motor] = GuitarBotParser.interp_with_blend(
            phase1_end[motor],
            target[motor],
            HOME_POINTS,
            tu.TRAJECTORY_BLEND_PERCENT,
        )
    return np.vstack([unpress_trajectory, home_trajectory])


def send_trajectory(traj: np.ndarray) -> None:
    send.main(traj)


class PlaybackSession:
    """Parser + last motor pose shared across successive play/reset calls."""

    def __init__(
        self,
        initial_point: list[float] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        tu.graph = False
        start = list(tu.initial_point if initial_point is None else initial_point)
        self.parser = GuitarBotParser(initial_point=start, graph=False)
        self.last_position = np.asarray(start, dtype=float)
        self.config = config
        self.busy_lock = threading.Lock()

    def try_acquire(self) -> bool:
        return self.busy_lock.acquire(blocking=False)

    def release(self) -> None:
        self.busy_lock.release()

    def plan_arrangement(
        self,
        song_dict: dict[str, Any],
        parser: GuitarBotParser | None = None,
    ) -> np.ndarray:
        tu.graph = False
        active_parser = parser if parser is not None else self.parser
        active_parser.graph = False
        chords, pluck = _robot_payloads(song_dict, self.config)
        traj = active_parser.parseAllMIDI(chords, pluck, midi_events=None)
        if traj.size == 0:
            raise ValueError("planner returned an empty trajectory")
        if traj.ndim != 2 or traj.shape[1] != NUM_MOTORS:
            raise ValueError(
                f"planner returned unexpected trajectory shape {getattr(traj, 'shape', None)}"
            )
        self.last_position = np.asarray(traj[-1, :], dtype=float).copy()
        active_parser.initial_point = self.last_position.tolist()
        return traj

    def play_arrangement(
        self,
        song_dict: dict[str, Any],
        *,
        send: bool = True,
        parser: GuitarBotParser | None = None,
    ) -> np.ndarray:
        traj = self.plan_arrangement(song_dict, parser=parser)
        if send:
            send_trajectory(traj)
        return traj

    def reset(
        self,
        *,
        current_position: np.ndarray | list[float] | None = None,
        send: bool = True,
    ) -> np.ndarray:
        current = self.last_position if current_position is None else current_position
        traj = build_reset_trajectory(current_position=current)
        if send:
            send_trajectory(traj)
        target = np.asarray(tu.initial_point, dtype=float)
        self.last_position = target.copy()
        self.parser.initial_point = target.tolist()
        self.parser.current_fret_positions = [0, 0, 0, 0, 0, 0]
        return traj


_default_session: PlaybackSession | None = None
_default_session_lock = threading.Lock()


def get_session() -> PlaybackSession:
    global _default_session
    with _default_session_lock:
        if _default_session is None:
            _default_session = PlaybackSession()
        return _default_session


def play_arrangement(
    song_dict: dict[str, Any],
    *,
    send: bool = True,
    parser: GuitarBotParser | None = None,
    session: PlaybackSession | None = None,
) -> np.ndarray:
    active = session if session is not None else get_session()
    return active.play_arrangement(song_dict, send=send, parser=parser)


def reset(
    *,
    current_position: np.ndarray | list[float] | None = None,
    send: bool = True,
    session: PlaybackSession | None = None,
) -> np.ndarray:
    active = session if session is not None else get_session()
    return active.reset(current_position=current_position, send=send)
