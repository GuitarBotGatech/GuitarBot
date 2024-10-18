import tkinter as tk
import customtkinter as ctk
from tkinter.constants import *
from frames.SectionFrame import SectionFrame
from frames.SectionLabelsFrame import SectionLabelsFrame

class SongFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, width, height):
        super().__init__(master, orientation='vertical', width=width, height=height)
        
        self.sections = []
        self.width = width
        self.height = height
        self.add_idx = 0
        self.curr_id = 1

    def id_to_section_idx(self, id):
        # id -> remove_idx
        section_idx = 0
        for section in self.sections:
            if section[0].id == id:
                break
            section_idx += 1

        return section_idx
    
    def add_section(self, time_signature):
        labels_frame = SectionLabelsFrame(master=self, id=self.curr_id, width=self.width * 0.05, height=self.height * 0.2)
        section_frame = SectionFrame(master=self, id=self.curr_id, width=self.width * 0.84, height=self.height * 0.21, time_signature=time_signature)
        self.sections.append((section_frame, labels_frame))

        labels_frame.grid(row=self.add_idx, column=0)
        section_frame.grid(row=self.add_idx, column=1)
        self.add_idx += 1
        self.curr_id += 1

        return section_frame, labels_frame
    
    def remove_section(self, section_id):
        remove_idx = self.id_to_section_idx(section_id)

        removed_labels_frame, removed_section_frame = self.sections[remove_idx]
        removed_section_frame.grid_forget()
        removed_labels_frame.grid_forget()
    
        self.sections.pop(remove_idx)
        if section_id == self.curr_id - 1:
            self.curr_id -= 1
        # self.add_idx -= 1 # This seems logical but breaks the code