"""One thing done to one string, and the motor points that thing produces."""

import math
import numpy as np
from tuning import tune as tu

# Slider command written into a left-hand event when the motion is a mute.
# -1 already means "leave the slider and lift the presser".
SLIDER_MUTE = -2

# Slider encoder counts per revolution.
_SLIDER_RESOLUTION = 2048


def fret_to_encoder(string, fret):
    """Slider target for a fret. Fret 0 and a mute leave the slider put, encoded as -1."""
    if fret <= 0:
        return -1
    direction = tu.SLIDER_MOTOR_DIRECTION[string]
    mm = tu.SLIDER_MM_PER_FRET[fret - 1]
    return ((mm * _SLIDER_RESOLUTION) / tu.MM_TO_ENCODER_CONVERSION_FACTOR + tu.SLIDER_ENCODER_OFFSET) * direction


def tremolo_pick_count(duration, speed):
    fill_points = fill_points = min(30, int(30 - (speed - 1) * (25 / 9))) - 4
    single_pick_duration = (fill_points * tu.TIME_STEP) + (tu.PICKER_PLUCK_MOTION_POINTS * tu.TIME_STEP)
    return max(0, math.floor(duration / single_pick_duration))


def _slider_targets(position, q0_slider):
    """Presser and slider endpoints for one left-hand event. Matches the note loop."""
    qf_slider = int(position)
    qf1_presser = tu.LH_PRESSER_UNPRESSED_POS
    qf2_presser = tu.LH_PRESSER_PRESSED_POS
    if int(position) == -1:
        qf_slider, qf2_presser = q0_slider, tu.LH_PRESSER_UNPRESSED_POS
    if int(position) == int(round(q0_slider)) and int(position) != -1:
        qf_slider, qf1_presser = q0_slider, tu.LH_PRESSER_PRESSED_POS
    return qf_slider, qf1_presser, qf2_presser


def _hand_points(q0_slider, q0_presser, qf_slider, qf1_presser, qf2_presser, slide, same_as_prev, prep_time_s, blend, tb_cent):
    total_points = max(3, int(round(float(prep_time_s) / float(tu.TIME_STEP))))
    base, remainder = divmod(total_points, 3)
    phase1_points = phase2_points = base
    phase3_points = base + remainder
    slider_points, presser_points = [], []

    if not same_as_prev:
        if slide:
            s1 = blend(q0_slider, q0_slider, phase1_points, tb_cent)
            p1 = blend(q0_presser, tu.LH_PRESSER_SLIDE_PRESS_POS, phase1_points, tb_cent)
            slider_points.extend(s1)
            presser_points.extend(p1)

            s2 = blend(q0_slider, qf_slider, phase2_points, tb_cent)
            p2 = blend(tu.LH_PRESSER_SLIDE_PRESS_POS, tu.LH_PRESSER_SLIDE_PRESS_POS, phase2_points, tb_cent)
            slider_points.extend(s2)
            presser_points.extend(p2)

            s3 = blend(qf_slider, qf_slider, phase3_points, tb_cent)
            p3 = blend(tu.LH_PRESSER_SLIDE_PRESS_POS, qf2_presser, phase3_points, tb_cent)
            slider_points.extend(s3)
            presser_points.extend(p3)
        else:
            s1 = blend(q0_slider, q0_slider, phase1_points, tb_cent)
            p1 = blend(q0_presser, qf1_presser, phase1_points, tb_cent)
            slider_points.extend(s1)
            presser_points.extend(p1)

            s2 = blend(q0_slider, qf_slider, phase2_points, tb_cent)
            p2 = blend(qf1_presser, qf1_presser, phase2_points, tb_cent)
            slider_points.extend(s2)
            presser_points.extend(p2)

            s3 = blend(qf_slider, qf_slider, phase3_points, tb_cent)
            p3 = blend(qf1_presser, qf2_presser, phase3_points, tb_cent)
            slider_points.extend(s3)
            presser_points.extend(p3)
    else:
        total_points = max(phase1_points + phase2_points + phase3_points, 1)
        s3 = blend(q0_slider, qf_slider, total_points, tb_cent)
        p3 = blend(q0_presser, qf2_presser, total_points, tb_cent)
        slider_points.extend(s3)
        presser_points.extend(p3)

    return slider_points, presser_points


class _Motion:
    def __eq__(self, other):
        return type(other) is type(self) and vars(self) == vars(other)


