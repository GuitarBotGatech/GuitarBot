import numpy as np
import pandas as pd
from tuning import tune as tu
from control.actions import (SLIDER_MUTE, Pluck, Tremolo, action_for_lh_event, actions_for, fret_to_encoder, tremolo_pick_count)
from control.path_planner import assign
from notation.events import load_config
from control.debug import plan_viz


class GuitarBotParser:
    def __init__(self, initial_point, graph=tu.graph):
        self.initial_point = initial_point
        self.graph = graph

    def parseAll(self, pluck, mutes=None):
        """
        Build a complete motor trajectory from planner pluck rows.

        Args:
            pluck: Rows from ``SongArrangement.to_plan()``
                (``[note, duration, speed, slide, timestamp]`` or with
                ``string_index`` inserted before timestamp).
            mutes: ``Mute`` actions for strings a chord damps. A mute is
                written only when that finger is not already playing a note.
        """
        # 1. Assign every pluck to a string
        picker_motor_positions, slide_toggles = self.parsePlucks(pluck)
        if self.graph:
            plan_viz.log_slide_toggles(slide_toggles)

        # 2. Interpolate (RH first — also emits the LH prep event for each pluck)
        pick_array, lh_pick_pos = self.interpPick(picker_motor_positions, slide_toggles, self.initial_point)

        # Lift every presser a second after the last note so no finger holds torque after the song.
        song_end = max((timestamp + event[3] for event, timestamp in picker_motor_positions), default=0.0)
        prep_time = float(tu.LH_PREP_TIME_BEFORE_PICK)
        release_start = song_end + 1.0 - prep_time
        lh_pick_pos += [[string, -1, 0, release_start, prep_time] for string in range(len(tu.STRING_MIDI_RANGES))]

        lh_array = self.lh_interpolate(lh_pick_pos, self.initial_point, mutes=mutes)

        # 3. Combine and Finalize Trajectory
        num_lh_rows = lh_array.shape[0]
        num_pick_rows = pick_array.shape[0]
        max_rows = max(num_lh_rows, num_pick_rows)

        # Resize arrays to match the longest one, filling with the last valid value
        if num_lh_rows < max_rows:
            last_row = lh_array[-1, :]
            padding = np.tile(last_row, (max_rows - num_lh_rows, 1))
            lh_array = np.vstack([lh_array, padding])

        if num_pick_rows < max_rows:
            last_row = pick_array[-1, :]
            padding = np.tile(last_row, (max_rows - num_pick_rows, 1))
            pick_array = np.vstack([pick_array, padding])

        # Combine into a single trajectory array
        combined_array = np.hstack([lh_array, pick_array])

        # Update the initial_point for the next segment of music
        if combined_array.size > 0:
            self.initial_point = combined_array[-1, :].tolist()

        if self.graph:
            plan_viz.log_matrix_shape(combined_array.shape)
            plan_viz.show_motor_trajectory(combined_array)

        return combined_array

    @staticmethod
    def interp_with_blend(q0, qf, N, tb_cent):
        if N <= 1:
            return np.array([qf], dtype=int) if N == 1 else np.array([], dtype=int)

        curve = np.zeros(N)
        nb = int(tb_cent * N)
        if nb == 0:
            return np.linspace(q0, qf, N).astype(int)

        a_2 = 0.5 * (qf - q0) / (nb * (N - nb))
        for i in range(nb):
            tmp = a_2 * (i ** 2)
            curve[i] = q0 + tmp
            curve[N - i - 1] = qf - tmp

        tmp = a_2 * (nb ** 2)
        qa = q0 + tmp
        qb = qf - tmp

        if N - (2 * nb) > 0:
            curve[nb:N - nb] = np.linspace(qa, qb, N - (2 * nb))

        return curve.astype(int)

    def lh_interpolate(self, lh_pick_pos, initial_point, tb_cent=tu.TRAJECTORY_BLEND_PERCENT, mutes=None):

        motor_available_time = {i: 0.0 for i in range(6)}

        def unpack_lh_pick_event(raw_event):
            motor_id = int(raw_event[0])
            position = raw_event[1]
            slide_toggle = raw_event[2]
            timestamp = float(raw_event[3])
            prep_time = (
                float(raw_event[4])
                if len(raw_event) >= 5
                else float(tu.LH_PREP_TIME_BEFORE_PICK)
            )
            prep_time = max(float(tu.TIME_STEP), prep_time)
            return motor_id, position, slide_toggle, timestamp, prep_time

        filtered_lh_pick_pos = []
        for raw_event in sorted(lh_pick_pos, key=lambda event: float(event[3])):
            motor_id, position, slide_toggle, timestamp, prep_time = unpack_lh_pick_event(raw_event)
            # Check if the motor is available at the required start time
            if timestamp >= motor_available_time.get(motor_id, 0.0):
                filtered_lh_pick_pos.append([motor_id, position, slide_toggle, timestamp, prep_time])

                # Update the time this motor will next be available
                motor_available_time[motor_id] = timestamp + prep_time
            else:
                # This event is too close to the previous one for the same finger, so we skip it.
                print(f"Skipping overlapping LH note event for motor {motor_id} at timestamp {timestamp}")

        # Use the filtered list for the rest of the function
        lh_pick_pos = filtered_lh_pick_pos
        # Idle slow-slide stretch when a string has a long gap between plucks.
        if lh_pick_pos:
            idle_window = float(getattr(tu, "LH_SLOW_SLIDE_IDLE_WINDOW", 0.0))
            slow_min = float(getattr(tu, "LH_SLOW_SLIDE_TIME_MIN", 0.0))
            slow_max = float(getattr(tu, "LH_SLOW_SLIDE_TIME_MAX", 0.0))
            slow_scale = (slow_max / idle_window) if idle_window > 0.0 else 0.0
            slow_allowed = idle_window > 0.0 and slow_max > 0.0

            pluck_times_by_motor: dict[int, list[float]] = {}
            index_by_motor: dict[int, list[int]] = {}
            for idx, raw_event in enumerate(lh_pick_pos):
                motor_id, _position, _slide_toggle, timestamp, prep_time = unpack_lh_pick_event(raw_event)
                pluck_time = float(timestamp) + float(prep_time)
                pluck_times_by_motor.setdefault(motor_id, []).append(pluck_time)
                index_by_motor.setdefault(motor_id, []).append(idx)

            for motor_id, pluck_times in pluck_times_by_motor.items():
                indices = index_by_motor.get(motor_id, [])
                for local_idx, event_idx in enumerate(indices):
                    if local_idx == 0:
                        continue
                    prev_pluck_time = pluck_times[local_idx - 1]
                    pluck_time = pluck_times[local_idx]
                    gap = pluck_time - prev_pluck_time

                    motor_id_ev, position, slide_toggle, timestamp, prep_time = unpack_lh_pick_event(
                        lh_pick_pos[event_idx]
                    )
                    if int(slide_toggle) == 1 or not slow_allowed:
                        continue
                    if gap < idle_window:
                        continue

                    target_slow = max(slow_min, slow_scale * gap) if slow_min > 0.0 else slow_scale * gap
                    target_slow = min(slow_max, target_slow) if slow_max > 0.0 else target_slow
                    if target_slow <= 0.0:
                        continue

                    pluck_time = float(timestamp) + float(prep_time)
                    new_prep_time = max(float(prep_time), target_slow)
                    if pluck_time > 0:
                        new_prep_time = min(new_prep_time, pluck_time)
                    new_timestamp = float(pluck_time - new_prep_time)
                    lh_pick_pos[event_idx] = [motor_id_ev, position, slide_toggle, new_timestamp, new_prep_time]

        # Mutes damp a string a chord marks silent. They are added after the note
        # timings are fixed, and only in a gap, so a note on that string is unchanged.
        if mutes:
            windows: dict[int, list[tuple[float, float]]] = {}
            for raw_event in lh_pick_pos:
                motor_id, _position, _slide_toggle, timestamp, prep_time = unpack_lh_pick_event(raw_event)
                windows.setdefault(motor_id, []).append((timestamp, timestamp + prep_time))
            for mute in mutes:
                start, prep_time = float(mute.start), float(mute.prep)
                if start < 0:
                    continue
                end = start + prep_time
                taken = windows.get(mute.string, [])
                if any(not (end <= begin or start >= stop) for begin, stop in taken):
                    continue
                lh_pick_pos.append([mute.string, SLIDER_MUTE, 0, start, prep_time])
                windows.setdefault(mute.string, []).append((start, end))

        initial_point_lh = initial_point[0:12]
        lh_pick_pos.sort(key=lambda event: event[3])
        max_required_time = max(
            (timestamp + prep_time for _, _, _, timestamp, prep_time in lh_pick_pos if timestamp >= 0),
            default=0.0,
        )

        # Add a small safety buffer (e.g., 200 timesteps) to prevent edge case errors
        buffer = 200 * tu.TIME_STEP
        num_rows = int((max_required_time + buffer) / tu.TIME_STEP)
        if num_rows == 0:
            num_rows = 1

        trajectory_array = np.full((num_rows, 12), np.nan)
        trajectory_array[0, :] = initial_point_lh
        current_encoder_position = list(initial_point_lh)

        def _state_at(index: int) -> list[float]: 
            # figures out where each LH motor actually is at a given timestep
            pose = list(current_encoder_position)
            if index < 0:
                return pose
            for col in range(trajectory_array.shape[1]):
                for row in range(min(index, num_rows - 1), -1, -1):
                    val = trajectory_array[row, col]
                    if not np.isnan(val):
                        pose[col] = float(val)
                        break
            return pose

        prev_position, prev_motor_id = None, None

        for motor_index, position, slide_toggle, timestamp, prep_time_s in lh_pick_pos:
            # Ignore events with negative timestamps
            if timestamp < 0:
                continue

            timestamp = round(timestamp, 3)
            start_index = int(timestamp / tu.TIME_STEP)
            curr_pos = _state_at(start_index - 1 if start_index > 0 else 0)

            slider_motor_ID, presser_motor_ID = motor_index, motor_index + 6
            q0_slider_motor = curr_pos[slider_motor_ID]
            q0_presser_motor = curr_pos[presser_motor_ID]
            action = action_for_lh_event(motor_index, position, timestamp, prep_time_s, slide_toggle)
            slider_points, presser_points = action.render(
                q0_slider_motor,
                q0_presser_motor,
                same_as_prev=prev_position == position and prev_motor_id == motor_index,
                blend=self.interp_with_blend,
                tb_cent=tb_cent,
            )

            if start_index + len(slider_points) <= num_rows:
                end_index = start_index + len(slider_points)
                trajectory_array[start_index: end_index, slider_motor_ID] = slider_points
                trajectory_array[start_index: end_index, presser_motor_ID] = presser_points

                if end_index < num_rows:
                    trajectory_array[end_index:, slider_motor_ID] = np.nan
                    trajectory_array[end_index:, presser_motor_ID] = np.nan

                current_encoder_position[slider_motor_ID] = slider_points[-1]
                current_encoder_position[presser_motor_ID] = presser_points[-1]
            else:
                safe_points = num_rows - start_index
                if safe_points > 0:
                    trajectory_array[start_index:, slider_motor_ID] = slider_points[:safe_points]
                    trajectory_array[start_index:, presser_motor_ID] = presser_points[:safe_points]
                    current_encoder_position[slider_motor_ID] = slider_points[safe_points - 1]
                    current_encoder_position[presser_motor_ID] = presser_points[safe_points - 1]

            prev_position, prev_motor_id = position, motor_index

        df = pd.DataFrame(trajectory_array)
        df.ffill(inplace=True)
        return df.to_numpy()

    def parsePlucks(self, picks):
        """Ask the configured planner for a string, then aim each picker's stroke."""
        strings = assign(picks, self.initial_point[:6], load_config().get("planner", "astar"))

        pick_events = []
        slide_toggles = []
        for pick, string in zip(picks, strings):
            if len(pick) == 6:
                note, duration, speed, slide_toggle, _specified, timestamp = pick
            else:
                note, duration, speed, slide_toggle, timestamp = pick
            timestamp = round(timestamp * tu.TIMESTAMP_ROUNDING_FACTOR) / tu.TIMESTAMP_ROUNDING_FACTOR
            duration = round(duration, 3)
            is_tremolo = duration >= tu.TREMOLO_DURATION_THRESHOLD
            if not is_tremolo:
                duration = tu.SHORT_NOTE_DEFAULT_DURATION
            if string is None:
                print(f"Warning: No string can play note {note} at {timestamp} in the prep time available.")
                continue
            pick_events.append((string, note, duration, speed, timestamp, is_tremolo))
            slide_toggles.append(slide_toggle)

        # Start each picker on the nearer of its up/down stops. Physical columns
        # are remapped (B↔e); calibration stays on the logical picker.
        rh_start_positions = list(self.initial_point[12:]) if len(self.initial_point) > 12 else []
        endpoints = []
        for motor_idx in range(len(tu.PICKER_MOTOR_INFO)):
            info = tu.PICKER_MOTOR_INFO[motor_idx]
            scale = info["resolution"] / tu.MM_TO_ENCODER_CONVERSION_FACTOR
            endpoints.append((info["up_pluck_mm"] * scale, info["down_pluck_mm"] * scale))

        picker_is_up = []
        for motor_idx, (up_enc, down_enc) in enumerate(endpoints):
            phys_idx = tu.picker_physical_index(motor_idx)
            if phys_idx >= len(rh_start_positions):
                picker_is_up.append(True)
                continue
            curr_enc = float(rh_start_positions[phys_idx])
            picker_is_up.append(abs(curr_enc - up_enc) <= abs(curr_enc - down_enc))

        pick_motor_positions = []
        for motor_id, note, duration, speed, timestamp, is_tremolo in pick_events:
            up_enc, down_enc = endpoints[motor_id]
            dest = down_enc if picker_is_up[motor_id] else up_enc
            pick_motor_positions.append([[motor_id, note, round(dest, 3), duration, speed], timestamp])
            odd_tremolo = is_tremolo and tremolo_pick_count(duration, speed) % 2 == 1
            if not is_tremolo or odd_tremolo:
                picker_is_up[motor_id] = not picker_is_up[motor_id]

        return pick_motor_positions, slide_toggles

    def interpPick(self, pick_events, slide_toggles, initial_point, tb_cent=tu.TRAJECTORY_BLEND_PERCENT):
        initial_point_rh = initial_point[12:]
        num_pickers = len(initial_point_rh)
        lh_pick_events = []

        max_timestamp = 0
        if pick_events:
            max_timestamp = max(event[1] + event[0][3] for event in pick_events)

        num_rows = int(max_timestamp / tu.TIME_STEP) + 100 # Add buffer
        trajectory_array = np.full((num_rows, num_pickers), np.nan)
        trajectory_array[0, :] = initial_point_rh
        current_positions = list(initial_point_rh)

        for i, (event_data, timestamp) in enumerate(pick_events):
            motor_id, note, commanded_dest_pos, duration, speed = event_data
            # Logical string keeps calibration / LH routing; RH column may differ (B↔e).
            phys_id = tu.picker_physical_index(motor_id)
            start_index = int(timestamp / tu.TIME_STEP)
            pluck_time = float(timestamp)

            # LH prep starts a fixed window before the pluck. Open strings leave the slider put.
            fret = note - tu.STRING_MIDI_RANGES[motor_id][0]
            hand, sound = actions_for(
                motor_id, fret, pluck_time,
                slide=bool(slide_toggles[i]), duration=duration, speed=speed,
            )
            lh_pick_events.append([
                motor_id, fret_to_encoder(motor_id, fret), slide_toggles[i], hand.start, hand.prep,
            ])

            start_pos = current_positions[phys_id]
            info = tu.PICKER_MOTOR_INFO[motor_id]
            res = info['resolution']
            down_enc = (info['down_pluck_mm'] * res) / tu.MM_TO_ENCODER_CONVERSION_FACTOR
            up_enc = (info['up_pluck_mm'] * res) / tu.MM_TO_ENCODER_CONVERSION_FACTOR

            if isinstance(sound, Pluck):
                all_points = sound.render(start_pos, commanded_dest_pos, self.interp_with_blend, tb_cent)
            elif isinstance(sound, Tremolo):
                all_points = sound.render(start_pos, down_enc, up_enc, self.interp_with_blend)
            else:
                all_points = np.array([])

            if all_points.size > 0:
                num_gen = len(all_points)
                if start_index + num_gen <= num_rows:
                    trajectory_array[start_index : start_index + num_gen, phys_id] = all_points
                current_positions[phys_id] = all_points[-1]

        df = pd.DataFrame(trajectory_array)
        df.ffill(inplace=True)
        if self.graph:
            plan_viz.log_lh_pick_events(lh_pick_events)
        return df.to_numpy(), lh_pick_events
