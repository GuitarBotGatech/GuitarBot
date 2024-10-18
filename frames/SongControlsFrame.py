import tkinter as tk
import tkinter.ttk as ttk
import customtkinter as ctk
from constants.time_signatures import time_signature_options
from constants.chord_modes import chord_mode_options
from constants.bot_specs import MIN_BPM, MAX_BPM, DEFAULT_BPM
from PIL import Image

class SongControlsFrame(tk.Frame):
    def __init__(self, master, width, height):
        super().__init__(master, width=width, height=height)
        self.width = width
        self.height = height
        self.song_title = tk.StringVar(self, 'Song Title')
        self.time_signature = tk.StringVar(self)
        self.bpm = tk.IntVar(self, DEFAULT_BPM)
        self.chord_mode = tk.StringVar(self)

        # configure row height
        for i in range(2):
            self.grid_rowconfigure(i, minsize=self.height * 0.25)

        # configure column width
        for i in range(10):
            if i in range(3, 6):
                # make middle columns tighter
                self.grid_columnconfigure(i, minsize=self.width * 0.05, pad=0)
            elif i in range(8, 10):
                self.grid_columnconfigure(i, minsize=self.width * 0.06, pad=0)
            else:
                self.grid_columnconfigure(i, minsize=self.width * 0.135, pad=0)

        # Chord Mode dropdown
        self.chord_mode_dd = ttk.OptionMenu(self, self.chord_mode, 'Chord Mode', *chord_mode_options)
        self.chord_mode_dd.grid(row=0, column=0, sticky='W') 

        # Chord Notations btn
        self.chord_notation_btn = tk.Button(self, text="Chord Notations")
        self.chord_notation_btn.grid(row=1, column=0, sticky='W')

        # Song Title
        self.song_title_lbl = ttk.Entry(self, textvariable=self.song_title, width=17, justify='center', font=('TkDefaultFont', 16, 'bold'))
        self.song_title_lbl.grid(row=0, column=3, columnspan=3)

        # Save, Load, Send btns
        self.save_btn = tk.Button(self, text="Save")
        self.save_btn.grid(row=1, column=3, sticky='E')

        self.load_btn = tk.Button(self, text="Load")
        self.load_btn.grid(row=1, column=4)

        self.send_btn = tk.Button(self, text="Send")
        self.send_btn.grid(row=1, column=5, sticky='W')

        # Preview audio icon button
        img = Image.open('./icons/preview-audio-24px.png')
        self.preview_icon = ctk.CTkImage(img, size=(24, 24)) # this must be an instance variable so python doesn't garbage collect it
        self.preview_btn = ctk.CTkButton(self, image=self.preview_icon, width=0, border_width=0, border_spacing=0, text='', fg_color='transparent')
        self.preview_btn.grid(row=0, column=6, sticky='W')

        # Help icon button
        img = Image.open('./icons/help-24px.png')
        self.help_icon = ctk.CTkImage(img, size=(24, 24)) # this must be an instance variable so python doesn't garbage collect it
        self.help_btn = ctk.CTkButton(self, image=self.help_icon, width=0, border_width=0, border_spacing=0, text='', fg_color='transparent')
        self.help_btn.grid(row=1, column=6, sticky='W')

        # BPM label and text entry
        self.bpm_label = tk.Label(self, text="BPM:")
        self.bpm_label.grid(row=0, column=8, sticky='E')

        self.bpm_spinbox = ttk.Spinbox(self, textvariable=self.bpm, width=3, justify='left')
        self.bpm_spinbox.grid(row=0, column=9, sticky='EW')

        # Time signature label and dropdown
        self.time_sig_lbl = tk.Label(self, text="Time Signature:")
        self.time_sig_lbl.grid(row=1, column=8, sticky='E')

        self.time_sig_dd = ttk.OptionMenu(self, self.time_signature, "4/4", *time_signature_options)
        self.time_sig_dd.grid(row=1, column=9, sticky='EW')

    def update_song_data(self, song_title, bpm, time_signature, chord_mode):
        self.song_title.set(song_title)
        self.bpm.set(bpm)
        self.time_signature.set(time_signature)
        self.chord_mode.set(chord_mode)