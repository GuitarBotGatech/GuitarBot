import pandas as pd

class ArmListParser:
    @staticmethod
    def get_chords_M(directory, chord_letter, chord_type):
        df_chords = pd.read_csv(directory)
        for new_x in range(334):
            if df_chords.iloc[new_x][0] == chord_letter:
                if df_chords.iloc[new_x][1] == chord_type:
                    x = new_x
                    break
        ftraj = False
        dtraj = []
        utraj = []
        try:
            s1 = int(df_chords.iloc[x][3])
            dtraj = [0, 6]
            utraj = [6, 0]
            ftraj = True
        except:
            s1 = -1
        try:
            s2 = int(df_chords.iloc[x][4])
            if ftraj == False:
                dtraj = [1, 6]
                utraj = [6, 1]
                ftraj = True
        except:
            s2 = -1

        try:
            s3 = int(df_chords.iloc[x][5])
            if ftraj == False:
                dtraj = [2, 6]
                utraj = [6, 2]
                ftraj = True
        except:
            s3 = -1
        try:
            s4 = int(df_chords.iloc[x][6])
            if ftraj == False:
                dtraj = [3, 6]
                utraj = [6, 3]
                ftraj = True
        except:
            s4 = -1
        try:
            s5 = int(df_chords.iloc[x][7])
            if ftraj == False:
                dtraj = [4, 6]
                utraj = [6, 4]
                ftraj = True
        except:
            s5 = -1
        try:
            s6 = int(df_chords.iloc[x][8])
            if ftraj == False:
                dtraj = [5, 6]
                utraj = [6, 5]
                ftraj = True
        except:
            s6 = -1
        fret_numbers = [s1, s2, s3, s4, s5, s6]
        fret_play = []
        if fret_numbers[0] == 0:
            fret_numbers[0] += 1
            fret_play.append(1)
        elif fret_numbers[0] == -1:
            fret_numbers[0] = 1
            fret_play.append(3)
        else:
            fret_play.append(2)

        if fret_numbers[1] == 0:
            fret_numbers[1] += 1
            fret_play.append(1)
        elif fret_numbers[1] == -1:
            fret_numbers[1] = 1
            fret_play.append(3)
        else:
            fret_play.append(2)

        if fret_numbers[2] == 0:
            fret_numbers[2] += 1
            fret_play.append(1)
        elif fret_numbers[2] == -1:
            fret_numbers[2] = 1
            fret_play.append(3)
        else:
            fret_play.append(2)

        if fret_numbers[3] == 0:
            fret_numbers[3] += 1
            fret_play.append(1)
        elif fret_numbers[3] == -1:
            fret_numbers[3] = 1
            fret_play.append(3)
        else:
            fret_play.append(2)

        if fret_numbers[4] == 0:
            fret_numbers[4] += 1
            fret_play.append(1)
        elif fret_numbers[4] == -1:
            fret_numbers[4] = 1
            fret_play.append(3)
        else:
            fret_play.append(2)

        if fret_numbers[5] == 0:
            fret_numbers[5] += 1
            fret_play.append(1)
        elif fret_numbers[5] == -1:
            fret_numbers[5] = 1
            fret_play.append(3)
        else:
            fret_play.append(2)
        print(fret_numbers, fret_play)
        print(dtraj, utraj)
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
        print("ri", right_information, initialStrum)
        return right_information, initialStrum, strumOnsets

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
                        if key != '#' or key != 'b':
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

                            #TODO: split these into individual chords once chords library is updated
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

                            #TODO: split these into individual chords once chords library is updated
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
                    frets, command, dtraj, utraj = ArmListParser.get_chords_M("Chords - Chords.csv", note + key, type)
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
        for m in left_arm:
            for b in m:
                if b == '':
                    continue
                else:
                    justchords.append(b)
        print("jc", justchords)
        # return left_arm, firstc, mtimings
        return justchords, firstc, mtimings