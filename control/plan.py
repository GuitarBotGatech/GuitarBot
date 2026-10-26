import numpy as np
import math
from control.chord_selector import find_lowest_cost_chord
import pandas as pd
from tuning import tune as tu
from control.path_planner import plan_strings
from control.debug import plan_viz


class GuitarBotParser:
    def __init__(self, initial_point, graph=tu.graph):
        self.initial_point = initial_point
        self.current_fret_positions = [0, 0, 0, 0, 0, 0]  # Start by preferring voicings near first position
        self.graph = graph
        self.use_path_planner = True

    def parseAll(self, chords, pluck):
        """
        Build a complete motor trajectory from notation planner rows.

        Args:
            chords: Chord rows from ``SongArrangement.to_planner_rows()``
                (``[chord_string, timestamp]``).
            pluck: Pluck rows from the same compiler
                (``[note, duration, speed, slide, timestamp]`` or with
                ``string_index`` inserted before timestamp).
        """
        # 1. Get events + Timestamps
        lh_motor_positions = self.parseChords(chords)
        picker_motor_positions, slide_toggles = self.parsePlucks(pluck)
        if self.graph:
            plan_viz.log_slide_toggles(slide_toggles)

        # 2. Interpolate (RH first — also emits LH prep events for fretted plucks)
        pick_array, lh_pick_pos = self.interpPick(picker_motor_positions, slide_toggles, self.initial_point)
        lh_array = self.lh_interpolate(lh_motor_positions, lh_pick_pos, self.initial_point)

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

    def lh_interpolate(self, lh_motor_positions, lh_pick_pos, initial_point, num_points=tu.PRESSER_INTERPOLATION_POINTS, tb_cent=tu.TRAJECTORY_BLEND_PERCENT):

        motor_available_time = {i: 0.0 for i in range(6)}
        lh_motor_positions = self.checkSyncEvents(lh_motor_positions)
        chord_motion_s = ((2 * tu.PRESSER_INTERPOLATION_POINTS) + tu.LH_SLIDER_MOTION_POINTS) * tu.TIME_STEP
        
        chord_windows = sorted(
            (float(ts), float(ts) + chord_motion_s)
            for _, ts in lh_motor_positions
            if float(ts) >= 0
        )
        next_chord = 0

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
            while next_chord < len(chord_windows) and chord_windows[next_chord][0] <= timestamp:
                chord_end = chord_windows[next_chord][1]
                for motor in range(6):
                    motor_available_time[motor] = max(motor_available_time[motor], chord_end)
                next_chord += 1
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

        initial_point_lh = initial_point[0:12]
        all_events_for_sizing = []
        if lh_motor_positions:
            for _, timestamp in lh_motor_positions:
                all_events_for_sizing.append({'timestamp': timestamp, 'type': 'chord'})

        if lh_pick_pos:
            for raw_event in lh_pick_pos:
                _, _, _, timestamp, prep_time = unpack_lh_pick_event(raw_event)
                if timestamp >= 0:
                    all_events_for_sizing.append({'timestamp': timestamp, 'type': 'note', 'duration_s': prep_time})

        max_required_time = 0
        if all_events_for_sizing:
            # Find the event with the latest start time
            latest_event = max(all_events_for_sizing, key=lambda x: x['timestamp'])
            latest_start_time = latest_event['timestamp']

            # Calculate the duration of that latest event to find its end time
            duration_of_last_event = 0
            if latest_event['type'] == 'chord':
                num_generated_points = (2 * tu.PRESSER_INTERPOLATION_POINTS) + tu.LH_SLIDER_MOTION_POINTS
                duration_of_last_event = num_generated_points * tu.TIME_STEP
            elif latest_event['type'] == 'note':
                duration_of_last_event = float(latest_event.get('duration_s', tu.LH_PREP_TIME_BEFORE_PICK))

            # The total time needed is the start of the last event plus its duration
            max_required_time = latest_start_time + duration_of_last_event

        # Add a small safety buffer (e.g., 200 timesteps) to prevent edge case errors
        buffer = 200 * tu.TIME_STEP
        num_rows = int((max_required_time + buffer) / tu.TIME_STEP)
        if num_rows == 0:
            num_rows = 1

        trajectory_array = np.full((num_rows, 12), np.nan)

        if self.graph:
            plan_viz.log_lh_events_header()
            plan_viz.print_events(lh_motor_positions)

        full_LH = []
        for motor_pos, timestamp in lh_motor_positions:
            full_LH.append({'type': 'chord', 'positions': motor_pos, 'timestamp': timestamp})
        for raw_event in lh_pick_pos:
            motor_id, position, slide_toggle, timestamp, prep_time = unpack_lh_pick_event(raw_event)
            full_LH.append(
                {'type': 'note', 'motor_id': motor_id, 'position': position, 'slide_toggle': slide_toggle,
                 'timestamp': timestamp, 'prep_time': prep_time})
        full_LH.sort(key=lambda x: x['timestamp'])

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

        for event in full_LH:
            # Ignore events with negative timestamps
            if event['timestamp'] < 0:
                continue

            timestamp = round(event['timestamp'], 3)
            start_index = int(timestamp / tu.TIME_STEP)
            curr_pos = _state_at(start_index - 1 if start_index > 0 else 0)

            if event['type'] == 'chord':
                target_positions_slider = event['positions'][:6]
                target_positions_presser = event['positions'][6:12]
                all_points = []

                # 1. UNPRESS
                unpress_sliders = np.array([self.interp_with_blend(curr_pos[i], curr_pos[i], num_points, tb_cent) for i in range(6)]).T
                unpress_pressers = np.array([self.interp_with_blend(curr_pos[i + 6], tu.LH_PRESSER_UNPRESSED_POS, num_points, tb_cent) for i in range(6)]).T

                all_points.extend(np.hstack([unpress_sliders, unpress_pressers]))

                # 2. SLIDE
                slide_sliders = np.array([self.interp_with_blend(curr_pos[i], target_positions_slider[i], tu.LH_SLIDER_MOTION_POINTS, tb_cent) for i in range(6)]).T
                slide_pressers = np.array([self.interp_with_blend(tu.LH_PRESSER_UNPRESSED_POS, tu.LH_PRESSER_UNPRESSED_POS, tu.LH_SLIDER_MOTION_POINTS, tb_cent) for i in range(6)]).T
                all_points.extend(np.hstack([slide_sliders, slide_pressers]))

                # 3. PRESS
                press_sliders = np.array([self.interp_with_blend(target_positions_slider[i], target_positions_slider[i], num_points, tb_cent) for i in range(6)]).T
                press_pressers = np.array([self.interp_with_blend(tu.LH_PRESSER_UNPRESSED_POS, target_positions_presser[i], num_points, tb_cent) for i in range(6)]).T
                all_points.extend(np.hstack([press_sliders, press_pressers]))

                num_generated_points = len(all_points)
                if start_index + num_generated_points <= num_rows:
                    end_index = start_index + num_generated_points
                    trajectory_array[start_index: end_index, :] = all_points

                    if end_index < num_rows:
                        trajectory_array[end_index:, :] = np.nan
                    current_encoder_position = list(all_points[-1])
                else:
                    safe_points = num_rows - start_index
                    if safe_points > 0:
                        trajectory_array[start_index:, :] = all_points[:safe_points]
                        current_encoder_position = list(all_points[safe_points - 1])


            elif event['type'] == 'note':
                slider_points, presser_points = [], []
                prep_time_s = float(event.get('prep_time', tu.LH_PREP_TIME_BEFORE_PICK))
                total_points = max(3, int(round(prep_time_s / float(tu.TIME_STEP))))
                base, remainder = divmod(total_points, 3)
                phase1_points = phase2_points = base
                phase3_points = base + remainder

                motor_index = event['motor_id']
                slider_motor_ID, presser_motor_ID = motor_index, motor_index + 6

                q0_slider_motor = curr_pos[slider_motor_ID]
                q0_presser_motor = curr_pos[presser_motor_ID]
                qf_slider = int(event['position'])
                qf1_presser = tu.LH_PRESSER_UNPRESSED_POS
                qf2_presser = tu.LH_PRESSER_PRESSED_POS

                if int(event['position']) == -1:
                    qf_slider, qf2_presser = q0_slider_motor, tu.LH_PRESSER_UNPRESSED_POS
                if int(event['position']) == int(round(q0_slider_motor)) and int(event['position']) != -1:
                    qf_slider, qf1_presser = q0_slider_motor, tu.LH_PRESSER_PRESSED_POS

                if not (prev_position == event['position'] and prev_motor_id == event['motor_id']):
                    if event['slide_toggle']:
                        s1 = self.interp_with_blend(q0_slider_motor, q0_slider_motor, phase1_points, tb_cent)
                        p1 = self.interp_with_blend(q0_presser_motor, tu.LH_PRESSER_SLIDE_PRESS_POS, phase1_points, tb_cent)
                        slider_points.extend(s1)
                        presser_points.extend(p1)

                        s2 = self.interp_with_blend(q0_slider_motor, qf_slider, phase2_points, tb_cent)
                        p2 = self.interp_with_blend(tu.LH_PRESSER_SLIDE_PRESS_POS, tu.LH_PRESSER_SLIDE_PRESS_POS, phase2_points, tb_cent)
                        slider_points.extend(s2)
                        presser_points.extend(p2)

                        s3 = self.interp_with_blend(qf_slider, qf_slider, phase3_points, tb_cent)
                        p3 = self.interp_with_blend(tu.LH_PRESSER_SLIDE_PRESS_POS, qf2_presser, phase3_points, tb_cent)
                        slider_points.extend(s3)
                        presser_points.extend(p3)
                    else:
                        s1 = self.interp_with_blend(q0_slider_motor, q0_slider_motor, phase1_points, tb_cent)
                        p1 = self.interp_with_blend(q0_presser_motor, qf1_presser, phase1_points, tb_cent)
                        slider_points.extend(s1)
                        presser_points.extend(p1)

                        s2 = self.interp_with_blend(q0_slider_motor, qf_slider, phase2_points, tb_cent)
                        p2 = self.interp_with_blend(qf1_presser, qf1_presser, phase2_points, tb_cent)
                        slider_points.extend(s2)
                        presser_points.extend(p2)

                        s3 = self.interp_with_blend(qf_slider, qf_slider, phase3_points, tb_cent)
                        p3 = self.interp_with_blend(qf1_presser, qf2_presser, phase3_points, tb_cent)
                        slider_points.extend(s3)
                        presser_points.extend(p3)
                else:
                    total_points = max(phase1_points + phase2_points + phase3_points, 1)
                    s3 = self.interp_with_blend(q0_slider_motor, qf_slider, total_points, tb_cent)
                    p3 = self.interp_with_blend(q0_presser_motor, qf2_presser, total_points, tb_cent)
                    slider_points.extend(s3)
                    presser_points.extend(p3)

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

                prev_position, prev_motor_id = event["position"], event["motor_id"]

        df = pd.DataFrame(trajectory_array)
        df.ffill(inplace=True)
        return df.to_numpy()

    def checkSyncEvents(self, motor_positions):
        prev_timestamp = -10000
        new_motor_positions = []
        lh_chord_change_points = (2 * tu.PRESSER_INTERPOLATION_POINTS) + tu.LH_SLIDER_MOTION_POINTS
        required_delta = lh_chord_change_points * tu.TIME_STEP

        for event in motor_positions:
            timestamp = event[1]
            delta = round(timestamp - prev_timestamp, 3)
            if delta >= required_delta:
                new_motor_positions.append(event)
                prev_timestamp = timestamp
            else:
                print(f"Not enough space between LH events, ignoring event: {event}")
        return new_motor_positions

    def _get_voicing(self, symbol):
        """Chord symbol → (fret numbers, press commands) for the cheapest library voicing."""
        key, chord_type = 'n', "MAJOR"
        if len(symbol) > 1:
            curr_index = 1
            key = symbol[curr_index]
            if key not in ['#', 'f']:
                key = 'n'
            else:
                curr_index += 1
            remaining_input = symbol[curr_index:]
            if len(remaining_input) == 1:
                chord_types_one_letter = {'m': "MINOR", '7': "DOMINANT", '9': "DOMINANT", '13': "DOMINANT",
                                          'o': "HALF-DIM", '5': "FIFTH"}
                chord_type = chord_types_one_letter.get(remaining_input, chord_type)
            elif len(remaining_input) == 2:
                chord_types_two_letters = {"M6": "MAJOR6", "M7": "MAJOR7", "M9": "MAJOR9", "m6": "MINOR6",
                                           "m7": "MINOR7", "m9": "MINOR9"}
                chord_type = chord_types_two_letters.get(remaining_input, chord_type)
            elif len(remaining_input) >= 3:
                chord_types_three_letters = {"sus": "SUS4", "sus4": "SUS4", "sus2": "SUS2", "dim": "DIMINISHED",
                                             "dim7": "DIMINISHED"}
                chord_type = chord_types_three_letters.get(remaining_input, chord_type)
        note = str.upper(symbol[0])
        voicing = find_lowest_cost_chord(self.current_fret_positions, tu.CHORD_LIBRARY_FILE, note + key, chord_type)

        self.current_fret_positions = voicing
        fret_numbers = voicing.copy()

        press_commands = []
        for i in range(6):
            if fret_numbers[i] == 0:
                fret_numbers[i] = 1
                press_commands.append(1)
            elif fret_numbers[i] == -1:
                fret_numbers[i] = 1
                press_commands.append(3)
            else:
                press_commands.append(2)

        return fret_numbers, press_commands

    def parseChords(self, chords):
        """Chord planner rows → LH motor position events."""
        lh_events = []
        for curr_chord in chords:
            timestamp = round(curr_chord[1] * tu.TIMESTAMP_ROUNDING_FACTOR) / tu.TIMESTAMP_ROUNDING_FACTOR
            frets, command = self._get_voicing(curr_chord[0])
            lh_events.append(["LH", [frets, command], timestamp])

        lh_motor_positions = []
        slider_encoder_values = [((v * 2048) / tu.MM_TO_ENCODER_CONVERSION_FACTOR + tu.SLIDER_ENCODER_OFFSET) for v in tu.SLIDER_MM_PER_FRET]

        for _, (positions, command), timestamp in lh_events:
            motor_values = []
            for i, fret in enumerate(positions):
                mult = tu.SLIDER_MOTOR_DIRECTION[i]
                if 1 <= fret <= len(slider_encoder_values):
                    motor_values.append(slider_encoder_values[fret - 1] * mult)
                else:
                    motor_values.append(0)  # Default for open or invalid

            for i, press_cmd in enumerate(command):
                if 1 <= press_cmd <= len(tu.PRESSER_ENCODER_POSITIONS):
                    motor_values.append(tu.PRESSER_ENCODER_POSITIONS[press_cmd - 1])
                else:
                    motor_values.append(tu.LH_PRESSER_UNPRESSED_POS)
                    
            lh_motor_positions.append([motor_values, timestamp])
        return lh_motor_positions

    def _tremolo_fill_points(self, speed):
        fill_points = min(30, int(30 - (speed - 1) * (25 / 9))) - 4
        return max(0, fill_points)

    def _estimate_tremolo_pick_count(self, duration, speed):
        fill_points = self._tremolo_fill_points(speed)
        single_pick_duration = (fill_points * tu.TIME_STEP) + (tu.PICKER_PLUCK_MOTION_POINTS * tu.TIME_STEP)

        return max(0, math.floor(duration / single_pick_duration))

    def _picker_ready_for_note(self, picker_id, note, slide_toggle, timestamp, last_notes, active_pickers):
        if last_notes[picker_id] == note and int(slide_toggle) != 1:
            return True

        prep_time = float(tu.LH_PREP_TIME_BEFORE_PICK)
        return float(timestamp) - prep_time + 1e-9 >= float(active_pickers[picker_id])

    def parsePlucks(self, picks): 
        """assigns each pluck once and turns that list into motor positions"""

        explicit_override_indices = {idx for idx, pick in enumerate(picks) if len(pick) == 6 and pick[4] is not None}

        if self.use_path_planner:
            picks = plan_strings(picks, initial_frets=list(self.current_fret_positions))

        n_strings = len(tu.STRING_MIDI_RANGES)
        pick_events = []
        slide_toggles = []
        # Free before the song, including a note at t=0 that still needs LH prep.
        active_pickers = [-0.5] * n_strings
        last_notes = [None] * n_strings

        def playable_on(note_value, picker_id):
            if not 0 <= picker_id < n_strings:
                return False
            low, high, _direction = tu.STRING_MIDI_RANGES[picker_id]
            return low <= note_value <= high

        def commit(picker_id, note, duration, speed, slide_toggle, timestamp, is_tremolo, remember_note):
            pick_events.append((picker_id, note, duration, speed, timestamp, is_tremolo))
            slide_toggles.append(slide_toggle)
            active_pickers[picker_id] = timestamp
            if remember_note:
                last_notes[picker_id] = note

        for pick_idx, pick_info in enumerate(picks):
            if len(pick_info) == 6:
                note, duration, speed, slide_toggle, specified_string, timestamp = pick_info
            else:
                note, duration, speed, slide_toggle, timestamp = pick_info
                specified_string = None
            timestamp = round(timestamp * tu.TIMESTAMP_ROUNDING_FACTOR) / tu.TIMESTAMP_ROUNDING_FACTOR

            # Chord pluck: note 0-5 is the string index. The plucker fires; the slider stays put.
            if 0 <= note <= 5:
                if timestamp >= active_pickers[note]:
                    commit(
                        note, note, duration, speed, slide_toggle, timestamp,
                        duration >= tu.TREMOLO_DURATION_THRESHOLD, False,
                    )
                else:
                    print(f"Warning: Picker {note} busy at {timestamp}, skipping chord pluck on string {note}.")
                continue

            duration = round(duration, 3)
            is_tremolo = duration >= tu.TREMOLO_DURATION_THRESHOLD
            if not is_tremolo:
                duration = tu.SHORT_NOTE_DEFAULT_DURATION
            assigned = False

            if specified_string is not None:
                picker_id = int(specified_string)
                if playable_on(note, picker_id):
                    ready = self._picker_ready_for_note(picker_id, note, slide_toggle, timestamp, last_notes, active_pickers)
                    if pick_idx in explicit_override_indices:
                        if not ready:
                            print(
                                f"Warning: Specified picker {picker_id} busy for note {note} at {timestamp}. "
                                "Honoring explicit string override."
                            )
                        commit(picker_id, note, duration, speed, slide_toggle, timestamp, is_tremolo, True)
                        assigned = True
                    elif ready:
                        commit(picker_id, note, duration, speed, slide_toggle, timestamp, is_tremolo, True)
                        assigned = True
                    else:
                        print(
                            f"Warning: Specified picker {picker_id} busy for note {note} at {timestamp}. "
                            "Falling back to auto-assignment."
                        )
                else:
                    print(f"Warning: Note {note} is not playable on specified string {specified_string}. Falling back to auto-assignment.")

            if not assigned:
                for picker_id, (low, high, _direction) in enumerate(tu.STRING_MIDI_RANGES):
                    if low <= note <= high and self._picker_ready_for_note(picker_id, note, slide_toggle, timestamp, last_notes, active_pickers):
                        commit(picker_id, note, duration, speed, slide_toggle, timestamp, is_tremolo, True)
                        assigned = True
                        break

            if not assigned:
                print(f"Warning: No available picker for note {note} at timestamp {timestamp}")

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
            odd_tremolo = is_tremolo and self._estimate_tremolo_pick_count(duration, speed) % 2 == 1
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
            is_pluck = duration < tu.TREMOLO_DURATION_THRESHOLD
            pluck_time = float(timestamp)

            # Chord plucks (note 0-5) never move the slider. Fretted notes start LH
            # prep a fixed window before the pluck.
            lh_event = None  # [motor_id, enc, slide, t_start, prep] or None

            if note > 5:
                fret = note - tu.STRING_MIDI_RANGES[motor_id][0]
                if fret == 0:
                    lh_enc_val = -1
                else:
                    s_dir = tu.STRING_MIDI_RANGES[motor_id][2]
                    lh_enc_val = ((tu.SLIDER_MM_PER_FRET[fret - 1] * 2048) / tu.MM_TO_ENCODER_CONVERSION_FACTOR + tu.SLIDER_ENCODER_OFFSET) * s_dir
                t_min = float(tu.LH_PREP_TIME_BEFORE_PICK)
                lh_event = [motor_id, lh_enc_val, slide_toggles[i], pluck_time - t_min, t_min]

            start_pos = current_positions[phys_id]
            info = tu.PICKER_MOTOR_INFO[motor_id]
            res = info['resolution']
            down_enc = (info['down_pluck_mm'] * res) / tu.MM_TO_ENCODER_CONVERSION_FACTOR
            up_enc = (info['up_pluck_mm'] * res) / tu.MM_TO_ENCODER_CONVERSION_FACTOR

            all_points = np.array([])
            if is_pluck:
                dest_pos = float(commanded_dest_pos)
                all_points = self.interp_with_blend(
                    start_pos, dest_pos, tu.PICKER_PLUCK_MOTION_POINTS, tb_cent
                )
            else:
                tremolo_points = []
                fill_points = self._tremolo_fill_points(speed)
                num_picks = self._estimate_tremolo_pick_count(duration, speed)
                current_pick_pos = start_pos
                for _ in range(num_picks):
                    dest_pos = (
                        down_enc
                        if abs(current_pick_pos - up_enc) < abs(current_pick_pos - down_enc)
                        else up_enc
                    )
                    points1 = self.interp_with_blend(current_pick_pos, dest_pos, tu.PICKER_PLUCK_MOTION_POINTS, 0.2)
                    points2 = np.full(fill_points, dest_pos)
                    tremolo_points.extend(points1)
                    tremolo_points.extend(points2)
                    current_pick_pos = dest_pos
                if tremolo_points:
                    all_points = np.array(tremolo_points)

            if all_points.size > 0:
                num_gen = len(all_points)
                if start_index + num_gen <= num_rows:
                    trajectory_array[start_index : start_index + num_gen, phys_id] = all_points
                current_positions[phys_id] = all_points[-1]

            if lh_event is not None:
                lh_pick_events.append(lh_event)

        df = pd.DataFrame(trajectory_array)
        df.ffill(inplace=True)
        if self.graph:
            plan_viz.log_lh_pick_events(lh_pick_events)
        return df.to_numpy(), lh_pick_events
