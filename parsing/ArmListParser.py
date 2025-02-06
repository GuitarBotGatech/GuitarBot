import numpy as np
import matplotlib.pyplot as plt
from parsing.chord_selector import find_lowest_cost_chord


class ArmListParser:
    current_fret_positions = [0, 0, 0, 0, 0, 0]  # begins by preferring voicings near first position

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
                dtraj = [i+1, 6]
                utraj = [6, i+1]
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

        print(fret_numbers, fret_play)
        print(dtraj, utraj)

        return fret_numbers, fret_play, dtraj, utraj

    # parse right arm (strums) input
    @staticmethod
    def parseright_M(right_arm, intervals, measure_time):
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
                            intervals[mra][bra] = intervals[mra][bra][0]
                        if beat == "U":
                            strumOnsets.append([time, 'U', 'N'])
                            right_information[mra][bra] = [beat, "N", measure_time / 8, 1]  # Change strum time here
                            intervals[mra][bra] = intervals[mra][bra][1]
                        if beat == "":
                            bra += 1
                            continue

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
                        intervals[mra][bra] = intervals[mra][bra][1]
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
                        intervals[mra][bra] = intervals[mra][bra][0]
                        if right_information[pmra][pbra][0] == "D":
                            right_information[pmra][pbra][1] = "C"
                        right_information[pmra][pbra][3] = deltaT
                        pmra -= pmra
                        pmra += mra
                        pbra -= pbra
                        pbra += bra
                        deltaT = 0
                    if beat == "":
                        intervals[mra][bra] = ''
                else:
                    print(right_information, mra, bra)
                    raise Exception("Right Arm input incorrect")
                bra += 1
                time += (measure_time / 8)
                # print(right_information, mra, bra, "loop")
                deltaT += measure_time / 8
            mra += 1
        print("strum onsets: ", strumOnsets)
        print("right hand: ", right_information)
        print("strum intervals: ", intervals)

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
            timestamp = round(x[0] * 200) / 200 # Rounding to nearest 0.005 = PDO_RATE
            rh_events.append(['strum', [pos, 75, deflect], timestamp]) # Later, 75 is default speed, change later
            prev_strum = x[1] #For detecting deflects
        print("LEN RH: ", len(rh_events))
        # print("ri", right_information, initialStrum)
        #print("These are the strumOnsets: ", strumOnsets)
        #print("These are the right hand events: ", rh_events)
        print("RH EVENTS LIST: ")
        ArmListParser.print_Events(rh_events)

        strummer_dict = {
            -45: [-115, 8], #US
            45: [-15, 10] # DS
        }

        rh_motor_positions = []
        deflections = []

        for event in rh_events:
            strumType = event[1][0] # 45 or -45
            speed = event[1][1] # 75
            deflect = event[1][2] # 0 or 1
            time_stamp = event[2]
            strum_mm_qf = strummer_dict.get(strumType)[0] # -115 or -15
            picker_mm_qf = strummer_dict.get(strumType)[1]
            if deflect == 1:
                deflections.append(1)
            else:
                deflections.append(0)
            rh_motor_positions.append([[strum_mm_qf, picker_mm_qf], time_stamp])

        print("\nRH MM:")
        ArmListParser.print_Events(rh_motor_positions)
        print("DEFLECTIONS LIST: ", deflections)
        rh_interpolated_dictionary = ArmListParser.rh_interpolate(rh_motor_positions, deflections)
        #print(rh_interpolated_list)
        #ArmListParser.print_Trajs(rh_interpolated_list)

        # return rh_events, initialStrum, strumOnsets
        return rh_interpolated_dictionary

    # parse left arm (chords) input
    @staticmethod
    def parseleft_M(left_arm, measure_time):
        firstc = []
        firstcfound = False
        mcount = 0
        mtimings = []
        time = 0
        intervals = [['']*8 for i in range(len(left_arm))]
        prevStrum = ''

        for measure in left_arm:
            bcount = 0
            scount = 0
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
                    prevStrum = [dtraj, utraj]
                    mtimings.append(time)
                    if not firstcfound:
                        firstc.append(frets)
                        firstc.append(command)
                        firstcfound = True
                intervals[mcount][scount] = prevStrum
                intervals[mcount][scount + 1] = prevStrum
                time += measure_time / 4
                bcount += 1
                scount += 2
            mcount += 1
        print("queue: ", mtimings)
        print("left arm: ", left_arm)
        print("strum intervals: ", intervals)
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
                    timestamp = round(mtimings[i] * 200) /200 # Rounding to nearest 0.005 = PDO_RATE
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

        presser_encoder_values = [-10, 38, 23]
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
        #print("LH EVENTS LIST: ")
        ArmListParser.print_Events(lh_motor_positions)
        #print("\n")
        lh_interpolated_dictionary = ArmListParser.lh_interpolate(lh_motor_positions, plot=False)

        #ArmListParser.print_Trajs(lh_interpolated_list)



        # Debugging
        # for entry in interpolated_list:
        #     for x in entry[0]:
        #         print(x)
        #     print(f"Timestamp: {entry[1]}\n")

        #print("These are the encoder tick slider/presser positions: ", lh_motor_positions)
        # return left_arm, firstc, mtimings
        # return lh_events, firstc, mtimings
        return lh_interpolated_dictionary, intervals

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
    def lh_interpolate(lh_motor_positions, num_points=20, tb_cent=0.2, plot=False):
        initial_point = [0, 0, 0, 0, 0, 0, -10, -10, -10, -10, -10, -10]  # Initial position, remember to make dynamic later.
        current_encoder_position = []
        for i, value in enumerate(initial_point):
            if i < 6:
                encoder_tick = (value * 2048) / 9.4
                current_encoder_position.append(encoder_tick)
            else:
                current_encoder_position.append(value)

        result = []
        points_only = []

        #1. Check to make sure no syncrhonous LH Events
        print("LH UPDATED EVENTS LIST (NO SYNC LH EVENTS): ")
        lh_motor_positions = ArmListParser.checkSyncEvents("LH", lh_motor_positions)
        ArmListParser.print_Events(lh_motor_positions)

        for event_index, event in enumerate(lh_motor_positions):
            points = []
            target_positions_slider = event[0][:6]  # First 6 values of the nested list
            target_positions_presser = event[0][6:12]
            timestamp = event[1]
            # First 20 points
            interpolated_values_1 = [
                ArmListParser.interp_with_blend(current_encoder_position[i], current_encoder_position[i], num_points, tb_cent) #Change to fill later
                for i in range(len(target_positions_slider))
            ]

            interpolated_points_1 = list(map(list, zip(*interpolated_values_1)))
            interpolated_values_2 = [
                ArmListParser.interp_with_blend(current_encoder_position[i+6], -10, num_points, tb_cent)
                for i in range(len(target_positions_presser))
            ]
            interpolated_points_2 = list(map(list, zip(*interpolated_values_2)))

            f_20 = [points1 + points2 for points1, points2 in zip(interpolated_points_1, interpolated_points_2)]
            points.extend(f_20)

            # Second 20 points
            interpolated_values_3 = [
                ArmListParser.interp_with_blend(current_encoder_position[i], target_positions_slider[i], num_points, tb_cent)
                for i in range(len(target_positions_slider))
            ]
            interpolated_points_3 = list(map(list, zip(*interpolated_values_3)))
            interpolated_values_4 = [
                ArmListParser.interp_with_blend(-10, -10, num_points, tb_cent) #Change to fill later
                for i in range(len(target_positions_presser))
            ]
            interpolated_points_4 = list(map(list, zip(*interpolated_values_4)))

            s_20 = [points1 + points2 for points1, points2 in zip(interpolated_points_3, interpolated_points_4)]
            points.extend(s_20)

            # Third 20 points
            interpolated_values_5 = [
                ArmListParser.interp_with_blend(target_positions_slider[i], target_positions_slider[i], num_points, tb_cent) # Change to fill later
                for i in range(len(target_positions_slider))
            ]
            interpolated_points_5 = list(map(list, zip(*interpolated_values_5)))
            interpolated_values_6 = [
                ArmListParser.interp_with_blend(-10, target_positions_presser[i], num_points, tb_cent)
                for i in range(len(target_positions_presser))
            ]
            interpolated_points_6 = list(map(list, zip(*interpolated_values_6)))

            t_20 = [points1 + points2 for points1, points2 in zip(interpolated_points_5, interpolated_points_6)]

            points.extend(t_20)
            result.append([points, timestamp])
            points_only.append([points])
            #print("\n")
            #print("debug_1", points)
            #print("debug_2", len(result))
            current_encoder_position = event[0]

        print("\nLH FULL MATRIX")
        matrix = ArmListParser.getFullMatrix(result, initial_point, plot = True)
        if plot:
            ArmListParser.plot_interpolation(result, 12)
        return matrix #result

    @staticmethod
    def rh_interpolate(rh_motor_positions, deflections, tb_cent = 0.2):
        initial_point = [-23965, 1960] # remember to change to dynamic later
        strummer_slider_q0 = -23965 # encoder ticks, CURRENT POINTS
        strummer_picker_q0 = 1960
        rh_points = []
        rh_points_only = []
        prev_timestamp = 0
        speed = 40

        #1. Check for any deflections
        rh_motor_positions = ArmListParser.checkDeflect(rh_motor_positions, deflections)
        print("RH UPDATED EVENTS LIST (WITH DEFLECTIONS): ")
        ArmListParser.print_Events(rh_motor_positions)

        #2. Check for any syncrhonous RH events
        rh_motor_positions = ArmListParser.checkSyncEvents("strum", rh_motor_positions)
        print("RH UPDATED EVENTS LIST (NO SYNC RH EVENTS): ")
        ArmListParser.print_Events(rh_motor_positions)

        for event_index, event in enumerate(rh_motor_positions):
            strummer_slider_qf = event[0][0]
            strummer_slider_qf = (strummer_slider_qf * 2048) / 9.4
            strummer_picker_qf = event[0][1]
            strummer_picker_qf = (strummer_picker_qf * 2048) / 9.4
            timestamp = event[1]

            #1. Strummer slider hold 5 points
            strummer_slider_interp1 = ArmListParser.interp_with_blend(strummer_slider_q0, strummer_slider_q0, 5, tb_cent)  # Change to fill later
            #2. Strummer slider move "speed" points
            strummer_slider_interp2 = ArmListParser.interp_with_blend(strummer_slider_q0, strummer_slider_qf, speed, tb_cent)
            #3. Strummer Picker move 5 points
            strummer_picker_interp1 = ArmListParser.interp_with_blend(strummer_picker_q0, strummer_picker_qf, 5, tb_cent)
            #4. Strummer Picker hold "speed" points
            strummer_picker_interp2 = ArmListParser.interp_with_blend(strummer_picker_qf, strummer_picker_qf, speed, tb_cent)
            #5. Combine strummer_slider_interp1 with strummer_picker_interp1
            #picker_moving = [points1 + points2 for points1, points2 in zip(strummer_slider_interp1, strummer_picker_interp1)]
            interp_points_1 = [list(pair) for pair in zip(strummer_slider_interp1, strummer_picker_interp1)]
            interp_points_2 = [list(pair) for pair in zip(strummer_slider_interp2, strummer_picker_interp2)]
            interp_points_1.extend(interp_points_2)
            rh_points.append([interp_points_1, timestamp])
            rh_points_only.append([interp_points_1])

            strummer_slider_q0 = event[0][0]
            strummer_picker_q0 = event[0][1]

        #ArmListParser.print_Trajs(temp)
        #print("len is: ", len(rh_points))

        # ArmListParser.plot_interpolation(rh_points, 2)
        print("\nRH FULL MATRIX")
        matrix = ArmListParser.getFullMatrix(rh_points, initial_point, plot = True)

            # print("PICKER MOVING: ", x, "\n")

        return matrix




    @staticmethod
    def plot_interpolation(data = None, points = None, mode = "events", matrix = None):
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
    def getFullMatrix(events_list, initial_point, plot = True):

        full_matrix = {}
        full_matrix[0.000] = initial_point

        for event in events_list:
            points, timestamp = event
            # print("debug, ", points)
            # print("debug, ", timestamp)
            points = np.array(points)
            time_values = np.arange(len(points)) * 0.005 + timestamp  # 5ms per point
            for time, point in zip(time_values, points):
                full_matrix[round(time,3)] = point.tolist()

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
            i+=1
        if plot:
            ArmListParser.plot_interpolation(mode="matrix", matrix=full_matrix)
        return full_matrix

    # Will dynamically add deflect messages between events if there is enough space
    @staticmethod
    def checkDeflect(rh_motor_positions, deflections):
        prev_timestamp = -1000 # dummy initial value
        new_rh_motor_positions = []
        idx = 0
        num_deflections = 0
        total_strum_speed = 45 # 40 points for SS, 5 points for SP # CHANGE LATER
        buffer_time = 0.005 #seconds
        for event in rh_motor_positions:
            new_rh_motor_positions.append(event)
        for event_index, event in enumerate(rh_motor_positions):
            strummer_slider_qf = event[0][0]
            strummer_picker_qf = event[0][1]
            timestamp = event[1]
            if deflections[event_index] == 1:  # DEFLECT NEEDED BEFORE THIS EVENT
                # 1. Check to see if there's enough time for a deflect message before this event (speed + 5ms picker + 5ms buffer = 230ms)
                # There is enough space if time between events is > 2 * 230ms because 230ms to do first event, then another 230ms to deflect
                strum_time = (total_strum_speed * 0.005) + buffer_time #ms
                delta = round(timestamp - prev_timestamp, 3)
                required_delta = 2 * strum_time
                print(f"{timestamp} - {prev_timestamp} = {delta}")

                if delta > required_delta:  # Insert deflect message, TODO: ELSE, ignore the message because there's not enough time to deflect
                    num_deflections += 1
                    if strummer_slider_qf == -15: # if coming from a down strum, insert an upstrum
                        deflect_SS_qf = -115
                        deflect_SP_qf = 14
                    else:
                        deflect_SS_qf = -15
                        deflect_SP_qf = 14
                    # If deflection, add a deflect event right after the previous event
                    #print("INSERTING DEFLECTION BEFORE EVENT: ", idx)
                    new_rh_motor_positions.insert(idx, [[deflect_SS_qf, deflect_SP_qf], prev_timestamp + strum_time]) # add deflect event after first event finishes
                    idx+=1 # Because inserting into new list, need to increment properly to stay on track (double increment only when inserting)
                else: # NOT ENOUGH SPACE IN BETWEEN EVENTS TO DEFLECT SO IGNORE SECOND EVENT
                    print("Not enough space to deflect, ignoring event:", idx)
                    new_rh_motor_positions.pop(idx)
                    idx-=1

            idx+=1
            prev_timestamp = timestamp
        print("NUMBER OF DEFLECTIONS ADDED: ", num_deflections)

        return new_rh_motor_positions

    # This function checks if any SAME TYPE EVENTS are called too close together (RH/LH sync is handled elsewhere)
    @staticmethod
    def checkSyncEvents(event_type, motor_positions):
        prev_timestamp = -10000 # dummy initial value
        new_motor_positions = []
        for event in motor_positions:
            new_motor_positions.append(event)

        event_trajs = {
            "LH" : 60,
            "strum" : 45,
            "pick" : 5
        }
        idx = 0
        for event_index, event in enumerate(motor_positions):
            points, timestamp = event
            delta = round(timestamp - prev_timestamp, 3)
            required_delta = event_trajs.get(event_type) * 0.005 # The amount of time to complete the trajectory based on event type
            if delta < required_delta:
                new_motor_positions.pop(idx)
                print("Not enough space between events, ignoring event: ", idx)
                print("REQUIRED DELTA: ", required_delta)
                print(f"RESULTING DELTA: {timestamp} - {prev_timestamp} = {delta}")
                idx-=1

            idx+=1
            prev_timestamp = timestamp


        return new_motor_positions

    @staticmethod
    def parseAll(left_arm, right_arm,measure_time):
        #Initialize full dictionary
        allpoints = {}
        #Dictionaries for LH and RH
        print("These are the dictionaries for left arm")
        lh_dictionary, intervals = ArmListParser.parseleft_M(left_arm, measure_time)
        print("These are the dictionaries for right arm")
        rh_dictionary = ArmListParser.parseright_M(right_arm, intervals, measure_time)

        lh_maxtimestamp = max(lh_dictionary.keys())
        rh_maxtimestamp = max(rh_dictionary.keys())
        print("Key sizes:")
        print(lh_maxtimestamp)
        print(rh_maxtimestamp)
        if lh_maxtimestamp > rh_maxtimestamp:
            shorterDict = rh_dictionary
            highkey = lh_maxtimestamp
            lowkey = rh_maxtimestamp
            reset = "Right"
        else:
            shorterDict = lh_dictionary
            highkey = rh_maxtimestamp
            lowkey = lh_maxtimestamp
            reset = "Left"
        # Filling short matrix first
        last_point = shorterDict[lowkey]
        shorterDict[highkey] = last_point
        max_time = max(shorterDict.keys())

        # Create a list of all timestamps, including the original ones
        all_timestamps = sorted(set(list(shorterDict.keys()) +
                                    [round(t, 3) for t in np.arange(0, max_time + .005, .005)]))

        last_value = None

        # Iterate through all timestamps
        for timestamp in all_timestamps:
            if timestamp in shorterDict:
                last_value = shorterDict[timestamp]
            elif last_value is not None:
                # If it's an interpolated timestamp, use the last known value
                shorterDict[timestamp] = last_value

        # print resulting dictionary
        i = 0
        # print("Debuig Matrix: ")
        # for key, value in shorterDict.items():
        #     print(f"{i}| {key} : {value}")
        #     i += 1
        # shorterDict = dict(sorted(shorterDict.items()))
        lh_copied_dictionary = {}
        rh_copied_dictionary = {}
        if reset == "Left":
            lh_copied_dictionary = shorterDict
            combined_dict = {
                timestamp: lh_copied_dictionary[timestamp] + [
                    x for x in rh_dictionary[timestamp]
                ]
                for timestamp in lh_copied_dictionary
            }
        if reset == "Right":
            rh_copied_dictionary = shorterDict
            combined_dict = {
                timestamp: lh_dictionary[timestamp] + [
                    x for x in rh_copied_dictionary[timestamp]
                ]
                for timestamp in lh_dictionary
            }
        print("Full Matrix: ")
        for key, value in combined_dict.items():
            print(f"{i}| {key} : {value}")
            i += 1

        return combined_dict




