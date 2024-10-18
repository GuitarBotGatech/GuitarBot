import customtkinter as ctk
import tkinter as tk
from vis_entities.DraggableSectionLabel import DraggableSectionLabel
from frames.SongBuilderDragAndDropFrame import SongBuilderDragAndDropFrame

class SongBuilderFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, width, height):
        super().__init__(master, orientation='horizontal', width=width, height=height)

        self.width = width
        self.height = height

        self.drag_and_drop_canvas = SongBuilderDragAndDropFrame(master=self, width=width, height=height)
        self.section_button_frame = tk.Frame(master=self.drag_and_drop_canvas)
        self.button_column = 0

        self.btn_dict = {}
        
        self.drag_and_drop_canvas.create_window(width/2.0, 15, anchor=tk.CENTER, window=self.section_button_frame)        
    
    def add_section_button(self, section_id, section_name, add_first_section_to_drag_drop=True):
        btn = tk.Label(master=self.section_button_frame, textvariable=section_name, bg='navy blue', fg='white', width=6, cursor='hand2')

        btn.bind("<ButtonPress-1>", lambda event, arg=(section_id, section_name): self.add_draggable_section(event, arg))
        btn.pack(side='left', padx=5)

        # automatically add first section to the song so that it is already there when the application starts
        if section_id == 1 and add_first_section_to_drag_drop:
            self.add_draggable_section(None, (section_id, section_name))

        self.btn_dict[section_id] = btn
        self.button_column += 1

    def remove_section_button_and_draggables(self, section_id):
        self.btn_dict[section_id].destroy()
        del self.btn_dict[section_id]
        
        # filter for sections we do/don't want to keep
        keep_list = [item for item in DraggableSectionLabel.existing_draggables_list if item.section_id != section_id]
        destroy_list = [item for item in DraggableSectionLabel.existing_draggables_list if item.section_id == section_id]
        
        # destroy sections which matched the section_id
        for section in destroy_list:
            section.destroy(None)

        # update draggable sections list
        DraggableSectionLabel.existing_draggables_list = keep_list

    def add_draggable_section(self, event, section_id_and_name):
        section_id, section_name = section_id_and_name
        dsl = DraggableSectionLabel(name=section_name, mid_height_y=self.height/2.0, section_id=section_id)
        dsl.attach_at_end(canvas=self.drag_and_drop_canvas)    