from Model import Model
from View import View, ChordNotationsPopup, HelpPopup
from constants.bot_specs import DEFAULT_BPM
# drag and drop
from vis_entities.DraggableSectionLabel import DraggableSectionLabel
# json saving/loading
from saving_loading.JsonHelper import JsonHelper
# preview functions
from preview.midi.ParserToMIDI import arms_to_MIDI
from preview.midi.PluginIntegration import play_midi_with_plugin
# messaging
from messaging.ArmListSender import ArmListSender
# threading
import threading

class Controller:
    def __init__(self, view: View, model: Model):
        self.view = view
        self.model = model

        # initialize udp message sender
        self.arm_list_sender = ArmListSender() 

        self.song_controls_frame = view.song_controls_frame
        self.song_frame = view.song_frame
        self.song_builder_frame = view.song_builder_frame
        self.new_section_btn = view.new_section_btn

        self._create_event_bindings()
        self._create_key_shortcuts()

        # manually add the first section to the UI
        self._add_section()

    def start(self):
        self.view.start_mainloop()

    #region EventBindings
    def _create_event_bindings(self):
        # Song title entry
        self.song_controls_frame.song_title.trace_add(('write'), self._update_song_title_handler)

        # BPM spinbox
        self.song_controls_frame.bpm_spinbox.bind('<KeyRelease>', lambda e: self._update_bpm_handler(e, 'KeyRelease'))
        self.song_controls_frame.bpm_spinbox.bind('<<Increment>>', lambda e: self._update_bpm_handler(e, 'Increment'))
        self.song_controls_frame.bpm_spinbox.bind('<<Decrement>>', lambda e: self._update_bpm_handler(e, 'Decrement'))

        # Time signature options
        self.song_controls_frame.time_signature.trace_add('write', self._update_time_sig_handler)

        # Chord mode options
        self.song_controls_frame.chord_mode.trace_add('write', self._update_chord_mode_handler)

        # Chord notations btn
        self.song_controls_frame.chord_notation_btn.config(command=self._show_chord_notations_popup)

        # Save btn
        self.song_controls_frame.save_btn.config(command=self._save_song_handler)

        # Load btn
        self.song_controls_frame.load_btn.config(command=self._load_song_handler)

        # Send btn
        self.song_controls_frame.send_btn.config(command=self._send_song_handler)

        # Preview icon btn
        self.song_controls_frame.preview_btn.configure(command=lambda: self._preview_song_handler()) # use configure for CTk btn

        # Help icon btn
        self.song_controls_frame.help_btn.configure(command=lambda: self._show_help_popup()) # use configure for CTk btn

        # New section btn
        self.new_section_btn.configure(command=self._new_section_handler) # use configure for CTk btn
        
    def _create_section_event_bindings(self, section):
        section_frame, labels_frame = section

        # this allows us to just add the icon/input event bindings (helpful for add_measure)
        if labels_frame is not None:
            # Trash, eraser button icons
            labels_frame.eraser_btn.configure(command=lambda: self._clear_section_handler(section_frame, labels_frame)) # use configure for CTk btn
            labels_frame.trash_btn.configure(command=lambda: self._remove_section_handler(section_frame.id)) # use configure for CTk btn

            # Strum options dropdown
            labels_frame.strum_pattern.trace_add(('write'), lambda e1, e2, e3: self._update_section_strum_pattern_handler(e1, e2, e3, section_frame, labels_frame))

        # Eraser (clear measure) icons
        for tuple in section_frame.eraser_btns:
            btn, measure_idx = tuple
            # TODO: measure_idx is only passing the last measure num. copy, deepcopy didn't fix it
            btn.configure(command=lambda: self._clear_measure_handler(section_frame, measure_idx)) # use configure for CTk btn

        # Trash (remove measure) icons
        for tuple in section_frame.trash_btns:
            btn, measure_idx = tuple
            btn.configure(command=lambda: self._remove_measure_handler(None, section_frame, measure_idx)) # use configure for CTk btn

        # Add/remove measure key bindings for input boxes
        for row in range(2, 4):
            for col in range(1, section_frame.subdiv_per_measure * section_frame.num_measures + 1):
                entry = section_frame.grid_slaves(row=row, column=col)[0]
                m = col % section_frame.subdiv_per_measure

                # Return -> Add measure
                entry.bind("<Shift-Return>", lambda e: self._add_measure_handler(e, section_frame, m))

                # Shift+Backspace -> Remove measure
                entry.bind("<Shift-BackSpace>", lambda e: self._remove_measure_handler(e, section_frame, m))

    #endregion EventBindings

    #region KeyShortcuts

    def _create_key_shortcuts(self):
        # Ctrl-S -> save song
        self.view.bind('<Control-s>', lambda e: self._save_song_handler())

        # Ctrl-L -> load song
        self.view.bind('<Control-l>', lambda e: self._load_song_handler())

        # Ctrl-P -> send song
        self.view.bind('<Control-p>', lambda e: self._send_song_handler())

    #endregion KeyShortcuts
        
    #region EventHandlers
    
    #region SongControls
    def _update_song_title_handler(self, event, *args):
        self.model.song_title = self.song_controls_frame.song_title.get()

    def _update_bpm_handler(self, event, type):
        # This event handler will run before increment/decrement buttons update the actual Entry, so we need to manually increment/decrement to account for that
        if type == 'Increment':
            self.model.bpm = int(self.song_controls_frame.bpm_spinbox.get()) + 1
        elif type == 'Decrement':
            self.model.bpm = int(self.song_controls_frame.bpm_spinbox.get()) - 1
        elif type == 'KeyRelease':
            try:
                self.model.bpm = int(self.song_controls_frame.bpm_spinbox.get())
            except ValueError:
                # If user enters invalid BPM (such as a letter or empty string) then set BPM to default value
                self.model.bpm = DEFAULT_BPM

    def _update_time_sig_handler(self, event, *args):
        time_sig = self.song_controls_frame.time_signature.get()

        # update model
        self.model.time_signature = time_sig

        # reset view w/ updated time signature
        for section in self.song_frame.sections:
            section_frame, section_label = section
            section_frame.rebuild_table(time_sig)

            # re-add section event bindings
            self._create_section_event_bindings(section)

        # update model accordingly
        self._update_model_sections()

    def _update_chord_mode_handler(self, event, *args):
        self.model.chord_mode = self.song_controls_frame.chord_mode.get()

    def _show_chord_notations_popup(self):
        popup = ChordNotationsPopup(self.view)

        # when "Close" button is clicked, popup will be destroyed
        popup.close_btn.config(command=popup.destroy)

    def _show_help_popup(self):
        popup = HelpPopup(self.view)

        # when "Close" button is clicked, popup will be destroyed
        popup.close_btn.config(command=popup.destroy)

    # Save btn
    def _save_song_handler(self):
        self._update_model_sections()
        song_order = self._get_ordered_section_ids()
        JsonHelper.write_song_to_json(self.model.song_title, self.model.time_signature, self.model.bpm, self.model.chord_mode, song_order, self.model.sections.values())

    # Load btn
    def _load_song_handler(self):
        # load song data
        song_dict, section_dicts = JsonHelper.load_song_from_json()

        # unpack song_dict
        song_title = song_dict["song_title"]
        bpm = song_dict["bpm"]
        time_signature = song_dict["time_signature"]
        chord_mode = song_dict["chord_mode"]
        ordered_section_ids = song_dict["ordered_section_ids"]

        # update song data in model
        self.model.update_song_data(song_title, bpm, time_signature, chord_mode)

        # remove existing sections from view
        for section_id in self.model.sections.keys():
            # remove section from song frame
            self.song_frame.remove_section(section_id)
            # remove section from song builder (drag and drop)
            self.song_builder_frame.remove_section_button_and_draggables(section_id)

        # repopulate song data (title, bpm, time signature, chord mode) in view
        self.song_controls_frame.update_song_data(song_title, bpm, time_signature, chord_mode)

        # Dictionary that stores section name tk.StringVar variables for each section
        # Needed later in this function when adding draggable sections
        section_name_vars = {}
        
        # add sections back to the view
        for section_dict in section_dicts:
            section_frame, labels_frame = self._add_section(add_first_section_to_drag_drop=False)

            # get section data from section_dict
            id = section_dict["id"]
            name = section_dict["name"]
            strum_pattern = section_dict["strum_pattern"]
            num_measures = section_dict["num_measures"]
            left_arm = section_dict["left_arm"]
            right_arm = section_dict["right_arm"]

            self._populate_section_with_data(section_frame, labels_frame, name, strum_pattern, num_measures, left_arm, right_arm)
            section_name_vars[id] = labels_frame.name

        # update sections data in the model
        self._update_model_sections()

        # add sections to drag and drop song builder (in the correct order)
        for section_id in ordered_section_ids:
            # NOTE in order for name to display correctly on drag/drop section, it must be a tk.StringVar variable (not just a regular string)
            section_name = section_name_vars[section_id]
            self.song_builder_frame.add_draggable_section(None, (section_id, section_name))

    # Send btn
    def _send_song_handler(self):
        self._update_model_sections()
        self._send_song_to_bot()

    # Preview btn
    def _preview_song_handler(self):
        self._update_model_sections()
        self._preview_song_with_plugin()

    #endregion SongControls

    #region Sections
        
    def _update_section_strum_pattern_handler(self, e1, e2, e3, section_frame, labels_frame):
        # NOTE e1, e2, e3 are dummy parameters but needed to prevent erroring
        strum_pattern = labels_frame.strum_pattern.get()
        section_frame.fill_strum_pattern(strum_pattern)
        self._update_model_sections()
        
    def _clear_section_handler(self, section_frame, labels_frame):
        # clear section data in View
        section_frame.clear_table()
        labels_frame.clear() # this will set strum options dropdown back to default value
        
        # get updated section data from View
        left_arm, right_arm = section_frame.build_arm_lists()

        # update section data in model
        self.model.update_section_data(section_frame.id, left_arm, right_arm)

    def _remove_section_handler(self, id):
        # minimum of 1 section
        if len(self.song_frame.sections) == 1:
            return
        
        # remove section from View
        self.song_frame.remove_section(id)
        self.song_builder_frame.remove_section_button_and_draggables(id)

        # update Model accordingly
        self.model.remove_section(id)

    def _add_measure_handler(self, e, section_frame, measure_idx):
        print(f'Add measure handler, {measure_idx} to section {section_frame.id}')
        # add measure to View
        # TODO uncomment once this function is implemented in SectionFrame.py (adds measure at any point in the section)
        #section_frame.add_measure(measure_idx)

        # for now, just add measure at the end of the section
        section_frame.add_measure()

        # re-add section event bindings to include new measure
        # we don't need to re-add section_label bindings, so we pass in None for this
        self._create_section_event_bindings((section_frame, None))

        # update section data in model
        self._update_model_section_arm_lists(section_frame)

    def _clear_measure_handler(self, section_frame, measure_idx):
        # clear section data in View
        section_frame.clear_measure(measure_idx)
        
        # update section data in model
        self._update_model_section_arm_lists(section_frame)

    def _remove_measure_handler(self, e, section_frame, measure_idx):
        print(f'Remove measure handler, {measure_idx} from section {section_frame.id}')
        # remove measure from View
        # TODO uncomment once this function is implemented in SectionFrame.py (removes measure from any point in the section)
        # section_frame.remove_measure(measure_idx)

        # for now, just remove measure from the end of the section
        section_frame.remove_measure()

        # update section data in model
        self._update_model_section_arm_lists(section_frame)

    # New section btn
    def _new_section_handler(self):
        self._add_section()

    #endregion Sections
        
    #endregion EventHandlers
    
    #region Helpers
        
    # Helper method for saving, loading, sending
    # Saves all the current section data in the View to the Model
    def _update_model_sections(self):
        # iterate over each section
        for section_tuple in self.view.song_frame.sections:
            section_frame, labels_frame = section_tuple

            # get section data from View
            id = section_frame.id
            name = labels_frame.name.get()
            strum_pattern = labels_frame.strum_pattern.get()
            num_measures = section_frame.num_measures
            left_arm, right_arm = section_frame.build_arm_lists()

            # update section data in model
            self.model.update_section_data(id, left_arm, right_arm, name, strum_pattern, num_measures)

    # Updates the arm lists for a particular section in the Model
    def _update_model_section_arm_lists(self, section_frame):
        # get updated section data from View
        left_arm, right_arm = section_frame.build_arm_lists()

        # update section data in model
        self.model.update_section_data(section_frame.id, left_arm, right_arm)
        #print(self.model.sections[section_frame.id].left_arm, self.model.sections[section_frame.id].right_arm)

    # Returns a list of the section ids in order of the song builder layout
    def _get_ordered_section_ids(self):
        ordered_section_ids = []

        # loop through song builder and append section ids in order
        for dd_section in DraggableSectionLabel.existing_draggables_list:
            # get the current section from the model
            model_section = self.model.sections[dd_section.section_id]
            ordered_section_ids.append(model_section.id)

        return ordered_section_ids

    # Helper method to add a new section to the View and Model accordingly
    def _add_section(self, add_first_section_to_drag_drop=True):
        # manually add new section to the UI
        section = self.view.song_frame.add_section(self.model.time_signature)
        section_frame, labels_frame = section
        id, name = section_frame.id, labels_frame.name

        # add section button to song builder buttons list (this will also automatically drop the very first section onto the song)
        self.song_builder_frame.add_section_button(id, name, add_first_section_to_drag_drop)

        # now update the model accordingly
        self.model.add_section(id, name)

        # add event bindings for new section
        self._create_section_event_bindings(section)

        return section_frame, labels_frame
    
    def _populate_section_with_data(self, section_frame, labels_frame, name, strum_pattern, num_measures, left_arm, right_arm):
        # add name, strum pattern selection to the section labels
        labels_frame.update_name_and_strum_pattern(name, strum_pattern)

        # add measures and left_arm, right_arm data
        section_frame.update_section_data(num_measures, left_arm, right_arm)

    def _build_complete_arm_lists(self):
        left_arm = []
        right_arm = []

        # loop through song builder and append individual section left/right arm lists to the total lists
        for dd_section in DraggableSectionLabel.existing_draggables_list:
            # get the current section from the model
            model_section = self.model.sections[dd_section.section_id]

            # append left_arm, right_arm lists
            left_arm = left_arm + model_section.left_arm
            right_arm = right_arm + model_section.right_arm

        # print(left_arm, '\n', right_arm)
        return left_arm, right_arm
    
    # calculate the total time per each measure in seconds
    def _calculate_measure_time(self):
        beats_per_measure = int(self.model.time_signature[0])
        beat_duration = 4/int(self.model.time_signature[2])
        measure_time = beats_per_measure * (60/self.model.bpm) * beat_duration
        return measure_time

    def _send_song_to_bot(self):
        left_arm, right_arm = self._build_complete_arm_lists()
        
        # get the total time for each measure in seconds
        measure_time = self._calculate_measure_time()
        # print(measure_time)

        # send arm lists, measure_time to reciever via UDP message
        self.arm_list_sender.send_arm_lists_to_reciever(left_arm, right_arm, measure_time)
        
    # TODO run this on a separate thread so that it doesn't block entire UI (current implementation not working)
    def _preview_song_with_plugin(self):
        left_arm, right_arm = self._build_complete_arm_lists()

        # preview with VST plugin
        # NOTE: plugin must be open and running separately through compatible DAW (GarageBand as of rn)
        midi_chords = arms_to_MIDI(left_arm, right_arm, self.model.bpm, subdiv_per_beat=2)

        # create separate thread to run preview function on
        preview_thread = threading.Thread(target=play_midi_with_plugin(midi_chords))
        preview_thread.start()

    #endregion Helpers