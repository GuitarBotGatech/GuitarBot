import tkinter as tk
import tkinter.ttk as ttk
import customtkinter as ctk
from constants.strum_patterns import strum_options
from PIL import Image

class SectionLabelsFrame(tk.Frame):
    def __init__(self, master, id, width, height):
        super().__init__(master=master, width=width, height=height)
        self.id = id

        self.height = height
        self.width = width
        self.name = tk.StringVar(self, "Section" + str(id))
        self.strum_pattern = tk.StringVar(self)

        # configure rows
        for i in range(2):
            self.grid_rowconfigure(i, minsize=self.height * 0.25)

        # configure columns
        for i in range(4):
            self.grid_columnconfigure(i, minsize=self.width * 0.2)

        # name entry box
        self.name_entry = ttk.Entry(self, textvariable=self.name, justify='center', width=6)
        self.name_entry.grid(row=0, column=0, columnspan=2)

        # trash, eraser icon buttons
        img = Image.open('./icons/trash-16px.png')
        self.trash_icon = ctk.CTkImage(img, size=(16, 16)) # this must be an instance variable so python doesn't garbage collect it
        self.trash_btn = ctk.CTkButton(self, image=self.trash_icon, width=0, border_width=0, border_spacing=0, text='', fg_color='transparent')
        self.trash_btn.grid(row=1, column=0)

        img = Image.open('./icons/eraser-16px.png')
        self.eraser_icon = ctk.CTkImage(img, size=(16, 16)) # this must be an instance variable so python doesn't garbage collect it
        self.eraser_btn = ctk.CTkButton(self, image=self.eraser_icon, width=0, border_width=0, border_spacing=0, text='', fg_color='transparent')
        self.eraser_btn.grid(row=1, column=1)

        # chords label
        chords_lbl = tk.Label(self, text='Chords:')
        chords_lbl.grid(row=0, column=2, columnspan=2, sticky='EW')
            
        # strum options dropdown
        self.strum_options_dd = ttk.OptionMenu(self, self.strum_pattern, 'Strum Pattern', *strum_options)
        self.strum_options_dd.grid(row=1, column=2, columnspan=2)

    def clear(self):
        # set strum_options_dd back to default value
        self.strum_pattern.set('Strum Pattern')

    def update_name_and_strum_pattern(self, name, strum_pattern):
        self.name.set(str(name))
        self.strum_pattern.set(strum_pattern)
