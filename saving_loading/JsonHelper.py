import json
import os.path
import tkinter.messagebox
from tkinter.filedialog import askopenfilename

class JsonHelper:
    @staticmethod
    # Save song data in JSON format 
    def write_song_to_json(song_title, time_signature, bpm, chord_mode, ordered_section_ids, sections):
        # check to make sure that user does not accidentally overwrite existing song
        if song_title != "default" and os.path.isfile('../UI/songs/' + song_title + '.json'):
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
            "ordered_section_ids": ordered_section_ids
        }

        json_data = []
        json_data.append(song_dict)

        # add individual section data to json_data
        for section in sections:
            section_dict = {}
            section_dict["id"] = section.id
            section_dict["name"] = section.name
            section_dict["num_measures"] = section.num_measures
            section_dict["strum_pattern"] = section.strum_pattern if section.strum_pattern != "Strum Pattern" else "Custom" # if user didn't select a strum pattern, set to "Custom"
            section_dict["left_arm"] = section.left_arm
            section_dict["right_arm"] = section.right_arm
            json_data.append(section_dict)

        with open('../UI/songs/' + song_title + '.json', 'w') as file:
            # write data to json
            file.write(json.dumps(json_data, indent=4))

    @staticmethod
    # Load song data from JSON file
    # Returns song_dict, section_dicts[] which contain song and sections data
    def load_song_from_json():
        path = askopenfilename()
        # print(str(path))
        with open(path, 'r') as file:
            json_data = json.load(file)

        # get general song data
        song_dict = json_data.pop(0)

        # get sections data
        section_dicts = []
        for section_dict in json_data:
            section_dicts.append(section_dict)

        return song_dict, section_dicts