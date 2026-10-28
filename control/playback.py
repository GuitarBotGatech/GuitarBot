"""Plan guitar arrangements and send trajectories to OpenCR.

Play path: UI JSON → notation Events → planner rows → plan → send.
"""

from __future__ import annotations

import socket
import threading
import time

import numpy as np

from tuning import tune as tu
from control.plan import GuitarBotParser
from notation.events import SongArrangement, load_config

UNPRESS_POINTS = 400
HOME_POINTS = 200
NUM_MOTORS = 18


def _robot_payloads(song_dict, config):
    """UI JSON → Events → pluck rows and mute actions for GuitarBotParser."""
    return SongArrangement.from_dict(song_dict, config=config).to_plan()


def build_reset_trajectory(current_position=None, target_position=None) -> np.ndarray:
    """Unpress pressers, then home sliders and pickers."""
    target = np.asarray(tu.initial_point if target_position is None else target_position, dtype=float)
    current = np.asarray(tu.initial_point if current_position is None else current_position, dtype=float)
    if current.size < target.size:
        current = np.concatenate([current, target[current.size :]])
    elif current.size > target.size:
        current = current[: target.size]

    num_motors = int(target.size)
    unpress_trajectory = np.zeros((UNPRESS_POINTS, num_motors))
    for motor in range(num_motors):
        q0 = current[motor]
        qf = tu.LH_PRESSER_UNPRESSED_POS if 6 <= motor <= 11 else q0
        unpress_trajectory[:, motor] = GuitarBotParser.interp_with_blend(q0, qf, UNPRESS_POINTS, tu.TRAJECTORY_BLEND_PERCENT)

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
    """Send a trajectory to OpenCR in timed UDP batches, without waiting for ACKs."""
    udp_ip = "10.2.1.177"
    udp_port = 8888
    batch_size = 20
    time_per_point_s = tu.TIME_STEP

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    num_total_points = len(traj)
    print(f"Starting song with {num_total_points} points.")
    print(f"Sending in batches of {batch_size} points every {batch_size * time_per_point_s:.2f} seconds.")

    total_start_time = time.time()
    for i in range(0, num_total_points, batch_size):
        start_time = time.time()
        chunk = traj[i : i + batch_size]
        byte_payload = chunk.astype(np.float32).tobytes()
        sock.sendto(byte_payload, (udp_ip, udp_port))

        num_points_in_chunk = len(chunk)
        print(f"Sent batch {i // batch_size + 1}: {num_points_in_chunk} points ({len(byte_payload)} bytes).")
        sleep_time = max(0, num_points_in_chunk * time_per_point_s - (time.time() - start_time))
        print(f"--> Sleeping for {sleep_time:.4f} seconds...\n")
        time.sleep(sleep_time)

    print(f"Total elapsed time: {time.time() - total_start_time:.4f} seconds")
    print("All batches sent. Song Complete.")


class PlaybackSession:
    """Parser + last motor pose shared across successive play/reset calls."""

    def __init__(self, initial_point=None, config=None) -> None:
        tu.graph = False
        start = list(tu.initial_point if initial_point is None else initial_point)
        self.parser = GuitarBotParser(initial_point=start, graph=False)
        self.last_position = np.asarray(start, dtype=float)
        self.config = load_config() if config is None else config
        self.busy_lock = threading.Lock()

    def try_acquire(self) -> bool:
        return self.busy_lock.acquire(blocking=False)

    def release(self) -> None:
        self.busy_lock.release()

    def plan_arrangement(self, song_dict, parser: GuitarBotParser | None = None) -> np.ndarray:
        tu.graph = False
        active_parser = parser if parser is not None else self.parser
        active_parser.graph = False
        plucks, mutes = _robot_payloads(song_dict, self.config)
        traj = active_parser.parseAll(plucks, mutes)
        if traj.size == 0:
            raise ValueError("planner returned an empty trajectory")
        if traj.ndim != 2 or traj.shape[1] != NUM_MOTORS:
            raise ValueError(f"planner returned unexpected trajectory shape {getattr(traj, 'shape', None)}")
        self.last_position = np.asarray(traj[-1, :], dtype=float).copy()
        active_parser.initial_point = self.last_position.tolist()
        return traj

    def play_arrangement(self, song_dict, *, send, parser: GuitarBotParser | None = None) -> np.ndarray:
        traj = self.plan_arrangement(song_dict, parser=parser)
        if send:
            send_trajectory(traj)
        return traj

    def reset(self, *, current_position: np.ndarray | list[float] | None = None, send: bool = True) -> np.ndarray:
        current = self.last_position if current_position is None else current_position
        traj = build_reset_trajectory(current_position=current)
        if send:
            send_trajectory(traj)
        target = np.asarray(tu.initial_point, dtype=float)
        self.last_position = target.copy()
        self.parser.initial_point = target.tolist()
        return traj


_default_session: PlaybackSession | None = None
_default_session_lock = threading.Lock()


def get_session() -> PlaybackSession:
    global _default_session
    with _default_session_lock:
        if _default_session is None:
            _default_session = PlaybackSession()
        return _default_session

def play_arrangement(song_dict, *, send, parser: GuitarBotParser | None = None, session: PlaybackSession | None = None) -> np.ndarray:
    active = session if session is not None else get_session()
    return active.play_arrangement(song_dict, send=send, parser=parser)

def reset(*, current_position=None, send=True, session: PlaybackSession | None = None) -> np.ndarray:
    active = session if session is not None else get_session()
    return active.reset(current_position=current_position, send=send)
