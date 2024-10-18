import tkinter as tk
import customtkinter as ctk
from frames.SongControlsFrame import SongControlsFrame
from frames.SongFrame import SongFrame
from frames.SongBuilderFrame import SongBuilderFrame
from tkhtmlview import HTMLScrolledText, RenderHTML

class View(tk.Tk):
    def __init__(self):
        super().__init__()

        SCREEN_WIDTH = self.winfo_screenwidth()
        SCREEN_HEIGHT = self.winfo_screenheight()

        # set up window
        self.title('GuitarBot')
        self.geometry(f'{SCREEN_WIDTH}x{SCREEN_HEIGHT}')

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # add main frames/components
        self.song_controls_frame = SongControlsFrame(master=self, width=SCREEN_WIDTH, height=SCREEN_HEIGHT * 0.20)
        self.song_controls_frame.grid(row=0, column=0)

        self.song_frame = SongFrame(master=self, width=SCREEN_WIDTH, height=SCREEN_HEIGHT * 0.625)
        self.song_frame.grid(row=1, column=0)

        self.new_section_btn = ctk.CTkButton(self, text="New Section", width=SCREEN_WIDTH * 0.08, height=SCREEN_HEIGHT * 0.02)
        self.new_section_btn.grid(row=2, column=0, pady=SCREEN_WIDTH*0.005)

        self.song_builder_frame = SongBuilderFrame(master=self, width=SCREEN_WIDTH, height=SCREEN_HEIGHT * 0.125)
        self.song_builder_frame.grid(row=3, column=0)
    
    def start_mainloop(self):
        self.mainloop()

# POP-UP WINDOWS
        
class ChordNotationsPopup(tk.Toplevel):
    def __init__(self, master):
        super().__init__()

        self.title("Chord Notations")
        self.geometry('800x500')

        # Add chord notations list (HTML)
        html_content = HTMLScrolledText(self, html=RenderHTML('./html/chord_notations_popup.html'))
        html_content.pack(fill='both', expand=True)
        # htmlContent.fit_height()

        # Add close button
        self.close_btn = tk.Button(self, text="Close")
        self.close_btn.pack()

class HelpPopup(tk.Toplevel):
    def __init__(self, master):
        super().__init__()

        self.title("Help")
        self.geometry('500x350')

        # Add html content
        html_content = HTMLScrolledText(self, html=RenderHTML('./html/help_popup.html'))
        html_content.pack(fill='both', expand=True)
        # htmlContent.fit_height()

        # Add close button
        self.close_btn = tk.Button(self, text="Close")
        self.close_btn.pack()