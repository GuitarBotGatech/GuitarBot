"""
sequence_player.py – Timed MIDI effect sequence playback for GuitarBot songs.

Overview
--------
This module lets a song composer pre-define a sequence of MIDI events (e.g.
pedal / effects changes) where each event carries an **absolute timestamp**
in seconds.  The :class:`SequencePlayer` plays those events in real-time,
pre-firing each one by ``robot_delay`` seconds so the physical robot has
enough time to react before the MIDI effect is needed.

This file lives in the GuitarBot repo because it is GuitarBot-specific; it
relies on ``midification`` as a library dependency for the OSC→MIDI translation
pipeline (``OSCMIDIMapper``, ``MIDIOutput``, ``BridgeConfig``).

Message format
--------------
Each OSC message in the sequence has the **timestamp as its last argument**::

    /cc   <ctrl>  <value>  [<interp_flag>]  <timestamp_s>
    /note <note>  <velocity> [<interp_flag>]  <timestamp_s>

The optional ``interp_flag`` is an **OSC integer** (type tag ``i``).
When set to ``1`` the receiver will linearly interpolate from this
message to the next message sharing the same address and key parameter
(e.g. same CC controller), inserting steps at
:data:`tune.MIDI_INTERPOLATION_INTERVAL_S` (default 5 ms).

Examples::

    /cc    7   30   0.00    # CC #7 =  30 at t = 0.0 s  (no interp)
    /cc    7   30  1 0.00   # CC #7 =  30 at t = 0.0 s, interpolate to next
    /cc    7  127  0 5.00   # CC #7 = 127 at t = 5.0 s  (step target)
    /note 60  100   5.00    # note_on note=60 vel=100 at t = 5.0 s

Typical usage
-------------
::

    from sequence_player import SequencePlayer
    from midification.config import BridgeConfig

    config = BridgeConfig.from_yaml("my_config.yaml")

    with SequencePlayer.from_config(config, robot_delay=0.05) as player:
        player.load_raw([
            ("/cc",   (7, 100,  0.00)),
            ("/cc",   (7,  64,  2.50)),
            ("/note", (60, 100, 5.00)),
        ])
        player.play()           # blocks until all messages sent

    # ── Non-blocking, synchronised to a GuitarBot song start ───────────
    t0 = time.monotonic()               # capture the moment the song starts
    osc_client.send_message("/Pluck", pluck_message)   # send robot moves
    player.play_async(start_time=t0)    # fire MIDI in sync on a bg thread

Robot delay
-----------
``robot_delay`` (default 50 ms) subtracts a fixed offset from every
scheduled fire time::

    fire_at = t0 + message.timestamp - robot_delay

A MIDI CC with ``timestamp=2.500`` and ``robot_delay=0.05`` is therefore
sent at ``t0 + 2.450``, giving the effects unit 50 ms of lead time before
the robot's striker physically hits the string at ``t0 + 2.500``.

Tune ``robot_delay`` to match your specific pedal + robot latency.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

import tune as tu

from midification.config import BridgeConfig
from midification.mapper import OSCMIDIMapper
from midification.midi_output import MIDIOutput

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(order=True)
class TimedMessage:
    """A single OSC→MIDI event with an absolute song timestamp."""

    timestamp: float
    """Seconds from song start at which this MIDI event should sound."""

    address: str = field(compare=False)
    """OSC address string, e.g. ``/cc``."""

    args: tuple[Any, ...] = field(compare=False)
    """OSC arguments **without** the trailing timestamp."""

    interpolate: bool = field(default=False, compare=False)
    """
    When ``True`` the player will linearly interpolate from this
    message to the next message with the same address and key
    parameter (see :func:`expand_interpolated`).

    Set by passing an OSC **integer** flag (type tag ``i``) as the
    second-to-last argument in the wire format::

        /cc ctrl value  i:1  timestamp   # interpolate=True
        /cc ctrl value  i:0  timestamp   # interpolate=False
    """

    # ------------------------------------------------------------------ #
    # Construction helpers                                                 #
    # ------------------------------------------------------------------ #

    @classmethod
    def from_osc_args(cls, address: str, args: Sequence[Any]) -> "TimedMessage":
        """
        Parse a timestamped OSC message into a :class:`TimedMessage`.

        The **last** element of *args* is consumed as the timestamp; all
        preceding elements become the payload passed to the MIDI mapper.

        Parameters
        ----------
        address:
            OSC address string, e.g. ``/cc``.
        args:
            Full OSC argument list **including** the trailing timestamp float.

        Raises
        ------
        ValueError
            If *args* is empty or its last element is not numeric.
        """
        if not args:
            raise ValueError(
                f"OSC message {address!r} has no arguments "
                "(expected at least a trailing timestamp)."
            )
        try:
            timestamp = float(args[-1])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Last argument of {address!r} must be numeric (timestamp); "
                f"got {args[-1]!r}"
            ) from exc

        # Detect an optional interpolation flag immediately before the
        # timestamp.  To avoid ambiguity with regular integer payload values
        # (e.g. /cc value=100), only treat it as a flag when the message has
        # at least two payload args + flag + timestamp, and the candidate is
        # exactly 0 or 1.
        if len(args) >= 4 and isinstance(args[-2], int) and args[-2] in (0, 1):
            interpolate = bool(args[-2])
            payload = tuple(args[:-2])
        else:
            interpolate = False
            payload = tuple(args[:-1])

        return cls(
            timestamp=timestamp,
            address=address,
            args=payload,
            interpolate=interpolate,
        )

    def __repr__(self) -> str:
        interp = " [interp]" if self.interpolate else ""
        return (
            f"TimedMessage(t={self.timestamp:.3f}s, "
            f"address={self.address!r}, args={self.args!r}{interp})"
        )




# ─────────────────────────────────────────────────────────────────────────────
# Interpolation expansion
# ─────────────────────────────────────────────────────────────────────────────


def expand_interpolated(
    messages: list[TimedMessage],
    interval_s: float,
) -> list[TimedMessage]:
    """
    Expand a message sequence by inserting linearly-interpolated steps
    wherever a :class:`TimedMessage` has ``interpolate=True``.

    For each such message *M*, the function finds the **next** message that
    shares the same *key* (address + first arg, e.g. same CC controller).
    It then generates intermediate messages spaced *interval_s* apart between
    *M*.timestamp and the next message's timestamp, linearly interpolating
    the **value** (last arg).

    Key rule
    --------
    * Messages with ≥ 2 args: key = ``(address, args[0])`` – e.g. same channel + controller
    * Messages with 1 arg:    key = ``(address,)``           – e.g. pitch-wheel

    Parameters
    ----------
    messages:
        Sorted list of :class:`TimedMessage` objects.
    interval_s:
        Step size in seconds between generated intermediate messages.
        Sourced from :data:`tune.MIDI_INTERPOLATION_INTERVAL_S`.

    Returns
    -------
    list[TimedMessage]
        New sorted list that includes every original message plus the
        generated interpolation steps.  Original messages are preserved
        unchanged; generated messages have ``interpolate=False``.
    """
    if not messages:
        return list(messages)

    def _key(msg: TimedMessage) -> tuple:
        if len(msg.args) >= 2:
            return (msg.address, msg.args[0])
        return (msg.address,)

    result: list[TimedMessage] = list(messages)

    for i, msg in enumerate(messages):
        if not msg.interpolate:
            continue

        k = _key(msg)
        next_msg: TimedMessage | None = None
        for j in range(i + 1, len(messages)):
            if _key(messages[j]) == k:
                next_msg = messages[j]
                break

        if next_msg is None:
            logger.warning(
                "TimedMessage %r has interpolate=True but no following message "
                "with key %r was found; flag ignored.", msg, k
            )
            continue

        t_start = msg.timestamp
        t_end = next_msg.timestamp
        dt = t_end - t_start

        if dt <= interval_s:
            continue  # endpoints are already within one step

        v_start = float(msg.args[-1])
        v_end = float(next_msg.args[-1])
        prefix_args = msg.args[:-1]  # everything except the interpolated value

        t = t_start + interval_s
        while t < t_end - interval_s / 2:
            alpha = (t - t_start) / dt
            value = v_start + alpha * (v_end - v_start)
            result.append(TimedMessage(
                timestamp=t,
                address=msg.address,
                args=prefix_args + (value,),
                interpolate=False,
            ))
            t += interval_s

    result.sort()
    return result

# ─────────────────────────────────────────────────────────────────────────────
# Player
# ─────────────────────────────────────────────────────────────────────────────


class SequencePlayer:
    """
    Plays a list of :class:`TimedMessage` objects as MIDI, synchronised to a
    GuitarBot song start time and pre-compensating for physical robot latency.

    Parameters
    ----------
    mapper:
        :class:`~midification.mapper.OSCMIDIMapper` used to translate OSC
        address + args into ``mido.Message`` objects.
    midi_output:
        A :class:`~midification.midi_output.MIDIOutput` instance.  The player
        opens and closes the port via :meth:`open` / :meth:`close`.
    robot_delay:
        Seconds to subtract from each message's timestamp so MIDI is sent
        *before* the intended musical moment, giving the physical robot time
        to reach its target.  Defaults to :attr:`DEFAULT_ROBOT_DELAY` (50 ms).
    """

    DEFAULT_ROBOT_DELAY: float = 0.05
    """Default pre-fire offset in seconds (50 ms)."""

    def __init__(
        self,
        mapper: OSCMIDIMapper,
        midi_output: MIDIOutput,
        robot_delay: float = DEFAULT_ROBOT_DELAY,
    ) -> None:
        if robot_delay < 0:
            raise ValueError(f"robot_delay must be >= 0, got {robot_delay!r}")

        self._mapper = mapper
        self._midi = midi_output
        self._robot_delay = robot_delay
        self._sequence: list[TimedMessage] = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------ #
    # Alternate constructors                                               #
    # ------------------------------------------------------------------ #

    @classmethod
    def from_config(
        cls,
        config: BridgeConfig,
        robot_delay: float = DEFAULT_ROBOT_DELAY,
        dry_run: bool = False,
    ) -> "SequencePlayer":
        """
        Build a :class:`SequencePlayer` from an existing
        :class:`~midification.config.BridgeConfig`.

        The mapper is initialised from ``config.mappings``; the MIDI output
        uses ``config.midi``.
        """
        mapper = OSCMIDIMapper(config.mappings)
        midi = MIDIOutput(
            port_name=config.midi.port_name,
            virtual=config.midi.virtual,
            dry_run=dry_run,
        )
        return cls(mapper=mapper, midi_output=midi, robot_delay=robot_delay)

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def open(self) -> "SequencePlayer":
        """Open the MIDI output port.  Returns *self* for chaining."""
        self._midi.open()
        logger.info(
            "SequencePlayer ready – robot_delay=%.3f s, %d messages loaded.",
            self._robot_delay,
            len(self._sequence),
        )
        return self

    def close(self) -> None:
        """Stop playback if running and close the MIDI port."""
        self.stop()
        self._midi.close()

    def __enter__(self) -> "SequencePlayer":
        return self.open()

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Sequence loading                                                     #
    # ------------------------------------------------------------------ #

    def load(self, messages: Sequence[TimedMessage]) -> None:
        """
        Replace the current sequence with *messages*, sorted by timestamp.

        Any :class:`TimedMessage` with ``interpolate=True`` is automatically
        expanded into a dense sequence of linearly-interpolated steps via
        :func:`expand_interpolated`, using the step size defined by
        :data:`tune.MIDI_INTERPOLATION_INTERVAL_S`.

        Safe to call between (or before) plays.
        """
        sorted_msgs = sorted(messages)
        self._sequence = expand_interpolated(
            sorted_msgs, tu.MIDI_INTERPOLATION_INTERVAL_S
        )
        logger.debug(
            "Loaded %d timed messages (%d after interpolation expansion).",
            len(sorted_msgs), len(self._sequence),
        )

    def load_raw(self, raw: Sequence[tuple[str, Sequence[Any]]]) -> None:
        """
        Build the sequence from raw ``(address, args_with_timestamp)`` pairs.

        The **last** element of each ``args`` list/tuple must be the event's
        timestamp in seconds.

        Parameters
        ----------
        raw:
            Iterable of ``(osc_address, args)`` tuples, e.g.::

                [
                    ("/cc",    (7, 100, 0.00)),
                    ("/cc",    (7,  64, 2.50)),
                    ("/note",  (60, 100, 5.00)),
                ]
        """
        messages = [TimedMessage.from_osc_args(addr, args) for addr, args in raw]
        self.load(messages)

    # ------------------------------------------------------------------ #
    # Playback                                                             #
    # ------------------------------------------------------------------ #

    def play(self, start_time: float | None = None) -> None:
        """
        Play the sequence, **blocking** until all messages have been sent or
        :meth:`stop` is called.

        Parameters
        ----------
        start_time:
            ``time.monotonic()`` value representing ``t = 0`` for this
            sequence.  Defaults to *now* if not supplied.

            Pass the same ``start_time`` used to fire the GuitarBot
            ``/Pluck`` or ``/Chords`` OSC message so both are synchronised::

                t0 = time.monotonic()
                osc_client.send_message("/Pluck", pluck_data)
                player.play(start_time=t0)   # fires MIDI in sync
        """
        if not self._sequence:
            logger.warning("SequencePlayer.play() called with an empty sequence.")
            return

        t0 = start_time if start_time is not None else time.monotonic()
        self._stop_event.clear()

        logger.info(
            "SequencePlayer starting: %d messages, robot_delay=%.3f s.",
            len(self._sequence),
            self._robot_delay,
        )

        sent = 0
        for msg in self._sequence:
            if self._stop_event.is_set():
                logger.info(
                    "SequencePlayer: stopped after %d/%d messages.",
                    sent, len(self._sequence),
                )
                break

            # Pre-fire by robot_delay so the effects unit has lead time.
            fire_at = t0 + msg.timestamp - self._robot_delay
            wait = fire_at - time.monotonic()

            if wait > 0:
                # Sleep interruptibly so stop() is responsive.
                interrupted = self._stop_event.wait(timeout=wait)
                if interrupted:
                    logger.info(
                        "SequencePlayer: stopped after %d/%d messages.",
                        sent, len(self._sequence),
                    )
                    break
            elif wait < -0.1:
                # More than 100 ms late – warn but still send.
                logger.warning(
                    "Message %r (t=%.3f s) fired %.3f s late "
                    "(robot_delay=%.3f s – consider reducing sequence offset).",
                    msg.address, msg.timestamp, -wait, self._robot_delay,
                )

            midi_msg = self._mapper.translate(msg.address, msg.args)
            if midi_msg is not None:
                self._midi.send(midi_msg)
                sent += 1
                logger.debug(
                    "t=%.3f s → %s %s → %s",
                    msg.timestamp, msg.address, msg.args, midi_msg,
                )

        logger.info(
            "SequencePlayer finished: %d/%d messages sent.", sent, len(self._sequence)
        )

    def play_async(self, start_time: float | None = None) -> threading.Thread:
        """
        Start playback in a background daemon thread and return immediately.

        Parameters
        ----------
        start_time:
            Same semantics as :meth:`play`.  Capture ``time.monotonic()``
            **before** sending the GuitarBot OSC message and pass the same
            value here so both are on the same clock::

                t0 = time.monotonic()
                osc_client.send_message("/Pluck", pluck_data)
                player.play_async(start_time=t0)

        Returns
        -------
        threading.Thread
            The background thread (daemon).  Join it to wait for completion
            or call :meth:`stop` to cancel early.

        Raises
        ------
        RuntimeError
            If the player is already running.
        """
        if self.is_playing:
            raise RuntimeError("SequencePlayer is already playing.")

        t0 = start_time if start_time is not None else time.monotonic()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self.play,
            kwargs={"start_time": t0},
            name="sequence-player",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "SequencePlayer async started: %d messages, robot_delay=%.3f s.",
            len(self._sequence),
            self._robot_delay,
        )
        return self._thread

    def stop(self) -> None:
        """Cancel playback started with :meth:`play_async`."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("SequencePlayer stopped.")

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def robot_delay(self) -> float:
        """Pre-fire offset in seconds used to compensate for robot latency."""
        return self._robot_delay

    @property
    def is_playing(self) -> bool:
        """``True`` while an async playback thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def sequence(self) -> list[TimedMessage]:
        """A copy of the currently loaded :class:`TimedMessage` list."""
        return list(self._sequence)

    def __repr__(self) -> str:
        state = "playing" if self.is_playing else "idle"
        return (
            f"<SequencePlayer {state} messages={len(self._sequence)} "
            f"robot_delay={self._robot_delay:.3f}s>"
        )
