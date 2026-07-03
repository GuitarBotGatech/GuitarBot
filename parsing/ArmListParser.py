import numpy as np
import matplotlib.pyplot as plt
import math
from parsing.chord_selector import find_lowest_cost_chord
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import copy


class ArmListParser:
    current_fret_positions = [0, 0, 0, 0, 0, 0]  # begins by preferring voicings near first position
    slide_toggle = None

    @staticmethod
    def _get_chords_M(filepath, chord_letter, chord_type):
        # print("chord stats: ", chord_type, chord_letter)

        fret_numbers_optimized = find_lowest_cost_chord(ArmListParser.current_fret_positions, filepath, chord_letter,
                                                        chord_type)
        ArmListParser.current_fret_positions = fret_numbers_optimized

        # NOTE keep for future use (when we want to know exactly which strings to strum)
        dtraj, utraj = [], []

        for i in range(6):
            if fret_numbers_optimized[i] != -1:
                dtraj = [i, 6]
                utraj = [6, i]
                break

        fret_numbers = fret_numbers_optimized.copy()
        fret_play = []

        # fret_play of 1 is open, 2 is pressed, 3 is muted
        for i in range(6):
            if fret_numbers[i] == 0:
                fret_numbers[i] = 1
                fret_play.append(1)
            elif fret_numbers[i] == -1:
                fret_numbers[i] = 1
                fret_play.append(3)
            else:
                fret_play.append(2)

        # print(fret_numbers, fret_play)
        # print(dtraj, utraj)

        return fret_numbers, fret_play, dtraj, utraj

    # parse right arm (strums) input
    @staticmethod
    def parseright_M(right_arm, measure_time):
        initialStrum = "D"
        firstbfound = False
        mra = 0
        pmra = 0
        pbra = 0
        deltaT = 0
        strumOnsets = []
        time = 0
        right_information = right_arm.copy()
        # print("right arm, parseright: ",right_arm)
        for measure in right_information:
            tempM = []
            bra = 0
            for beat in measure:
                # convert any lowercase inputs to uppercase:
                beat = str.upper(beat)

                if beat == "U" or beat == "D" or beat == "":
                    if not firstbfound:
                        if beat == "D":
                            strumOnsets.append([time, 'D', 'N'])
                            right_information[mra][bra] = [beat, "N", measure_time / 8, 1]  # Change strum time here
                        if beat == "U":
                            strumOnsets.append([time, 'U', 'N'])
                            right_information[mra][bra] = [beat, "N", measure_time / 8, 1]  # Change strum time here

                        firstbfound = True
                        initialStrum = beat
                        pmra = mra
                        pbra = bra

                        bra += 1
                        deltaT += measure_time / 8
                        time += measure_time / 8
                        checkfirst = False
                        continue
                    if beat == "U":
                        strumOnsets.append([time, 'U', 'N'])
                        right_information[mra][bra] = [beat, "N", measure_time / 8, deltaT]  # Change strum time here
                        if right_information[pmra][pbra][0] == "U":
                            right_information[pmra][pbra][1] = "C"
                        right_arm[pmra][pbra][3] = deltaT
                        pmra -= pmra
                        pmra += mra
                        pbra -= pbra
                        pbra += bra
                        deltaT = 0
                        # print(pmra, pbra)
                    if beat == "D":
                        strumOnsets.append([time, 'D', 'N'])
                        right_information[mra][bra] = [beat, "N", measure_time / 8, deltaT]  # Change strum time here
                        if right_information[pmra][pbra][0] == "D":
                            right_information[pmra][pbra][1] = "C"
                        right_information[pmra][pbra][3] = deltaT
                        pmra -= pmra
                        pmra += mra
                        pbra -= pbra
                        pbra += bra
                        deltaT = 0
                else:
                    print(right_information, mra, bra)
                    raise Exception("Right Arm input incorrect")
                bra += 1
                time += (measure_time / 8)
                # print(right_information, mra, bra, "loop")
                deltaT += measure_time / 8
            mra += 1
        count = 0
        for x in strumOnsets:
            try:
                if x[1] == 'D' and strumOnsets[count + 1][1] == 'D':
                    x[2] = 'C'
                if x[1] == 'U' and strumOnsets[count + 1][1] == 'U':
                    x[2] = 'C'
                count += 1
            except:
                break
        rh_events = []
        prev_strum = 'N'
        for x in strumOnsets:
            pos = 45
            deflect = 0
            if x[1] == 'U':
                pos = -45
            if prev_strum == x[1]:
                deflect = 1
            timestamp = round(x[0] * 200) / 200  # Rounding to nearest 0.005 = PDO_RATE
            rh_events.append(['strum', [pos, 75, deflect], timestamp])  # Later, 75 is default speed, change later
            prev_strum = x[1]  #For detecting deflects
        print("LEN RH: ", len(rh_events))
        # print("ri", right_information, initialStrum)
        #print("These are the strumOnsets: ", strumOnsets)
        #print("These are the right hand events: ", rh_events)
        print("RH EVENTS LIST: ")

        ArmListParser.print_Events(rh_events)

        strummer_dict = {
            -45: [-115, 8],  #US
            45: [-15, 10]  # DS
        }

        rh_motor_positions = []
        deflections = []

        for event in rh_events:
            strumType = event[1][0]  # 45 or -45
            speed = event[1][1]  # 75
            deflect = event[1][2]  # 0 or 1
            time_stamp = event[2]
            strum_mm_qf = strummer_dict.get(strumType)[0]  # -115 or -15
            strum_mm_qf = (strum_mm_qf * 2048) / 9.4
            picker_mm_qf = strummer_dict.get(strumType)[1]
            picker_mm_qf = (picker_mm_qf * 2048) / 9.4

            if deflect == 1:
                deflections.append(1)
            else:
                deflections.append(0)
            rh_motor_positions.append([[strum_mm_qf, picker_mm_qf], time_stamp])

        print("\nRH MM:")
        ArmListParser.print_Events(rh_motor_positions)
        print("DEFLECTIONS LIST: ", deflections)
        return rh_motor_positions, deflections

    # parse left arm (chords) input
    @staticmethod
    def parseleft_M(left_arm, measure_time):
        firstc = []
        firstcfound = False
        mcount = 0
        mtimings = []
        time = 0
        for measure in left_arm:
            bcount = 0
            for chords in measure:
                if len(chords) != 0:
                    # Parse each individual chord input
                    # default to major, natural chord: 'C', 'G', 'F', etc.
                    key = 'n'
                    type = "MAJOR"

                    # in case the user entered a basic chord (ex. 'C'), we skip over this. Key/type have already been set by default
                    if len(chords) > 1:
                        curr_index = 1

                        # determine whether chord is sharp/natural/flat
                        key = chords[curr_index]
                        if key != '#' and key != 'b':
                            key = 'n'
                        else:
                            curr_index += 1

                        # grab the rest of the chord input
                        remaining_input = chords[curr_index:]

                        # check one-letter notations first
                        if len(remaining_input) == 1:
                            if remaining_input == 'm':
                                type = "MINOR"
                                # print("MINOR CHORD")

                            # TODO: split these into individual chords once chords library is updated
                            elif remaining_input == '7' or remaining_input == '9' or remaining_input == '13':
                                type = "DOMINANT"
                                # print("DOMINANT CHORD")
                            elif remaining_input == 'o':
                                type = "HALF-DIM"
                                # print("HALF-DIM CHORD")

                            # # TODO: add this to chords library, then uncomment
                            # elif remaining_input == '+':
                            #     type = "AUGMENTED"
                            #     # print("AUGMENTED CHORD")

                            elif remaining_input == '5':
                                type = "FIFTH"
                                # Power chord
                                # print("FIFTH CHORD")

                        # check two-letter notations
                        elif len(remaining_input) == 2:
                            if remaining_input == "M6":
                                type = "MAJOR6"
                                # print("MAJOR6 CHORD")
                            elif remaining_input == "M7":
                                type = "MAJOR7"
                                # print("MAJOR7 CHORD")
                            elif remaining_input == "M9":
                                type = "MAJOR9"
                                # print("MAJOR9 CHORD")
                            elif remaining_input == "m6":
                                type = "MINOR6"
                                # print("MINOR6 CHORD")
                            elif remaining_input == "m7":
                                type = "MINOR7"
                                # print("MINOR7 CHORD")
                            elif remaining_input == "m9":
                                type = "MINOR9"
                                # print("MINOR9 CHORD")

                            # # TODO: uncomment once added to chords library
                            # elif remaining_input == "m11":
                            #     type = "MINOR11"
                            #     # print("MINOR11 CHORD")

                        # check three-letter+ notations
                        elif len(remaining_input) >= 3:
                            if remaining_input == "sus" or remaining_input == "sus4":
                                type = "SUS4"
                                # print("SUS4 CHORD")
                            elif remaining_input == "sus2":
                                type = "SUS2"
                                # print("SUS2 CHORD")

                            # TODO: split these into individual chords once chords library is updated
                            elif remaining_input == "dim" or remaining_input == "dim7":
                                type = "DIMINISHED"
                                # print("DIMINISHED CHORD")

                            # check for test chord inputs
                            if remaining_input == "TEST0" or remaining_input == "TEST":
                                type = "TEST0"
                                print("test 0 accepted")
                            if remaining_input == "TEST1":
                                type = "TEST1"
                                print("test 1 accepted")
                            if remaining_input == "TEST2":
                                type = "TEST2"
                                print("test 2 accepted")
                            if remaining_input == "TEST3":
                                type = "TEST3"
                                print("test 3 accepted")
                            if remaining_input == "TEST4":
                                type = "TEST4"
                                print("test 4 accepted")
                            if remaining_input == "TEST5":
                                type = "TEST5"
                                print("test 5 accepted")
                            if remaining_input == "TEST6":
                                type = "TEST6"
                                print("test 6 accepted")
                            if remaining_input == "TEST7":
                                type = "TEST7"
                                print("test 7 accepted")

                    # read chord from csv
                    note = str.upper(chords[0])
                    # frets, command, dtraj, utraj = ArmListParser._get_chords_M("Chords - Chords.csv", note + key, type)
                    frets, command, dtraj, utraj = ArmListParser._get_chords_M("Alternate_Chords.csv", note + key, type)
                    left_arm[mcount][bcount] = [frets, command]
                    mtimings.append(time)
                    if not firstcfound:
                        firstc.append(frets)
                        firstc.append(command)
                        firstcfound = True
                time += measure_time / 4
                bcount += 1
            mcount += 1
        print("queue: ", mtimings)
        # print(left_arm)
        justchords = []
        lh_events = []
        i = 0
        for m in left_arm:
            for b in m:
                if b == '':
                    continue
                else:
                    justchords.append(b)
                    timestamp = round(mtimings[i] * 200) / 200  # Rounding to nearest 0.005 = PDO_RATE
                    lh_events.append(["LH", b, timestamp])
                    i += 1
        # print("jc", justchords)
        #print("These are the chord change onsets: ", mtimings)
        #print("These are the LH Events: ", lh_events)
        # Note, lh_events is the new list we'd like to return.
        # Plan for LH Conversions to points
        # For each event, we want to send n x [[m], timestamp] where n is the number of points for an event and m are the 18 motor values.
        # STEP 1: convert to encoder tick positions.
        # For events in lh_events
        lh_motor_positions = []
        slider_mm_values = [23, 56, 87, 114, 143, 167, 190, 214, 236]
        slider_encoder_values = []
        mult = -1
        for value in slider_mm_values:
            encoder_tick = (value * 2048) / 9.4
            slider_encoder_values.append(encoder_tick)

        presser_encoder_values = [-10, 350, 200]
        for events in lh_events:
            # for lh_events[1][0] AND for lh_events[1][1]
            # convert from fret position/finger position to encoder tick position respectively
            temp = [[]]
            # make motors 1,4,5 negative

            for i, slider_value in enumerate(events[1][0]):
                mult = -1
                if i == 1 or i == 2 or i == 5:
                    mult = 1
                if 1 <= slider_value <= 9:
                    temp[0].append(slider_encoder_values[slider_value - 1] * mult)
            for i, presser_value in enumerate(events[1][1]):
                if 1 <= presser_value <= 3:
                    temp[0].append(presser_encoder_values[presser_value - 1])
            temp.append(events[2])
            lh_motor_positions.append(temp)

        # STEP 2: For every event, create a new list of points that interpolates the events into 60 points.
        #

        # Generate the interpolated list
        print("LH EVENTS LIST: ")
        ArmListParser.print_Events(lh_motor_positions)

        return lh_motor_positions

    @staticmethod
    def interp_with_blend(q0, qf, N, tb_cent):
        curve = np.zeros(N)
        if curve is None:
            return
        nb = int(tb_cent * N)
        a_2 = 0.5 * (qf - q0) / (nb * (N - nb))

        for i in range(nb):
            tmp = a_2 * (i ** 2)
            curve[i] = q0 + tmp
            curve[N - i - 1] = qf - tmp

        tmp = a_2 * (nb ** 2)
        qa = q0 + tmp
        qb = qf - tmp

        curve[nb:N - nb] = np.linspace(qa, qb, N - (2 * nb))
        curve = curve.astype(int)

        return curve

    @staticmethod
    def lh_interpolate(lh_motor_positions, lh_pick_pos, initial_point, num_points=10, tb_cent=0.2, plot=False):
        # initial_point = [0, 0, 0, 0, 0, 0, -10, -10, -10, -10, -10, -10]  # Initial position, remember to make dynamic later.
        #print("lh_pick_pos: ", lh_pick_pos)
        initial_point = initial_point[0:12]
        current_encoder_position = []
        sorted_lh_pick_pos = sorted(lh_pick_pos, key=lambda x: x[-1])
        if not lh_pick_pos:
            max_timestamp = lh_motor_positions[-1][1] + 0.6
        else:
            #print("LAST LH MOTOR POSITION: ", lh_motor_positions[-1], lh_motor_positions[-1][1])
            #print("LAST PICK MOTOR POSITION: ", lh_pick_pos[-1], lh_pick_pos[-1][2])

            max_timestamp = max(lh_motor_positions[-1][1] + 0.6, sorted_lh_pick_pos[-1][3] + .6)  # 6

        full_matrix = {}
        for t in np.arange(0, max_timestamp + 0.005, 0.005):
            full_matrix[round(t, 3)] = [100000] * 12  # 12 zeros for 12 motors

        for i, value in enumerate(initial_point):
            if i < 6:
                # encoder_tick = (value * 2048) / 9.4
                current_encoder_position.append(value)
            else:
                current_encoder_position.append(value)

        #1. Check to make sure no syncrhonous LH Events
        print("LH UPDATED EVENTS LIST (NO SYNC LH EVENTS): ")
        lh_motor_positions = ArmListParser.checkSyncEvents("LH", lh_motor_positions)
        ArmListParser.print_Events(lh_motor_positions)
        curr_ts = 0
        # combine pick and chord lists and add headers
        full_LH = []

        # Process lh_motor_positions
        for motor_pos, timestamp in lh_motor_positions:
            full_LH.append({
                'type': 'chord',
                'positions': motor_pos,
                'timestamp': timestamp
            })

        # Process lh_pick_pos

        for motor_id, position, slide_toggle, timestamp in lh_pick_pos:
            full_LH.append({
                'type': 'note',
                'motor_id': motor_id,
                'position': position,
                'slide_toggle': slide_toggle,
                'timestamp': timestamp
            })

        # Sort the combined dictionary by timestamp
        full_LH.sort(key=lambda x: x['timestamp'])
        #print("FULL LH MATRIX SORTED: ", full_LH)
        full_matrix[0] = initial_point
        prev_type = None
        prev_position = None
        prev_motor_id = None
        for i, event in enumerate(full_LH):
            timestamp = round(event['timestamp'], 3)

            if timestamp in full_matrix:
                if event['type'] == 'chord':
                    points = []
                    target_positions_slider = event['positions'][:6]  # First 6 values of the nested list
                    target_positions_presser = event['positions'][6:12]  # last 6
                    curr_pos = current_encoder_position.copy()
                    interpolated_values_1 = [  # Hold slider 10 points
                        ArmListParser.interp_with_blend(curr_pos[i], curr_pos[i],
                                                        num_points, tb_cent)  # Change to fill later
                        for i in range(len(target_positions_slider))
                    ]

                    interpolated_points_1 = list(map(list, zip(*interpolated_values_1)))
                    interpolated_values_2 = [  # Unpress pressers for 10 points
                        ArmListParser.interp_with_blend(curr_pos[i + 6], -500, num_points, tb_cent)
                        for i in range(len(target_positions_presser))
                    ]
                    interpolated_points_2 = list(map(list, zip(*interpolated_values_2)))

                    f_20 = [points1 + points2 for points1, points2 in zip(interpolated_points_1, interpolated_points_2)]
                    points.extend(f_20)

                    # Second 20 points
                    interpolated_values_3 = [  # Move sliders 40 points
                        ArmListParser.interp_with_blend(curr_pos[i], target_positions_slider[i],
                                                        40, tb_cent)
                        for i in range(len(target_positions_slider))
                    ]
                    interpolated_points_3 = list(map(list, zip(*interpolated_values_3)))
                    interpolated_values_4 = [  # Hold Unpress for 40 points
                        ArmListParser.interp_with_blend(-500, -500, 40, tb_cent)  # Change to fill later
                        for i in range(len(target_positions_presser))]
                    interpolated_points_4 = list(map(list, zip(*interpolated_values_4)))

                    s_20 = [points1 + points2 for points1, points2 in zip(interpolated_points_3, interpolated_points_4)]
                    points.extend(s_20)

                    # Third 20 points
                    interpolated_values_5 = [  # Hold slider for 10 points
                        ArmListParser.interp_with_blend(target_positions_slider[i], target_positions_slider[i],
                                                        num_points, tb_cent)  # Change to fill later
                        for i in range(len(target_positions_slider))
                    ]
                    interpolated_points_5 = list(map(list, zip(*interpolated_values_5)))
                    interpolated_values_6 = [  # Press for 10 points
                        ArmListParser.interp_with_blend(-500, target_positions_presser[i], num_points, tb_cent)
                        for i in range(len(target_positions_presser))
                    ]
                    interpolated_points_6 = list(map(list, zip(*interpolated_values_6)))

                    t_20 = [points1 + points2 for points1, points2 in zip(interpolated_points_5, interpolated_points_6)]
                    curr_t = timestamp
                    points.extend(t_20)
                    for curr_p in points:
                        full_matrix[curr_t] = curr_p
                        curr_t = round(curr_t + .005, 3)
                        current_encoder_position = copy.deepcopy(curr_p)


                elif event['type'] == 'note':
                    num_points_note = 60
                    current_type = event['type']
                    current_motor_id = event['motor_id']
                    current_position = event['position']
                    slide_toggle = event['slide_toggle']

                    slider_points = []
                    presser_points = []
                    motor_index = event['motor_id']
                    slider_motor_ID = motor_index + motor_index  # CHANGE ME LATER FOR ALL MOTORS
                    presser_motor_ID = motor_index + 6 + motor_index  # CHANGE ME LATER FOR ALL MOTORS
                    # q0_slider_motor = current_encoder_position[motor_index] # For all motors
                    q0_slider_motor = current_encoder_position[slider_motor_ID]  # CHANGE ME LATER FOR ALL MOTORS
                    # q0_presser_motor = current_encoder_position[motor_index + 6] # For all motors
                    q0_presser_motor = current_encoder_position[presser_motor_ID]  # CHANGE ME LATER FOR ALL MOTORS
                    qf_slider = int(event['position'])
                    qf_presser = 600
                    if int(event['position']) == -1:  # open string
                        qf_slider = q0_slider_motor
                        qf_presser = -500
                    if prev_type == 'chord' or not (
                            current_type == prev_type and prev_position == current_position and prev_motor_id == current_motor_id):  # If the prior is not the same MIDI note
                        print("DIFFERENT NOTE")

                        print("qf presser: ", qf_presser)
                        # If sliding
                        if slide_toggle:
                            print("SLIDING")
                            # Hold slider 10 points, press to 650
                            s1 = ArmListParser.interp_with_blend(q0_slider_motor, q0_slider_motor, num_points, tb_cent)
                            p1 = ArmListParser.interp_with_blend(q0_presser_motor, 600, num_points, tb_cent)
                            slider_points.extend(s1)
                            presser_points.extend(p1)

                            # Move slider 60 points, keep pressing
                            s2 = ArmListParser.interp_with_blend(q0_slider_motor, qf_slider, num_points_note, tb_cent)
                            p2 = ArmListParser.interp_with_blend(600, 600, 60, tb_cent)
                            slider_points.extend(s2)
                            presser_points.extend(p2)

                            # Hold slide 10 points, keep pressing (unless open string)
                            s3 = ArmListParser.interp_with_blend(qf_slider, qf_slider, num_points, tb_cent)
                            p3 = ArmListParser.interp_with_blend(600, qf_presser, num_points, tb_cent)
                            slider_points.extend(s3)
                            presser_points.extend(p3)

                        else:  # Not sliding
                            print("NOT SLIDING")
                            qf_presser_unpress = -500
                            qf_presser_press = 650
                            # Hold slider 10 points, unpress to -500 for 20 points
                            s1 = ArmListParser.interp_with_blend(q0_slider_motor, q0_slider_motor, 20, tb_cent)
                            p1 = ArmListParser.interp_with_blend(q0_presser_motor, qf_presser_unpress, 20, tb_cent)
                            slider_points.extend(s1)
                            presser_points.extend(p1)

                            # Move slider 40 points, hold presser
                            s2 = ArmListParser.interp_with_blend(q0_slider_motor, qf_slider, 25, tb_cent)
                            p2 = ArmListParser.interp_with_blend(qf_presser_unpress, qf_presser_unpress, 25, tb_cent)
                            slider_points.extend(s2)
                            presser_points.extend(p2)

                            # Hold slider 10 points, press
                            s3 = ArmListParser.interp_with_blend(qf_slider, qf_slider, 20, tb_cent)
                            p3 = ArmListParser.interp_with_blend(qf_presser_unpress, qf_presser, 20, tb_cent)
                            slider_points.extend(s3)
                            presser_points.extend(p3)


                    else:  # Same note back to back
                        print("Same NOTE")
                        s3 = ArmListParser.interp_with_blend(q0_slider_motor, qf_slider, num_points_note, tb_cent)
                        p3 = ArmListParser.interp_with_blend(q0_presser_motor, qf_presser, num_points, tb_cent)
                        slider_points.extend(s3)
                        presser_points.extend(p3)

                    curr_t = timestamp
                    for curr_p in slider_points:
                        full_matrix[curr_t][slider_motor_ID] = copy.deepcopy(curr_p)
                        curr_t = round(curr_t + .005, 3)
                    curr_t = timestamp
                    for curr_p in presser_points:
                        full_matrix[curr_t][presser_motor_ID] = copy.deepcopy(curr_p)
                        curr_t = round(curr_t + .005, 3)

                    current_encoder_position[slider_motor_ID] = s3[-1]
                    current_encoder_position[presser_motor_ID] = p3[-1]

                    # Update previous note values
                    prev_type = event["type"]
                    prev_position = event["position"]
                    prev_motor_id = event["motor_id"]

        # Fill in gaps
        prev_values = initial_point.copy()
        for t in sorted(full_matrix.keys()):
            for i in range(12):
                if full_matrix[t][i] == initial_point[i]:
                    full_matrix[t][i] = prev_values[i]
                else:
                    prev_values[i] = full_matrix[t][i]

        sorted_timestamps = sorted(full_matrix.keys())
        #print("Sorted Timestamps: ", sorted_timestamps) # up to 6
        previous_values = copy.deepcopy(initial_point)

        for timestamp in sorted_timestamps:
            current_values = full_matrix[timestamp]
            for i in range(len(current_values)):
                if current_values[i] == 100000:
                    current_values[i] = previous_values[i]
                else:
                    previous_values[i] = current_values[i]
            full_matrix[timestamp] = current_values

        return full_matrix


    @staticmethod
    def plot_interpolation(data=None, points=None, mode="events", matrix=None):
        if mode == "events":
            fig, axs = plt.subplots(4, 3, figsize=(20, 24))  # 4 rows, 3 columns of subplots
            fig.suptitle('Graph of 12 Motors Over Time', fontsize=6)
            axs = axs.flatten()

            for i in range(points):
                for event in data:
                    points, timestamp = event
                    # Round to nearest 0.005
                    #print("debug, ", points)
                    #print("debug, ", timestamp)
                    points = np.array(points)
                    time_values = np.arange(len(points)) * 0.005 + timestamp  # 5ms per point

                    axs[i].plot(time_values, points[:, i])

                axs[i].set_title(f'Motor {i + 1}')
                axs[i].set_xlabel('Time (seconds)')
                axs[i].set_ylabel('Encoder Tick Value')
                axs[i].grid(True)

            plt.tight_layout()
            plt.show()
        if mode == "matrix":
            timestamps = list(matrix.keys())
            motor_data = np.array(list(matrix.values()))

            num_motors = motor_data.shape[1]

            num_rows = (num_motors - 1) // 3 + 1
            num_cols = min(3, num_motors)

            fig, axs = plt.subplots(num_rows, num_cols, figsize=(15, 5 * num_rows))
            axs = axs.flatten()

            for i in range(num_motors):
                axs[i].plot(timestamps, motor_data[:, i])
                axs[i].set_title(f'Motor {i + 1}')
                axs[i].set_xlabel('Time (seconds)')
                axs[i].set_ylabel('Encoder Tick Value')
                axs[i].grid(True)

            for i in range(num_motors, len(axs)):
                fig.delaxes(axs[i])

            plt.tight_layout()
            plt.show()

    @staticmethod
    def print_Events(motor_positions):
        print("PRINTING EVENTS: ")
        for event in motor_positions:
            print(event)

    @staticmethod
    def print_Trajs(interpolated_list):
        print("INTERPOLATED LIST:")
        for e, event in enumerate(interpolated_list):
            print("Event: ", e)
            for traj in event:
                for i, points in enumerate(traj):
                    print(i, points)
                print("\n")

    @staticmethod
    def getFullMatrix(events_list, initial_point, plot=False):

        full_matrix = {}
        full_matrix[0.000] = initial_point

        for event in events_list:
            points, timestamp = event
            # print("debug, ", points)
            # print("debug, ", timestamp)
            points = np.array(points)
            time_values = np.arange(len(points)) * 0.005 + timestamp  # 5ms per point
            for time, point in zip(time_values, points):
                full_matrix[round(time, 3)] = point.tolist()

        ## Fill
        # Find the maximum timestamp
        max_time = max(full_matrix.keys())

        # Create a list of all timestamps, including the original ones
        all_timestamps = sorted(set(list(full_matrix.keys()) +
                                    [round(t, 3) for t in np.arange(0, max_time + .005, .005)]))

        last_value = None

        # Iterate through all timestamps
        for timestamp in all_timestamps:
            if timestamp in full_matrix:
                last_value = full_matrix[timestamp]
            elif last_value is not None:
                # If it's an interpolated timestamp, use the last known value
                full_matrix[timestamp] = last_value
        # print resulting dictionary
        i = 0
        full_matrix = dict(sorted(full_matrix.items()))
        for key, value in full_matrix.items():
            print(f"{i}| {key} : {value}")
            i += 1
        if plot:
            ArmListParser.plot_interpolation(mode="matrix", matrix=full_matrix)
        return full_matrix

    # Will dynamically add deflect messages between events if there is enough space
    @staticmethod
    def checkDeflect(rh_motor_positions, deflections):
        prev_timestamp = 0  # dummy initial value
        new_rh_motor_positions = []
        idx = 0
        num_deflections = 0
        total_strum_speed = 60  # 40 points for SS, 5 points for SP # CHANGE LATER
        buffer_time = 0.005  #seconds
        for event in rh_motor_positions:
            new_rh_motor_positions.append(event)
        for event_index, event in enumerate(rh_motor_positions):
            strummer_slider_qf = event[0][0]
            strummer_picker_qf = event[0][1]
            timestamp = event[1]
            if deflections[event_index] == 1:  # DEFLECT NEEDED BEFORE THIS EVENT
                # 1. Check to see if there's enough time for a deflect message before this event (speed + 5ms picker + 5ms buffer = 230ms)
                # There is enough space if time between events is > 2 * 230ms because 230ms to do first event, then another 230ms to deflect
                strum_time = (total_strum_speed * 0.005) + buffer_time  #ms
                delta = round(timestamp - prev_timestamp, 3)
                required_delta = 2 * strum_time
                print(f"{timestamp} - {prev_timestamp} = {delta}")

                if delta > required_delta:  # Insert deflect message, TODO: ELSE, ignore the message because there's not enough time to deflect
                    num_deflections += 1

                    if strummer_slider_qf == -3268.0851063829787:  # if coming from a down strum, insert an upstrum
                        deflect_SS_qf = -115
                        deflect_SP_qf = 14
                    else:
                        deflect_SS_qf = -15
                        deflect_SP_qf = 14

                    deflect_SS_qf = (deflect_SS_qf * 2048) / 9.4
                    deflect_SP_qf = (deflect_SP_qf * 2048) / 9.4
                    # If deflection, add a deflect event right after the previous event
                    #print("INSERTING DEFLECTION BEFORE EVENT: ", idx)
                    new_rh_motor_positions.insert(idx, [[deflect_SS_qf, deflect_SP_qf],
                                                        prev_timestamp + strum_time])  # add deflect event after first event finishes
                    idx += 1  # Because inserting into new list, need to increment properly to stay on track (double increment only when inserting)
                else:  # NOT ENOUGH SPACE IN BETWEEN EVENTS TO DEFLECT SO IGNORE SECOND EVENT
                    print("Not enough space to deflect, ignoring event:", idx)
                    new_rh_motor_positions.pop(idx)
                    idx -= 1

            idx += 1
            prev_timestamp = timestamp
        print("NUMBER OF DEFLECTIONS ADDED: ", num_deflections)

        return new_rh_motor_positions

    # This function checks if any SAME TYPE EVENTS are called too close together (RH/LH sync is handled elsewhere)
    @staticmethod
    def checkSyncEvents(event_type, motor_positions):
        prev_timestamp = -10000  # dummy initial value
        new_motor_positions = []
        for event in motor_positions:
            new_motor_positions.append(event)

        event_trajs = {
            "LH": 60,
            "strum": 45,
            "pick": 5
        }
        idx = 0
        for event_index, event in enumerate(motor_positions):
            points, timestamp = event
            delta = round(timestamp - prev_timestamp, 3)
            required_delta = event_trajs.get(
                event_type) * 0.005  # The amount of time to complete the trajectory based on event type
            if delta < required_delta:
                new_motor_positions.pop(idx)
                print("Not enough space between events, ignoring event: ", idx)
                print("REQUIRED DELTA: ", required_delta)
                print(f"RESULTING DELTA: {timestamp} - {prev_timestamp} = {delta}")
                idx -= 1

            idx += 1
            prev_timestamp = timestamp

        return new_motor_positions



    @staticmethod
    def interpolateEvents(lh_positions_adj, picker_motor_positions_adj, slide_toggles, initial_point):

        # rh_interpolated_dictionary = ArmListParser.rh_interpolate(rh_positions_adj, deflections, initial_point)
        pick_interpolated_dictionary, lh_pick_pos = ArmListParser.interpPick(picker_motor_positions_adj, slide_toggles,
                                                                             initial_point)
        lh_interpolated_dictionary = ArmListParser.lh_interpolate(lh_positions_adj, lh_pick_pos, initial_point,
                                                                  plot=False)

        return lh_interpolated_dictionary, pick_interpolated_dictionary

    '''
    Main Dashboard Function
    Inputs: Raw chord, strum, pluck commands
    Outputs: Interpolated dictionary for RobotController to send to bot
    '''

    @staticmethod
    def parseAllMIDI(chords, pluck, initial_point, graph=True):
        #Initialize full dictionary
        allpoints = {}
        #Dictionaries for LH and RH

        #1. Get events + Timestamps
        lh_motor_positions = ArmListParser.parseleftMIDI(chords)
        # rh_motor_positions, deflections = ArmListParser.parserightMIDI(strum) (dep)
        picker_motor_positions, slide_toggles = ArmListParser.parsePickMIDI(pluck)
        print("Slide Toggles: ", slide_toggles)

        #2. PrepMovements (Adjust timestamps) LH changes occur before a strum,
        # lh_positions_adj, rh_positions_adj = ArmListParser.prepMovements(lh_motor_positions, rh_motor_positions) (dep)
        # Make sure no LH movements happen at the same time as a picker movement.
        picker_motor_positions_adj = ArmListParser.prepPicker(lh_motor_positions, picker_motor_positions)
        # print("LH events")
        # ArmListParser.print_Events(lh_positions_adj)
        # print("Picker events")
        # ArmListParser.print_Events(picker_motor_positions_adj)
        #3. Interpolate (dedicated interp function)
        lh_dictionary, pick_dictionary = ArmListParser.interpolateEvents(lh_motor_positions, picker_motor_positions_adj,
                                                                         slide_toggles, initial_point)

        # print("Picker Dictionary: ")  # only up to 6
        # i = 0
        # for key, value in pick_dictionary.items():
        #     print(f"{i}| {key} : {value}")
        #     i += 1
        # Find the maximum timestamp across all dictionaries
        max_timestamp = max(max(lh_dictionary.keys()), max(pick_dictionary.keys()))
        print("Max Timestamp ParseAllMidi: ", max_timestamp)

        # Create a list of all timestamps, including interpolated ones
        all_timestamps = sorted(set(
            list(lh_dictionary.keys()) +
            # list(rh_dictionary.keys()) +
            list(pick_dictionary.keys()) +
            [round(t, 3) for t in np.arange(0, max_timestamp + 0.005, 0.005)]
        ))

        # Interpolate all dictionaries
        lh_interpolated = ArmListParser.interpolate_dict(lh_dictionary, all_timestamps)
        pick_interpolated = ArmListParser.interpolate_dict(pick_dictionary, all_timestamps)

        # Combine all dictionaries
        combined_dict = {}
        for timestamp in all_timestamps:
            combined_dict[timestamp] = (
                    lh_interpolated.get(timestamp, []) +
                    pick_interpolated.get(timestamp, [])
            )
        i = 0
        print("Full Matrix: ")
        for key, value in combined_dict.items():
            print(f"{i}| {key} : {value}")
            i += 1
        if graph:
            fig = go.Figure()

            #Add a trace for each motor
            for motor in range(15):
                # if motor > 13:
                y_values = [values[motor] for values in combined_dict.values()]
                fig.add_trace(
                    go.Scatter(x=list(combined_dict.keys()), y=y_values, mode='lines', name=f'Motor {motor + 1}'))

            # Update layout
            fig.update_layout(
                title='Motor Positions Over Time',
                xaxis_title='Timestamp',
                yaxis_title='Motor Position',
                legend_title='Motors'
            )

            # Show the plot
            fig.show()

        return combined_dict

    @staticmethod
    def interpolate_dict(dictionary, all_timestamps):
        interpolated = {}
        last_value = None
        for timestamp in all_timestamps:
            if timestamp in dictionary:
                last_value = dictionary[timestamp]
            if last_value is not None:
                interpolated[timestamp] = last_value
        return interpolated

    @staticmethod
    def parse_chord(chords):
        # Default chord type and key
        key = 'n'
        chord_type = "MAJOR"

        if len(chords) > 1:
            curr_index = 1

            # Determine whether chord is sharp/natural/flat
            key = chords[curr_index]
            if key not in ['#', 'f']:
                key = 'n'
            else:
                curr_index += 1

            # Grab the rest of the chord input
            remaining_input = chords[curr_index:]

            # Check one-letter notations
            if len(remaining_input) == 1:
                chord_types_one_letter = {
                    'm': "MINOR",
                    '7': "DOMINANT",
                    '9': "DOMINANT",
                    '13': "DOMINANT",
                    'o': "HALF-DIM",
                    '5': "FIFTH"
                }
                chord_type = chord_types_one_letter.get(remaining_input, chord_type)

            # Check two-letter notations
            elif len(remaining_input) == 2:
                chord_types_two_letters = {
                    "M6": "MAJOR6",
                    "M7": "MAJOR7",
                    "M9": "MAJOR9",
                    "m6": "MINOR6",
                    "m7": "MINOR7",
                    "m9": "MINOR9"
                }
                chord_type = chord_types_two_letters.get(remaining_input, chord_type)

            # Check three-letter+ notations
            elif len(remaining_input) >= 3:
                chord_types_three_letters = {
                    "sus": "SUS4",
                    "sus4": "SUS4",
                    "sus2": "SUS2",
                    "dim": "DIMINISHED",
                    "dim7": "DIMINISHED"
                }
                chord_type = chord_types_three_letters.get(remaining_input, chord_type)

                # Check for test chord inputs
                if remaining_input.startswith("TEST"):
                    test_number = remaining_input[4:]
                    if test_number.isdigit():
                        chord_type = f"TEST{test_number}"
                        print(f"test {test_number} accepted")

        # Read chord from csv
        note = str.upper(chords[0])
        frets, command, dtraj, utraj = ArmListParser._get_chords_M("Alternate_Chords.csv", note + key, chord_type)

        return frets, command, dtraj, utraj, note, key, chord_type

    @staticmethod
    def parseleftMIDI(chords):
        lh_events = []
        for curr_chord in chords:
            note = curr_chord[0][0]
            timestamp = curr_chord[1]
            timestamp = round(timestamp * 200) / 200

            # Parse the chord
            chord_input = note + curr_chord[0][1:]
            frets, command, dtraj, utraj, parsed_note, key, chord_type = ArmListParser.parse_chord(chord_input)

            lh_events.append(["LH", [frets, command], timestamp])

        lh_motor_positions = []
        slider_mm_values = [19, 54, 87, 114, 141, 165, 188, 212, 234]
        # slider_mm_values = [23, 23, 23, 23, 23, 23, 23, 23, 23] # for testing
        slider_encoder_values = []
        mult = -1
        for value in slider_mm_values:
            encoder_tick = (value * 2048) / 9.4 - 2000
            slider_encoder_values.append(encoder_tick)

        presser_encoder_values = [-500, 500, 100]
        # presser_encoder_values = [-10, -10, -10] # for testing
        for events in lh_events:
            # for lh_events[1][0] AND for lh_events[1][1]
            # convert from fret position/finger position to encoder tick position respectively
            temp = [[]]
            # make motors 1,4,5 negative
            for i, slider_value in enumerate(events[1][0]):
                mult = -1
                if i == 1 or i == 2 or i == 5:
                    mult = 1
                if 1 <= slider_value <= 9:
                    temp[0].append(slider_encoder_values[slider_value - 1] * mult)
            for i, presser_value in enumerate(events[1][1]):
                if 1 <= presser_value <= 3:
                    temp[0].append(presser_encoder_values[presser_value - 1])
            temp.append(events[2])
            lh_motor_positions.append(temp)

        return lh_motor_positions

    @staticmethod
    def parsePickMIDI(picks):
        pick_events = []
        slide_toggles = []
        # MIDI note ranges for each string
        # string_ranges = [ # for all pluckers
        #     (40, 50),  # String 1
        #     (45, 55),  # String 2
        #     (50, 60),  # String 3
        #     (55, 65),  # String 4
        #     (59, 69),  # String 5
        #     (64, 74)   # String 6
        # ]
        string_ranges = [  # for plucker prototype 1
            (40, 49),  # String 1
            (50, 58),  # String 3
            (59, 68),  # String 5
        ]

        tremolo_threshold = .5

        active_pickers = [-.5] * len(string_ranges)
        last_notes = [None] * len(string_ranges)
        for note, duration, speed, slide_toggle, timestamp in picks:
            slide_toggles.append(slide_toggle)
            assigned = False
            timestamp = round(timestamp * 200) / 200
            duration = round(duration, 3)
            if duration < tremolo_threshold:
                duration = .025

            for pickerID, (low, high) in enumerate(string_ranges):
                # print("Active Pickers: ", active_pickers)
                if low <= note <= high:  # Check if the note falls within the string's range
                    if last_notes[pickerID] == note:
                        # If the note is the same as the last one on this picker, only check if it's free
                        if timestamp >= active_pickers[pickerID]:
                            assigned = True
                    else:
                        # If the note is different, check for 325ms gap (300 to slide and press, 25 to pluck)
                        if timestamp >= active_pickers[pickerID] and timestamp - 0.325 >= active_pickers[pickerID]:
                            assigned = True

                    if assigned:
                        # end = timestamp + duration
                        end = timestamp
                        pick_events.append(["pick", [pickerID, note, duration, speed, timestamp]])
                        active_pickers[pickerID] = end
                        last_notes[pickerID] = note
                        # print(f"Assigning Picker {pickerID} for note {note}")
                        break

            if not assigned:
                print(f"Warning: No available picker for note {note} at timestamp {timestamp}")

        # pick_events = [["pick", [MotorID, midival, duration,  timestamp]]]

        pick_motor_positions = []
        # [[[motor_ID, qf_encoder_picker, duration, speed] * num_pickers], timestamp]],]
        num_pickers = 3
        pickerStates = [
                           1] * num_pickers  #TODO: Need to keep track of this at the end of songs similar to LH and RH last positions
        motorInformation = {  # motor_id : [down_pluck mm, up_pluck mm]
            0: [3, 7, 1024],
            1: [0, 3.5, 2048],
            2: [4, 7, 2048]
        }
        for event in pick_events:
            motor_id = event[1][0]
            note = event[1][1]
            duration = round(event[1][2], 3)
            speed = round(event[1][3])
            timestamp = event[1][4]
            timestamp = round(timestamp * 200) / 200
            curr_event = [motor_id, note, 0, duration, speed]
            # 1. Get Motors that need to slide and press.
            slide_MotorID = motor_id + 6
            press_MotorID = motor_id + 12
            # 2. Get the timestamp that the event should happen.
            lh_tmstmp = timestamp - .325

            if duration < tremolo_threshold:
                pick_state = pickerStates[motor_id]
                qf_mm = int(motorInformation[motor_id][not pick_state])
                pos2pulse = (qf_mm * motorInformation[motor_id][2]) / 9.4
                curr_event[2] = round(pos2pulse, 3)
                pickerStates[motor_id] = not pick_state
            else:
                pick_state = pickerStates[motor_id]
                qf_mm = int(motorInformation[motor_id][pick_state])
                pos2pulse = (qf_mm * motorInformation[motor_id][2]) / 9.4
                curr_event[2] = round(pos2pulse, 3)
            full_event = [curr_event, timestamp]
            pick_motor_positions.append(full_event)

        return pick_motor_positions, slide_toggles

    @staticmethod
    def prepPicker(lh_motor_positions, pick_motor_positions):
        pick_motor_positions_prepped = []
        lh_index = 0

        for pick_element in pick_motor_positions:
            pick_timestamp = pick_element[1]
            overlap = False

            # Check for overlapping left-hand events
            while lh_index < len(lh_motor_positions) and lh_motor_positions[lh_index][1] <= pick_timestamp + 0.300:
                lh_timestamp = lh_motor_positions[lh_index][1]
                if abs(pick_timestamp - lh_timestamp) <= 0.300:
                    overlap = True
                    break
                lh_index += 1

            # If no overlap, add the pick event
            if not overlap:
                pick_motor_positions_prepped.append(pick_element)

        return pick_motor_positions_prepped

    @staticmethod
    def interpPick(pick_events, slide_toggles, initial_point, num_points=20, tb_cent=0.2):
        # initial_point = [762, 873, 1743]  # encoder ticks for Low E and D strings
        initial_point = initial_point[12:]
        current_positions = initial_point.copy()
        result = {}
        motorInformation = {  # motor_id : [down_pluck mm qf, up_pluck mm qf, encoder resolution]
            0: [3.75, 7.5, 1024],
            1: [0, 3.5, 2048],
            2: [2.5, 6, 2048]
        }
        # NEED TO HANDLE SLIDER/PRESSER
        pick_states = [1, 1, 1, 1, 1, 1]  # curr states positions initialized as all 'up'
        #pick_states = [0, 0, 0, 0, 0, 0]
        events_list = []
        lh_pick_events = []

        for i, event in enumerate(pick_events):
            picker_actions, timestamp = event[0], event[1]
            event_points = [0]
            motor_id, note, qf_encoder_picker, duration, speed = event[0]
            is_pluck = duration < 0.500

            start_pos = current_positions[motor_id]

            if is_pluck:
                # Single pluck
                pick_states[motor_id] = not pick_states[motor_id]
                qf_encoder_picker = (motorInformation[motor_id][pick_states[motor_id]] * motorInformation[motor_id][
                    2]) / 9.4

                all_points = ArmListParser.interp_with_blend(start_pos, qf_encoder_picker, 11, tb_cent)
                # print("pluck on ", motor_id, " ", timestamp, " ", duration)
                events_list.append([all_points, motor_id, timestamp])
            else:
                # Tremolo # CHANGE TO SIN WAVE
                # picker 1, change to dictionary of values for all 6 motors
                # max_mm, min_mm = motorInformation[motor_id][0:2]  # 3, 7, or 0, 4
                # max_encoder = (max_mm * motorInformation[motor_id][2]) / 9.4
                # min_encoder = (min_mm * motorInformation[motor_id][2]) / 9.4
                #
                # print("Max, min", max_encoder, min_encoder)
                # vert_shift = (max_encoder + min_encoder) / 2  # 544
                # print("Vertical Shift: ", vert_shift)
                #
                # max_amp = abs((max_encoder - min_encoder))/2  # Default: 218 for picker 1
                # min_amp = max_amp * 0.80
                # #min amplitude for picker 1 needed is 225
                # # Amplitude Scaling
                # #amp = ArmListParser.scaleAmplitude(max_amp, min_amp, speed) #TODO: Double Check amplitude calculation
                # amp = min_amp
                # print("Amplitude", amp)
                #
                # all_points = ArmListParser.maketremolo(vert_shift, amp, duration, speed, pick_states[motor_id])

                # Slowest number of points is .300 seconds between evens  = 60 points
                # fastest number of points 5 point (25 ms)
                fill_points = min(30, int(30 - (speed - 1) * (25 / 9))) - 4
                num_tremolos = math.floor(duration / (((fill_points * .005) + .055) * 2))
                qf_encoder_picker = (motorInformation[motor_id][not pick_states[motor_id]] * motorInformation[motor_id][
                    2]) / 9.4
                all_points = []
                for _ in range(num_tremolos):
                    # 11 is a good value for all
                    # Changing it too much conflicts with fill points for speed
                    num_points = 11
                    points1 = ArmListParser.interp_with_sine_blend(start_pos, qf_encoder_picker, num_points)  # (move)
                    points2 = ArmListParser.interp_with_sine_blend(qf_encoder_picker, qf_encoder_picker,
                                                                   fill_points)  # (fill)
                    start_pos = (motorInformation[motor_id][pick_states[motor_id]] * motorInformation[motor_id][
                        2]) / 9.4
                    points3 = ArmListParser.interp_with_sine_blend(qf_encoder_picker, start_pos, num_points)  # (move)
                    points4 = ArmListParser.interp_with_sine_blend(start_pos, start_pos, fill_points)  # (fill)

                    all_points.extend(points1)
                    all_points.extend(points2)
                    all_points.extend(points3)
                    all_points.extend(points4)

                events_list.append([all_points, motor_id, timestamp])

            # Update the event_points for this motor
            current_positions[motor_id] = all_points[-1]
            # [Slider_MotorID, enc_val target position, TS]
            # max midi_va for MotorID - note
            # string_ranges = [ # Forall Pluckers
            #     (40, 50, -1),  # String 1
            #     (45, 55,  1),  # String 2
            #     (50, 60,  1),  # String 3
            #     (55, 65, -1),  # String 4
            #     (59, 69, -1),  # String 5
            #     (64, 74,  1)   # String 6
            # ]
            string_ranges = [  # for plucker prototype 1
                (40, 49, -1),  # String 1
                (50, 58, 1),  # String 3
                (59, 68, -1),  # String 5
            ]

            slider_mm_values = [19, 54, 87, 114, 141, 165, 188, 212, 234]
            # slider_mm_values = [23, 23, 23, 23, 23, 23, 23, 23, 23] # for testing

            # LH Pick Events Format: [[motor ID, lh qf encoder value, slide toggle, timestamp]]
            fret = note - string_ranges[motor_id][0]
            if fret == 0:
                lh_enc_val = -1
            else:
                lh_enc_val = ((slider_mm_values[fret - 1] * 2048) / 9.4 - 2000) * string_ranges[motor_id][2]
            curr_lhp_event = [motor_id, lh_enc_val, slide_toggles[i],
                              timestamp - .4]  # assumes 80 points for lh movement
            lh_pick_events.append(curr_lhp_event)

        # initialize dictionary with initial point for every .005 ms for every point
        # Find max timestamp by looping through events and determining end times
        max_timestamp = 0
        max_timestamp_event = None
        for i, pick_event in enumerate(events_list):
            timestamp = pick_event[2]
            duration = 0.005 * len(pick_event[0])
            event_time = round((timestamp + duration) * 200) / 200
            # print("Current Max Timestamp: ", max_timestamp, max_timestamp_event)
            # print("Current Event Time: ", event_time)
            if event_time > max_timestamp:
                max_timestamp = event_time
                max_timestamp_event = i

        #max_timestamp = events_list[-1][2] + (.005 * len(events_list[-1][0]))
        # print("Max Timestep + event: ", max_timestamp, max_timestamp_event)
        curr_timestamp = 0
        while curr_timestamp <= max_timestamp:
            #print("Initial Point: ", initial_point)
            result[curr_timestamp] = initial_point.copy()  # be careful, changing to a list will change all elements!
            curr_timestamp = round(curr_timestamp + .005, 3)
        for event in events_list:
            points, id, timestamp = event
            curr = round(timestamp * 200) / 200
            for p in points:
                result[curr][id] = p
                curr = round(curr + .005, 3)
                prev_pos = p
            while curr <= max_timestamp:
                result[curr][id] = prev_pos
                curr = round(curr + .005, 3)
        print("LH PICK EVENTS: ", lh_pick_events)
        return result, lh_pick_events

    @staticmethod
    def scale_speed(value):
        usermin = 1
        usermax = 10
        fastest = 0.025
        slowest = 0.15
        scaled = (10 + 2 * ((slowest / 0.005) - (value - 1) * ((fastest * 1000) / (usermax - usermin)))) * 0.005

        return scaled

    @staticmethod
    def tremolocos(curT, period, amp, vert_shift, pick_state):
        if pick_state == 1:
            tremolo_s = vert_shift + amp * math.cos((2 * math.pi * (curT)) / period)
        else:
            tremolo_s = vert_shift + amp * -math.cos((2 * math.pi * (curT)) / period)
        return tremolo_s  #produces one tremolo point at a time

    @staticmethod
    def maketremolo(vert_shift, amp, duration, speed, pick_state):  # Todo: Test case of starting at 326, should work
        # print("Duration: ", duration)
        # Calculate the period based on the user's inputted speed value 1-10
        period = ArmListParser.scale_speed(speed)
        # print("period: ", period)
        # print("frequency: ", 1/period)
        # Determine max number of tremolos we can achieve in the duration for the given speed
        tstep = 0.005
        num_tremolos = (duration // period)  # amount of tremolos we can do and end at the top or bottom
        # print("Max number of tremolos: ", num_tremolos)
        # Interpolate the cosine wave for every point in num_tremolos
        trem_times = np.arange(0, (num_tremolos * period) + tstep, tstep)
        #print("Times: ", trem_times)
        tremoloArray = [ArmListParser.tremolocos(t, period, amp, vert_shift, pick_state) for t in trem_times]
        #fullarray[:len(tremoloArray)] = tremoloArray
        #print("Tremolo Points: ", tremoloArray)

        # Add in a fill at the very end if needed
        end_fill = duration - trem_times[-1]
        fill_array = []
        if end_fill > 0:
            fill_array = np.full(int(period // 0.005),
                                 ArmListParser.tremolocos(trem_times[-1], period, amp, vert_shift, pick_state))
            # print("Fill array: ", fill_array)
        tremoloArray.extend(fill_array)
        # print("Full Tremolo Array: ", tremoloArray)

        return tremoloArray

    @staticmethod
    def scaleAmplitude(max_amplitude, min_amplitude, speed):
        print("Max Amplitude, Min Amplitude: ", max_amplitude, min_amplitude)
        low_speed = 1
        high_speed = 10
        scaledAmp = max_amplitude + ((speed - low_speed) / (high_speed - low_speed)) * (min_amplitude - max_amplitude)
        return scaledAmp

    @staticmethod
    def interp_with_sine_blend(start_pos, end_pos, num_points):
        t = np.linspace(0, np.pi, num_points)
        blend = (1 - np.cos(t)) / 2
        points = (1 - blend) * start_pos + blend * end_pos

        return points
