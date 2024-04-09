import json
import os.path
import tkinter.messagebox
from tkinter.filedialog import askopenfilename

class JsonHelper:
    @staticmethod
    def write_song_to_json(song_title, time_signature, bpm, chord_mode, song_order, sections):
        # check to make sure that user does not accidentally overwrite existing song
        if song_title != "default" and os.path.isfile('./UI/songs/' + song_title + '.json'):
            response = tkinter.messagebox.askquestion("Warning",
                                                      "A song with the same name is already saved. Would you like to overwrite the " +
                                                      "contents of the existing song? (If you select no, song will be saved as a new file.)")
            if response == 'no':
                song_title = song_title + "(1)"

        # organize general song data
        song_dict = {
            "song_title": song_title,
            "time_signature": time_signature,
            "bpm": bpm,
            "chord_mode": chord_mode,
            "song_order": song_order
        }

        json_data = []
        json_data.append(song_dict)

        # add individual section data to json_data
        for section in sections:
            section_dict = {}
            section_dict["name"] = section.name
            section_dict["num_measures"] = section.num_measures
            section_dict["strum_pattern"] = section.strum_pattern if section.strum_pattern != "Strum Pattern" else "Custom" # if user didn't select a strum pattern, set to "Custom"
            section_dict["left_arm"] = section.left_arm
            section_dict["right_arm"] = section.right_arm
            json_data.append(section_dict)

        with open('./UI/songs/' + song_title + '.json', 'w') as file:
            # write data to json
            file.write(json.dumps(json_data, indent=4))

    # TODO
    @staticmethod
    def load_song_from_json():
        path = askopenfilename()
        print(str(path))
        with open(path, 'r') as file:
            json_data = json.load(file)

        # set general song data
        song_dict = json_data.pop(0)

        # update UI components
        songTitle.delete(0, END)
        songTitle.insert(0, song_dict["name"])
        songInput.delete(0, END)
        songInput.insert(0, song_dict["input"])
        bpmInput.delete(0, END)
        bpmInput.insert(0, song_dict["bpm"])
        timeSelection.set(song_dict["timeSig"])

        # reset UI to initial state
        update_table(None)

        # create and populate sections with data
        count = 0
        for section_dict in json_data:
            if count == 0:
                section = initSection
            else:
                section = add_section()

            section.name = section_dict["name"]
            section.nameInput.insert(0, section.name)

            for i in range(1, int(section_dict["numMeasures"])):
                add_measure(section)

            section.strumPattern.set(section_dict["strumPattern"])
            # flatten input arrays
            leftArm = [item for sublist in section_dict["leftArm"] for item in sublist]
            rightArm = [item for sublist in section_dict["rightArm"] for item in sublist]
            section.insertChordStrumData(leftArm, rightArm)
            count += 1