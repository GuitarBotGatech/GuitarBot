import numpy as np
import matplotlib.pyplot as plt
import math
# This is a custom module you will need in your environment.
from parsing.chord_selector import find_lowest_cost_chord
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import copy
import pandas as pd
import tune as tu


class GuitarBotParser:
    def __init__(self, initial_point, graph=tu.graph):
        """
        Initializes the GuitarBotParser instance.
        Args:
            initial_point (list): The starting motor positions for the robot.
            graph (bool): Whether to display a graph of the motor trajectories.
        """
        self.initial_point = initial_point
        self.current_fret_positions = [0, 0, 0, 0, 0, 0]  # Start by preferring voicings near first position
        self.graph = graph

    '''
        Main Dashboard Function
        Inputs: Raw chord, pluck commands
        Outputs: Interpolated NumPy array for RobotController to send to bot
    '''

    def parseAllMIDI(self, chords, pluck, midi_events=None):
        """
        Parses MIDI commands and generates a complete motor trajectory array.
        This is the main entry point for the parser instance.

        Args:
            chords: Raw chord OSC data.
            pluck:  Raw pluck OSC data.
            midi_events (list[TimedMessage] | None): Optional timed MIDI effect
                events.  When provided and ``self.graph`` is True, they are
                overlaid on the trajectory plot as vertical lines so the
                composer can visually verify alignment with robot motion.
        """
        # 1. Get events + Timestamps
        lh_motor_positions = self.parseleftMIDI(chords)
        picker_motor_positions, slide_toggles = self.parsePickMIDI(pluck)
        print("Slide Toggles: ", slide_toggles)

        # 2. PrepMovements (Adjust timestamps)
        picker_motor_positions_adj = self.prepPicker(lh_motor_positions, picker_motor_positions)

        # 3. Interpolate
        lh_array, pick_array = self.interpolateEvents(lh_motor_positions,
                                                      picker_motor_positions_adj,
                                                      slide_toggles,
                                                      self.initial_point)

        # 4. Combine and Finalize Trajectory
        num_lh_rows, num_lh_cols = lh_array.shape
        num_pick_rows, num_pick_cols = pick_array.shape
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

        print("Full Matrix Shape: ", combined_array.shape)

        if self.graph:
            timestamps = np.arange(0, max_rows * tu.TIME_STEP, tu.TIME_STEP)
            cc_points_by_controller = {}
            if midi_events:
                for event in midi_events:
                    if event.address != '/cc' or len(event.args) < 2:
                        continue
                    try:
                        controller = int(event.args[0])
                        value = int(round(float(event.args[1])))
                        value = max(0, min(127, value))
                    except (ValueError, TypeError):
                        continue
                    cc_points_by_controller.setdefault(controller, []).append((event.timestamp, value))

            has_cc_subplot = bool(cc_points_by_controller)
            if has_cc_subplot:
                fig = make_subplots(
                    rows=2,
                    cols=1,
                    shared_xaxes=True,
                    row_heights=[0.8, 0.2],
                    vertical_spacing=0.06,
                    subplot_titles=('Motor Positions', 'MIDI CC (0–127)')
                )
            else:
                fig = go.Figure()

            # Add a trace for each motor
            for motor in range(12):
                motor_type = "Slider" if motor < 6 else "Presser"
                string_id = motor if motor < 6 else motor - 6

                fig.add_trace(
                    go.Scatter(
                        x=timestamps,
                        y=combined_array[:, motor],
                        mode='lines',
                        name=f'LH {motor_type} {string_id + 1}'
                    ),
                    **({'row': 1, 'col': 1} if has_cc_subplot else {})
                )

            # Plot right hand motors (12-14)
            for motor in range(12, min(15, combined_array.shape[1])):
                picker_id = motor - 12

                fig.add_trace(
                    go.Scatter(
                        x=timestamps,
                        y=combined_array[:, motor],
                        mode='lines',
                        name=f'RH Picker {picker_id}',
                        line=dict(width=2)
                    ),
                    **({'row': 1, 'col': 1} if has_cc_subplot else {})
                )

            if has_cc_subplot:
                for controller in sorted(cc_points_by_controller):
                    points = sorted(cc_points_by_controller[controller], key=lambda p: p[0])
                    fig.add_trace(
                        go.Scatter(
                            x=[point[0] for point in points],
                            y=[point[1] for point in points],
                            mode='lines+markers',
                            name=f'CC{controller}',
                            marker=dict(size=5),
                            line=dict(width=1.5),
                        ),
                        row=2,
                        col=1,
                    )

            # Update layout
            if has_cc_subplot:
                fig.update_layout(
                    title='Motor Positions Over Time + MIDI CC',
                    legend_title='Signals'
                )
                fig.update_yaxes(title_text='Motor Position', row=1, col=1)
                fig.update_yaxes(title_text='CC Value', range=[0, 127], row=2, col=1)
                fig.update_xaxes(title_text='Time (s)', row=2, col=1)
            else:
                fig.update_layout(
                    title='Motor Positions Over Time',
                    xaxis_title='Time (s)',
                    yaxis_title='Motor Position',
                    legend_title='Motors'
                )
            fig.show()

        return combined_array

    def _get_chords_M(self, filepath, chord_letter, chord_type):
        fret_numbers_optimized = find_lowest_cost_chord(self.current_fret_positions, filepath, chord_letter,
                                                        chord_type)
        self.current_fret_positions = fret_numbers_optimized

        dtraj, utraj = [], []
        for i in range(6):
            if fret_numbers_optimized[i] != -1:
                dtraj = [i, 6]
                utraj = [6, i]
                break

        fret_numbers = fret_numbers_optimized.copy()
        fret_play = []

        for i in range(6):
            if fret_numbers[i] == 0:
                fret_numbers[i] = 1
                fret_play.append(1)
            elif fret_numbers[i] == -1:
                fret_numbers[i] = 1
                fret_play.append(3)
            else:
                fret_play.append(2)

        return fret_numbers, fret_play, dtraj, utraj
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

    def lh_interpolate(self, lh_motor_positions, lh_pick_pos, initial_point,
                              num_points=tu.PRESSER_INTERPOLATION_POINTS,
                              tb_cent=tu.TRAJECTORY_BLEND_PERCENT, plot=False):
        motor_available_time = {i: 0.0 for i in range(6)}

        def unpack_lh_pick_event(raw_event):
            motor_id = int(raw_event[0])
            position = raw_event[1]
            slide_toggle = raw_event[2]
            timestamp = float(raw_event[3])
            prep_time = (
                float(raw_event[4])
                if len(raw_event) >= 5
                else float(self.get_lh_note_movement_duration())
            )
            prep_time = max(float(tu.TIME_STEP), prep_time)
            return motor_id, position, slide_toggle, timestamp, prep_time

        def split_note_phase_points(prep_time_s: float) -> tuple[int, int, int]:
            total_points = max(3, int(round(prep_time_s / float(tu.TIME_STEP))))
            phase1 = max(1, total_points // 3)
            phase2 = max(1, total_points // 3)
            phase3 = total_points - phase1 - phase2
            if phase3 < 1:
                phase3 = 1
                if phase2 > 1:
                    phase2 -= 1
                elif phase1 > 1:
                    phase1 -= 1
            return phase1, phase2, phase3

        filtered_lh_pick_pos = []
        for raw_event in lh_pick_pos:
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
                duration_of_last_event = float(latest_event.get('duration_s', self.get_lh_note_movement_duration()))

            # The total time needed is the start of the last event plus its duration
            max_required_time = latest_start_time + duration_of_last_event

        # Add a small safety buffer (e.g., 200 timesteps) to prevent edge case errors
        buffer = 200 * tu.TIME_STEP
        num_rows = int((max_required_time + buffer) / tu.TIME_STEP)
        if num_rows == 0:
            num_rows = 1

        trajectory_array = np.full((num_rows, 12), np.nan)

        print("LH UPDATED EVENTS LIST (NO SYNC LH EVENTS): ")
        lh_motor_positions = self.checkSyncEvents("LH", lh_motor_positions)
        self.print_Events(lh_motor_positions)

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

        prev_type, prev_position, prev_motor_id = None, None, None

        for event in full_LH:
            # Ignore events with negative timestamps
            if event['timestamp'] < 0:
                continue

            timestamp = round(event['timestamp'], 3)
            start_index = int(timestamp / tu.TIME_STEP)

            if event['type'] == 'chord':
                target_positions_slider = event['positions'][:6]
                target_positions_presser = event['positions'][6:12]
                curr_pos = current_encoder_position.copy()
                all_points = []

                # 1. UNPRESS
                unpress_sliders = np.array(
                    [self.interp_with_blend(curr_pos[i], curr_pos[i], num_points, tb_cent) for i in range(6)]).T
                unpress_pressers = np.array(
                    [self.interp_with_blend(curr_pos[i + 6], tu.LH_PRESSER_UNPRESSED_POS, num_points, tb_cent) for i in
                     range(6)]).T
                all_points.extend(np.hstack([unpress_sliders, unpress_pressers]))

                # 2. SLIDE
                slide_sliders = np.array([self.interp_with_blend(curr_pos[i], target_positions_slider[i],
                                                                 tu.LH_SLIDER_MOTION_POINTS, tb_cent) for i in
                                          range(6)]).T
                slide_pressers = np.array([self.interp_with_blend(tu.LH_PRESSER_UNPRESSED_POS,
                                                                  tu.LH_PRESSER_UNPRESSED_POS,
                                                                  tu.LH_SLIDER_MOTION_POINTS, tb_cent) for i in
                                           range(6)]).T
                all_points.extend(np.hstack([slide_sliders, slide_pressers]))

                # 3. PRESS
                press_sliders = np.array(
                    [self.interp_with_blend(target_positions_slider[i], target_positions_slider[i], num_points, tb_cent)
                     for i in range(6)]).T
                press_pressers = np.array([self.interp_with_blend(tu.LH_PRESSER_UNPRESSED_POS,
                                                                  target_positions_presser[i], num_points, tb_cent) for
                                           i in range(6)]).T
                all_points.extend(np.hstack([press_sliders, press_pressers]))

                num_generated_points = len(all_points)
                if start_index + num_generated_points <= num_rows:
                    trajectory_array[start_index: start_index + num_generated_points, :] = all_points
                    current_encoder_position = list(all_points[-1])
                else:
                    safe_points = num_rows - start_index
                    if safe_points > 0:
                        trajectory_array[start_index:, :] = all_points[:safe_points]
                        current_encoder_position = list(all_points[safe_points - 1])


            elif event['type'] == 'note':
                slider_points, presser_points = [], []
                prep_time_s = float(event.get('prep_time', self.get_lh_note_movement_duration()))
                phase1_points, phase2_points, phase3_points = split_note_phase_points(prep_time_s)
                motor_index = event['motor_id']
                slider_motor_ID, presser_motor_ID = motor_index * 2, motor_index * 2 + 6
                q0_slider_motor, q0_presser_motor = current_encoder_position[slider_motor_ID], current_encoder_position[
                    presser_motor_ID]
                qf_slider = int(event['position'])
                qf1_presser = tu.LH_PRESSER_UNPRESSED_POS
                qf2_presser = tu.LH_PRESSER_PRESSED_POS
                # print((event['position']))
                # print(current_encoder_position[slider_motor_ID])
                # print("----------------")
                if int(event['position']) == -1:
                    qf_slider, qf2_presser = q0_slider_motor, tu.LH_PRESSER_UNPRESSED_POS
                if (int(event['position'])) == current_encoder_position[slider_motor_ID] and int(event['position']) != -1:
                    qf_slider, qf1_presser = q0_slider_motor, tu.LH_PRESSER_PRESSED_POS


                if prev_type == 'chord' or not (
                        event['type'] == prev_type and prev_position == event['position'] and prev_motor_id == event[
                    'motor_id']):
                    if event['slide_toggle']:
                        s1 = self.interp_with_blend(q0_slider_motor, q0_slider_motor, phase1_points, tb_cent)
                        p1 = self.interp_with_blend(q0_presser_motor, tu.LH_PRESSER_SLIDE_PRESS_POS, phase1_points,
                                                    tb_cent)
                        slider_points.extend(s1)
                        presser_points.extend(p1)

                        s2 = self.interp_with_blend(q0_slider_motor, qf_slider, phase2_points,
                                                    tb_cent)
                        p2 = self.interp_with_blend(tu.LH_PRESSER_SLIDE_PRESS_POS, tu.LH_PRESSER_SLIDE_PRESS_POS,
                                                    phase2_points, tb_cent)
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

                        s2 = self.interp_with_blend(q0_slider_motor, qf_slider, phase2_points,
                                                    tb_cent)
                        p2 = self.interp_with_blend(qf1_presser, qf1_presser,
                                                    phase2_points, tb_cent)
                        slider_points.extend(s2)
                        presser_points.extend(p2)

                        s3 = self.interp_with_blend(qf_slider, qf_slider, phase3_points, tb_cent)
                        p3 = self.interp_with_blend(qf1_presser, qf2_presser, phase3_points, tb_cent)
                        slider_points.extend(s3)
                        presser_points.extend(p3)
                else:
                    total_points = max(phase1_points + phase2_points + phase3_points, 1)
                    s3 = self.interp_with_blend(q0_slider_motor, qf_slider, total_points,
                                                tb_cent)
                    p3 = self.interp_with_blend(q0_presser_motor, qf2_presser, total_points,
                                                tb_cent)
                    slider_points.extend(s3)
                    presser_points.extend(p3)

                num_generated_points = len(slider_points)
                if start_index + num_generated_points <= num_rows:
                    trajectory_array[start_index: start_index + num_generated_points, slider_motor_ID] = slider_points
                    trajectory_array[start_index: start_index + num_generated_points, presser_motor_ID] = presser_points
                    current_encoder_position[slider_motor_ID] = slider_points[-1]
                    current_encoder_position[presser_motor_ID] = presser_points[-1]
                else:
                    safe_points = num_rows - start_index
                    if safe_points > 0:
                        trajectory_array[start_index:, slider_motor_ID] = slider_points[:safe_points]
                        trajectory_array[start_index:, presser_motor_ID] = presser_points[:safe_points]
                        current_encoder_position[slider_motor_ID] = slider_points[safe_points - 1]
                        current_encoder_position[presser_motor_ID] = presser_points[safe_points - 1]

                prev_type, prev_position, prev_motor_id = event["type"], event["position"], event["motor_id"]

        df = pd.DataFrame(trajectory_array)
        df.ffill(inplace=True)
        return df.to_numpy()

    def print_Events(self, motor_positions):
        print("PRINTING EVENTS: ")
        for event in motor_positions:
            print(event)

    def print_Trajs(self, interpolated_list):
        print("INTERPOLATED LIST:")
        for e, event in enumerate(interpolated_list):
            print("Event: ", e)
            for traj in event:
                for i, points in enumerate(traj):
                    print(i, points)
                print("\n")

    def checkSyncEvents(self, event_type, motor_positions):
        prev_timestamp = -10000
        new_motor_positions = []

        lh_chord_change_points = (2 * tu.PRESSER_INTERPOLATION_POINTS) + tu.LH_SLIDER_MOTION_POINTS
        event_trajs = {"LH": lh_chord_change_points, "pick": tu.PICKER_PLUCK_MOTION_POINTS}

        for event in motor_positions:
            timestamp = event[1]
            delta = round(timestamp - prev_timestamp, 3)
            required_delta = event_trajs.get(event_type, 0) * tu.TIME_STEP
            if delta >= required_delta:
                new_motor_positions.append(event)
                prev_timestamp = timestamp
            else:
                print(f"Not enough space between {event_type} events, ignoring event: {event}")
        return new_motor_positions

    def interpolateEvents(self, lh_positions_adj, picker_motor_positions_adj, slide_toggles, initial_point):
        pick_interpolated_array, lh_pick_pos = self.interpPick(picker_motor_positions_adj, slide_toggles,
                                                               initial_point)
        lh_interpolated_array = self.lh_interpolate(lh_positions_adj, lh_pick_pos, initial_point, plot=False)
        return lh_interpolated_array, pick_interpolated_array

    def parse_chord(self, chords):
        key, chord_type = 'n', "MAJOR"
        if len(chords) > 1:
            curr_index = 1
            key = chords[curr_index]
            if key not in ['#', 'f']:
                key = 'n'
            else:
                curr_index += 1
            remaining_input = chords[curr_index:]
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
        note = str.upper(chords[0])
        frets, command, dtraj, utraj = self._get_chords_M(tu.CHORD_LIBRARY_FILE, note + key, chord_type)
        return frets, command, dtraj, utraj, note, key, chord_type

    def parseleftMIDI(self, chords):
        lh_events = []
        for curr_chord in chords:
            note, timestamp = curr_chord[0][0], curr_chord[1]
            timestamp = round(timestamp * tu.TIMESTAMP_ROUNDING_FACTOR) / tu.TIMESTAMP_ROUNDING_FACTOR
            chord_input = note + curr_chord[0][1:]
            frets, command, _, _, _, _, _ = self.parse_chord(chord_input)
            lh_events.append(["LH", [frets, command], timestamp])

        lh_motor_positions = []
        slider_encoder_values = [((v * 2048) / tu.MM_TO_ENCODER_CONVERSION_FACTOR + tu.SLIDER_ENCODER_OFFSET) for v in
                                 tu.SLIDER_MM_PER_FRET]

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

    # Maps 0-based string index to picker ID for chord pluck messages.
    # Only strings 0, 2, 4 have physical pluckers.
    _CHORD_PLUCK_STRING_TO_PICKER = {0: 0, 2: 1, 4: 2}

    def _picker_note_to_fret(self, note, picker_id):
        if note is None or picker_id is None:
            return None

        try:
            picker_idx = int(picker_id)
            midi_note = int(note)
        except (TypeError, ValueError):
            return None

        if not (0 <= picker_idx < len(tu.STRING_MIDI_RANGES)):
            return None

        string_low_note = int(tu.STRING_MIDI_RANGES[picker_idx][0])
        return midi_note - string_low_note

    def _is_edge_fret(self, fret):
        if fret is None:
            return False

        min_fret = int(getattr(tu, "LH_MIN_FRET", 0))
        max_fret = int(
            getattr(
                tu,
                "LH_MAX_FRET",
                getattr(tu, "LH_HIGH_FRET_CAUTION_START_FRET", len(tu.SLIDER_MM_PER_FRET)),
            )
        )

        fret_value = int(fret)
        return fret_value <= min_fret or fret_value >= max_fret

    def _get_edge_prep_timing(self, max_prep):
        prep_bonus = max(
            0.0,
            float(
                getattr(
                    tu,
                    "LH_EDGE_PREP_TIME_BONUS",
                    getattr(tu, "LH_HIGH_FRET_EXTRA_PREP_TIME", 0.0),
                )
            ),
        )
        prep_cap = max(
            max_prep,
            float(
                getattr(
                    tu,
                    "LH_EDGE_PREP_TIME_CAP",
                    getattr(tu, "LH_HIGH_FRET_MAX_PREP_TIME", max_prep),
                )
            ),
        )
        return prep_bonus, prep_cap

    def _lh_prep_time_for_event(self, prev_note, note, duration, slide_toggle, picker_id=None):
        max_prep = float(tu.LH_PREP_TIME_BEFORE_PICK)
        min_prep = float(getattr(tu, "LH_PREP_TIME_MIN", max_prep * 0.2))
        min_prep = max(0.0, min(min_prep, max_prep))
        max_delta = int(getattr(tu, "LH_PREP_MAX_SEMITONE_DELTA", 9))
        max_delta = max(1, max_delta)
        effective_max_prep = max_prep

        if note <= 5:
            return max_prep

        same_note = prev_note is not None and int(prev_note) == int(note)
        is_tremolo = float(duration) >= float(tu.TREMOLO_DURATION_THRESHOLD)
        slide_enabled = int(slide_toggle) == 1

        if prev_note is None:
            # First fretted note after rest starts from baseline prep.
            motion_time = max_prep
        elif same_note and not slide_enabled:
            motion_time = min_prep
        else:
            semitone_delta = abs(int(note) - int(prev_note))
            ratio = min(1.0, float(semitone_delta) / float(max_delta))
            motion_time = min_prep + (max_prep - min_prep) * ratio

            if slide_enabled:
                # Sliding transitions benefit from a small extra buffer, still capped by max_prep.
                motion_time += float(tu.TIME_STEP)

        if is_tremolo:
            motion_time += float(tu.TIME_STEP)

        if picker_id is not None and note > 5:
            target_fret = self._picker_note_to_fret(note, picker_id)
            source_fret = self._picker_note_to_fret(prev_note, picker_id) if prev_note is not None else None

            near_edge = self._is_edge_fret(target_fret) or self._is_edge_fret(source_fret)
            if near_edge:
                edge_prep_bonus, edge_prep_cap = self._get_edge_prep_timing(max_prep)

                # Add safety headroom whenever a move starts from or lands near a travel edge.
                motion_time = max(motion_time, max_prep) + edge_prep_bonus
                effective_max_prep = edge_prep_cap

        return min(effective_max_prep, max(min_prep, motion_time))

    def parsePickMIDI(self, picks):
        """
        Parses picking MIDI commands and converts them into motor positions.
        Allows for optional manual string assignment for each pick.
        Args:
            picks (list of tuples): A list where each tuple represents a picking event.
                The tuple format can be either:
                (note, duration, speed, slide_toggle, timestamp) for automatic string assignment,
                OR
                (note, duration, speed, slide_toggle, timestamp, string) for manual assignment,
                where 'string' is an integer from 1 to 6.

                Special chord pluck format: when note is 0-5, it is treated as a direct
                string index (0-based) that activates the plucker without modifying the
                slider trajectory.  Only strings 0, 2, 4 have pluckers; strings 1, 3, 5
                will produce a warning and be skipped.
        Returns:
            tuple: A tuple containing:
                - pick_motor_positions (list): A list of motor position events for the picking mechanism.
                - slide_toggles (list): A list of boolean slide toggles corresponding to each pick.
        """
        pick_events = []
        slide_toggles = []
        string_ranges_tuples = [(r[0], r[1]) for r in tu.STRING_MIDI_RANGES]
        active_pickers = [-.5] * len(string_ranges_tuples)
        last_notes = [None] * len(string_ranges_tuples)

        def _is_note_playable_on_picker(note_value, picker_id):
            if not (0 <= picker_id < len(string_ranges_tuples)):
                return False
            low, _high = string_ranges_tuples[picker_id]
            max_note = low + len(tu.SLIDER_MM_PER_FRET)
            return low <= note_value <= max_note

        def _resolve_specified_picker_id(note_value, specified_string_value):
            if specified_string_value is None:
                return None
            raw = int(specified_string_value)
            candidates = []

            # Preferred: 0-based index (UI uses 0,1,2)
            if 0 <= raw < len(string_ranges_tuples):
                candidates.append(raw)

            # Backward compatibility: 1-based index
            one_based = raw - 1
            if 0 <= one_based < len(string_ranges_tuples) and one_based not in candidates:
                candidates.append(one_based)

            for candidate in candidates:
                if _is_note_playable_on_picker(note_value, candidate):
                    return candidate
            return None

        for pick_info in picks:
            if len(pick_info) == 6:
                note, duration, speed, slide_toggle, specified_string, timestamp = pick_info
            else:
                note, duration, speed, slide_toggle, timestamp = pick_info
                specified_string = None
            assigned = False
            timestamp = round(timestamp * tu.TIMESTAMP_ROUNDING_FACTOR) / tu.TIMESTAMP_ROUNDING_FACTOR

            # Chord pluck: note 0-5 is a direct string index, not a MIDI pitch.
            # The plucker fires but the slider trajectory is left unchanged.
            if 0 <= note <= 5:
                pickerID = self._CHORD_PLUCK_STRING_TO_PICKER.get(note)
                if pickerID is None:
                    print(f"Warning: String {note} has no plucker, skipping chord pluck at {timestamp}.")
                elif timestamp >= active_pickers[pickerID]:
                    pick_events.append(["pick", [pickerID, note, duration, speed, timestamp]])
                    slide_toggles.append(slide_toggle)
                    active_pickers[pickerID] = timestamp
                else:
                    print(f"Warning: Picker {pickerID} busy at {timestamp}, skipping chord pluck on string {note}.")
                continue
            duration = round(duration, 3)
            if duration < tu.TREMOLO_DURATION_THRESHOLD:
                duration = tu.SHORT_NOTE_DEFAULT_DURATION

            if specified_string is not None:
                pickerID = _resolve_specified_picker_id(note, specified_string)
                if pickerID is not None:
                    prep_time = self._lh_prep_time_for_event(
                        last_notes[pickerID],
                        note,
                        duration,
                        slide_toggle,
                        picker_id=pickerID,
                    )
                    if last_notes[pickerID] == note or timestamp - prep_time >= active_pickers[pickerID]:
                        pick_events.append(["pick", [pickerID, note, duration, speed, timestamp]])
                        slide_toggles.append(slide_toggle)
                        active_pickers[pickerID] = timestamp
                        last_notes[pickerID] = note
                        assigned = True
                    else:
                        print(f"Warning: Specified picker {pickerID} busy for note {note} at {timestamp}. Falling back to auto-assignment.")
                else:
                    print(f"Warning: Note {note} is not playable on specified string {specified_string}. Falling back to auto-assignment.")

            # 2. Fallback to automatic assignment if no string was specified or if the specified one failed
            if not assigned:
                for pickerID, (low, high) in enumerate(string_ranges_tuples):
                    if low <= note <= high:
                        prep_time = self._lh_prep_time_for_event(
                            last_notes[pickerID],
                            note,
                            duration,
                            slide_toggle,
                            picker_id=pickerID,
                        )
                        if last_notes[pickerID] == note or timestamp - prep_time >= active_pickers[pickerID]:
                            pick_events.append(["pick", [pickerID, note, duration, speed, timestamp]])
                            slide_toggles.append(slide_toggle)
                            active_pickers[pickerID] = timestamp
                            last_notes[pickerID] = note
                            assigned = True
                            break

            # 3. If still not assigned after all attempts, print a warning
            if not assigned:
                print(f"Warning: No available picker for note {note} at timestamp {timestamp}")

        pick_motor_positions = []

        # Infer picker start state from the parser's current RH start point so
        # segment-to-segment plucks stay synchronized with the actual trajectory.
        rh_start_positions = list(self.initial_point[12:]) if len(self.initial_point) > 12 else []
        pickerStates = []  # True = up, False = down
        for motor_idx in range(len(tu.PICKER_MOTOR_INFO)):
            if motor_idx >= len(rh_start_positions):
                pickerStates.append(True)
                continue

            info = tu.PICKER_MOTOR_INFO[motor_idx]
            res = info['resolution']
            down_enc = (info['down_pluck_mm'] * res) / tu.MM_TO_ENCODER_CONVERSION_FACTOR
            up_enc = (info['up_pluck_mm'] * res) / tu.MM_TO_ENCODER_CONVERSION_FACTOR
            curr_enc = float(rh_start_positions[motor_idx])

            dist_to_up = abs(curr_enc - up_enc)
            dist_to_down = abs(curr_enc - down_enc)
            pickerStates.append(dist_to_up <= dist_to_down)

        for _, (motor_id, note, duration, speed, timestamp) in pick_events:
            pick_state = pickerStates[motor_id]
            dest_key = 'down_pluck_mm' if pick_state else 'up_pluck_mm'
            qf_mm = tu.PICKER_MOTOR_INFO[motor_id][dest_key]
            res = tu.PICKER_MOTOR_INFO[motor_id]['resolution']
            pos2pulse = (qf_mm * res) / tu.MM_TO_ENCODER_CONVERSION_FACTOR

            curr_event = [motor_id, note, round(pos2pulse, 3), duration, speed]
            pick_motor_positions.append([curr_event, timestamp])
            if duration < tu.TREMOLO_DURATION_THRESHOLD:
                pickerStates[motor_id] = not pick_state
        return pick_motor_positions, slide_toggles

    def prepPicker(self, lh_motor_positions, pick_motor_positions):
        pick_motor_positions_prepped = []
        lh_timestamps = [ts for _, ts in lh_motor_positions]

        for pick_element in pick_motor_positions:
            pick_timestamp = pick_element[1]
            note = pick_element[0][1]
            # Chord plucks (note 0-5) are intentionally paired with chord events;
            # they must not be filtered out by the LH overlap window.
            if 0 <= note <= 5:
                pick_motor_positions_prepped.append(pick_element)
                continue
            overlap = any(abs(pick_timestamp - lh_ts) <= tu.MOVEMENT_OVERLAP_WINDOW for lh_ts in lh_timestamps)
            if not overlap:
                pick_motor_positions_prepped.append(pick_element)
            else:
                print(f"Picker event at {pick_timestamp} overlaps with LH movement, removing.")
        return pick_motor_positions_prepped

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
        last_lh_note_by_picker = [None] * max(1, len(tu.PICKER_MOTOR_INFO))

        for i, (event_data, timestamp) in enumerate(pick_events):
            motor_id, note, commanded_dest_pos, duration, speed = event_data
            start_index = int(timestamp / tu.TIME_STEP)
            is_pluck = duration < tu.TREMOLO_DURATION_THRESHOLD

            start_pos = current_positions[motor_id]
            info = tu.PICKER_MOTOR_INFO[motor_id]
            res = info['resolution']
            down_enc = (info['down_pluck_mm'] * res) / tu.MM_TO_ENCODER_CONVERSION_FACTOR
            up_enc = (info['up_pluck_mm'] * res) / tu.MM_TO_ENCODER_CONVERSION_FACTOR
            mid_point = (up_enc + down_enc) / 2

            all_points = np.array([]) # Initialize as empty numpy array
            if is_pluck:
                # Keep picker timing in sync with parsePickMIDI by honoring the commanded destination.
                dest_pos = float(commanded_dest_pos)
                all_points = self.interp_with_blend(start_pos, dest_pos, tu.PICKER_PLUCK_MOTION_POINTS, tb_cent)
            else: # Tremolo
                tremolo_points = []
                fill_points = min(30, int(30 - (speed - 1) * (25 / 9))) - 4
                single_pick_duration = (fill_points * tu.TIME_STEP) + (tu.PICKER_PLUCK_MOTION_POINTS * tu.TIME_STEP)
                num_picks = math.floor(duration / single_pick_duration) if single_pick_duration > 0 else 0

                current_pick_pos = start_pos
                for _ in range(num_picks):
                    dest_pos = down_enc if current_pick_pos < mid_point else up_enc
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
                    trajectory_array[start_index : start_index + num_gen, motor_id] = all_points
                current_positions[motor_id] = all_points[-1]

            # Chord plucks (note 0-5) activate the plucker without repositioning the slider.
            if note > 5:
                fret = note - tu.STRING_MIDI_RANGES[motor_id][0]
                if fret == 0:
                    lh_enc_val = -1
                else:
                    s_dir = tu.STRING_MIDI_RANGES[motor_id][2]
                    lh_enc_val = ((tu.SLIDER_MM_PER_FRET[fret - 1] * 2048) / tu.MM_TO_ENCODER_CONVERSION_FACTOR + tu.SLIDER_ENCODER_OFFSET) * s_dir
                prev_note = last_lh_note_by_picker[motor_id] if 0 <= motor_id < len(last_lh_note_by_picker) else None
                prep_time = self._lh_prep_time_for_event(
                    prev_note,
                    note,
                    duration,
                    slide_toggles[i],
                    picker_id=motor_id,
                )
                lh_pick_events.append([motor_id, lh_enc_val, slide_toggles[i], timestamp - prep_time, prep_time])
                if 0 <= motor_id < len(last_lh_note_by_picker):
                    last_lh_note_by_picker[motor_id] = note

        df = pd.DataFrame(trajectory_array)
        df.ffill(inplace=True)
        print("LH PICK EVENTS: ", lh_pick_events)
        return df.to_numpy(), lh_pick_events

    def scale_speed(self, value):
        usermin, usermax = 1, 10
        fastest, slowest = 0.025, 0.15
        return (10 + 2 * (
                    (slowest / tu.TIME_STEP) - (value - 1) * ((fastest * 1000) / (usermax - usermin)))) * tu.TIME_STEP

    def tremolocos(self, curT, period, amp, vert_shift, pick_state):
        if pick_state == 1:
            return vert_shift + amp * math.cos((2 * math.pi * curT) / period)
        else:
            return vert_shift + amp * -math.cos((2 * math.pi * curT) / period)

    def maketremolo(self, vert_shift, amp, duration, speed, pick_state):
        period = self.scale_speed(speed)
        tstep = tu.TIME_STEP
        num_tremolos = (duration // period)
        trem_times = np.arange(0, (num_tremolos * period) + tstep, tstep)
        tremoloArray = [self.tremolocos(t, period, amp, vert_shift, pick_state) for t in trem_times]
        end_fill = duration - trem_times[-1]
        if end_fill > 0:
            fill_array = np.full(int(period // tstep), tremoloArray[-1])
            tremoloArray.extend(fill_array)
        return tremoloArray

    def get_lh_note_movement_duration(self):
        # Legacy fallback duration when per-event prep metadata is unavailable.
        return float(tu.LH_PREP_TIME_BEFORE_PICK)

    def scaleAmplitude(self, max_amplitude, min_amplitude, speed):
        low_speed, high_speed = 1, 10
        return max_amplitude + ((speed - low_speed) / (high_speed - low_speed)) * (min_amplitude - max_amplitude)

    def interp_with_sine_blend(self, start_pos, end_pos, num_points):
        if num_points == 0:
            return np.array([])
        t = np.linspace(0, np.pi, num_points)
        blend = (1 - np.cos(t)) / 2
        return (1 - blend) * start_pos + blend * end_pos