class Fret(_Motion):
    """Move the slider to `fret` and press. Occupies the string for `prep` seconds before the note."""

    def __init__(self, string, start, fret, prep, slide):
        self.string = string
        self.start = start
        self.fret = fret
        self.prep = prep
        self.slide = slide

    def render(self, q0_slider, q0_presser, *, same_as_prev, blend, tb_cent):
        qf_slider, qf1_presser, qf2_presser = _slider_targets(
            fret_to_encoder(self.string, self.fret), q0_slider
        )
        return _hand_points(
            q0_slider, q0_presser, qf_slider, qf1_presser, qf2_presser,
            self.slide, same_as_prev, self.prep, blend, tb_cent,
        )


class Release(_Motion):
    """Lift the presser and leave the slider where it is. This is an open string, or the lift after the song."""

    def __init__(self, string, start, prep, slide=False):
        self.string = string
        self.start = start
        self.prep = prep
        self.slide = slide

    def render(self, q0_slider, q0_presser, *, same_as_prev, blend, tb_cent):
        qf_slider, qf1_presser, qf2_presser = _slider_targets(-1, q0_slider)
        return _hand_points(
            q0_slider, q0_presser, qf_slider, qf1_presser, qf2_presser,
            self.slide, same_as_prev, self.prep, blend, tb_cent,
        )


class Mute(_Motion):
    """Damp the string with the presser. The slider stays where it is, so a mute can happen at any fret."""

    def __init__(self, string, start, prep):
        self.string = string
        self.start = start
        self.prep = prep

    @property
    def presser_pos(self):
        return tu.LH_PRESSER_MUTE_POS

    def render(self, q0_slider, q0_presser, *, same_as_prev, blend, tb_cent):
        return _hand_points(
            q0_slider, q0_presser, q0_slider, tu.LH_PRESSER_UNPRESSED_POS, self.presser_pos,
            False, same_as_prev, self.prep, blend, tb_cent,
        )


class Pluck(_Motion):
    def __init__(self, string, start):
        self.string = string
        self.start = start

    def render(self, start_pos, dest_pos, blend, tb_cent):
        return blend(start_pos, float(dest_pos), tu.PICKER_PLUCK_MOTION_POINTS, tb_cent)


class Tremolo(_Motion):
    """Repeated picker strokes over `duration` seconds."""

    def __init__(self, string, start, duration, speed):
        self.string = string
        self.start = start
        self.duration = duration
        self.speed = speed

    def render(self, start_pos, down_enc, up_enc, blend, tb_cent=tu.TRAJECTORY_BLEND_PERCENT):
        tremolo_points = []
        fill_points = min(30, int(30 - (self.speed - 1) * (25 / 9))) - 4
        current_pick_pos = start_pos
        for _ in range(tremolo_pick_count(self.duration, self.speed)):
            dest_pos = (
                down_enc
                if abs(current_pick_pos - up_enc) < abs(current_pick_pos - down_enc)
                else up_enc
            )
            points1 = blend(current_pick_pos, dest_pos, tu.PICKER_PLUCK_MOTION_POINTS, tb_cent)
            points2 = np.full(fill_points, dest_pos)
            tremolo_points.extend(points1)
            tremolo_points.extend(points2)
            current_pick_pos = dest_pos
        if not tremolo_points:
            return np.array([])
        return np.array(tremolo_points)


def actions_for(string, fret, pluck_time, *, slide=False, duration=0.0, speed=1.0):
    """Hand motion for this fret, then the picker stroke. A muted string is not plucked."""
    prep = float(tu.LH_PREP_TIME_BEFORE_PICK)
    start = float(pluck_time) - prep
    if fret < 0:
        return [Mute(string, start, prep)]
    if fret == 0:
        hand = Release(string, start, prep, slide)
    else:
        hand = Fret(string, start, fret, prep, slide)
    if duration >= tu.TREMOLO_DURATION_THRESHOLD:
        sound = Tremolo(string, float(pluck_time), float(duration), float(speed))
    else:
        sound = Pluck(string, float(pluck_time))
    return [hand, sound]


def action_for_lh_event(string, position, start, prep, slide):
    """The hand action for one left-hand event. Slider target -1 is a release."""
    string = int(string)
    if int(position) == SLIDER_MUTE:
        return Mute(string, start, prep)
    if int(position) == -1:
        return Release(string, start, prep, slide)

    low, high = tu.STRING_MIDI_RANGES[string]
    for fret in range(1, high - low + 1):
        if fret_to_encoder(string, fret) == position:
            return Fret(string, start, fret, prep, slide)

    raise ValueError(f"No fret on string {string} for slider target {position}")
