from constants.bot_specs import DEFAULT_BPM, MIN_BPM, MAX_BPM
from constants.time_signatures import DEFAULT_TIME_SIG
from constants.chord_modes import DEFAULT_CHORD_MODE
from models.Section import Section

# model stores all of the UI's data
class Model:
    def __init__(self):
        self.song_title = 'Song Title'

        # TODO: add logic to limit bpm to MIN_BPM, MAX_BPM range and update view accordingly
        self.bpm = DEFAULT_BPM

        self.time_signature = DEFAULT_TIME_SIG
        self.chord_mode = DEFAULT_CHORD_MODE

        self.sections = {} # Key-value pairs of form {id, Section}

    # Called by Controller, adds a new section to the Model
    def add_section(self, section_id, name):
        new_section = Section(section_id, name) # left_arm, right_arm will be initialized to empty lists
        self.sections[section_id] = new_section

    def update_song_data(self, song_title, bpm, time_signature, chord_mode):
        self.song_title = song_title
        self.bpm = bpm
        self.time_signature = time_signature
        self.chord_mode = chord_mode

    # Called by Controller, updates the data for a particular section (indexed by id)
    # Data includes name and left_arm, right_arm lists
    def update_section_data(self, section_id, left_arm, right_arm, name=None, strum_pattern=None, num_measures=None):
        section = self.sections[section_id]

        # update optional fields
        if name is not None:
            section.name = name
        if strum_pattern is not None:
            section.strum_pattern = strum_pattern
        if num_measures is not None:
            section.num_measures = num_measures

        section.left_arm = left_arm
        section.right_arm = right_arm

    # Called by Controller, removes a particular section (indexed by id)
    def remove_section(self, section_id):
        self.sections.pop(section_id)