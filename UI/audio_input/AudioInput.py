# from ChordRecognition.ISMIR_LVCR.chord_recognition import chord_recognition
# from ChordRecognition.audioInput import inputAudio

chordtype_uichordtype = {
    'min/b7' : 'm',
    'min/2'  : 'm',
    'maj/b7' : '',
    'maj/2'  : '',
    'sus4(b7)' : 'sus4',
    "sus2" : 'sus2',
    "sus4" : 'sus4',
    "13" : '13',
    "11" : '11',
    "min9" : 'm9',
    "9" : '9',
    "maj9" : 'M9',
    "dim7" : 'dim7',
    "hdim7" : 'o',
    "min7" : 'm7',
    "7" : '7',
    "maj7" : 'M7',
    "min/5" : 'm',
    "min/b3" : 'm',
    "maj/5" : '',
    "maj/3" : '',
    "dim" : 'dim',
    "aug" : '+',
    "min" : 'm',
    "maj" : ''
}
def record_left_arm(self):
        # # ad = inputAudio(waveName='output.mp3')
        # # ad.start()
        # # ad.outputWav()

        # ui_left_arm = []

        # chord_rows = chord_recognition('output.mp3')
        # # chord_rows = [['C:maj7'], ['D:dim7'], ['E:hdim7'], ["F:maj"]] # should be output of the model

        # for chord_row in chord_rows:
        #     chordname = chord_row[0]

        #     chordnote, chordtype = chordname[0:chordname.index(':')], chordtype_uichordtype[chordname[chordname.index(':')+1:]]

        #     uichordname = chordnote + chordtype
        #     ui_left_arm.append(uichordname)

        # return ui_left_arm

    return [['C', '', '', ''], ['D', '', '', '']]


# def main():
#     my_list = record_for_UI()
#     print(my_list)

# main()