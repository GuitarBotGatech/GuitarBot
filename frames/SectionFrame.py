import tkinter as tk
import tkinter.ttk as ttk
import customtkinter as ctk
from constants.strum_patterns import *
from constants.time_signatures import *
from PIL import Image

class SectionFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, id, width, height, time_signature):
        super().__init__(master=master, width=width, height=height, orientation='horizontal')
        self.id = id

        self.width = width
        self.height = height

        self.time_signature = time_signature
        self.last_col = 0
        self.num_measures = 0
        self.curr_measure = 0
        self.beats_per_measure = int(time_signature[0])
        self.subdiv_per_measure = self.beats_per_measure * 2
        self.beat_labels = beat_labels[time_signature]
        
        self.plus_btns = [] # for plus signs (currently not implemented)
        self.trash_btns = [] # tuple of form (trash_btn, measure_idx)
        self.eraser_btns = [] # tuple of form (eraser_btn, measure_idx)

        self.chords_tab_order = []
        self.strums_tab_order = []

        # create intial measure
        self.add_measure() # start each section with an initial measure

    def _reset_instance_variables(self, time_signature):
        self.time_signature = time_signature
        self.last_col = 0
        self.num_measures = 0
        self.curr_measure = 0
        self.beats_per_measure = int(time_signature[0])
        self.subdiv_per_measure = self.beats_per_measure * 2
        self.beat_labels = beat_labels[time_signature]
        
        self.plus_btns = []
        self.trash_btns = []
        self.eraser_btns = []

        self.chords_tab_order = []
        self.strums_tab_order = []

    def build_measure(self, start_col):
        # get underlying frame's background color
        frame_bg =self.master.cget('bg')

        # build chords/strum inputs
        for row in range(0, 4):
            col = start_col

            while col <= (self.subdiv_per_measure * self.num_measures):
                if row == 0:
                    # BAR LABELS
                    #print(self.curr_measure)
                    self.cell = tk.Label(self, width=4, text="Bar " + str(self.curr_measure), bg=frame_bg, justify="center")
                    self.cell.grid(row=row, column=col + self.beats_per_measure - 2, sticky='e',
                                    columnspan=2)
                    
                    # Add trash (delete measure) icon
                    img = Image.open('./icons/trash-16px.png')
                    self.trash_icon = ctk.CTkImage(img, size=(16, 16)) # this must be an instance variable so python doesn't garbage collect it
                    self.trash_btn = ctk.CTkButton(self, image=self.trash_icon, width=0, border_width=0, border_spacing=0, text='', fg_color='transparent')
                    self.trash_btn.grid(row=row, column=col + self.beats_per_measure, sticky='w')
                    self.trash_btns.append((self.trash_btn, self.curr_measure - 1)) # subtract 1 so measure_idx is 0-indexed

                    # Add eraser (clear measure) icon
                    img = Image.open('./icons/eraser-16px.png')
                    self.eraser_icon = ctk.CTkImage(img, size=(16, 16)) # this must be an instance variable so python doesn't garbage collect it
                    self.eraser_btn = ctk.CTkButton(self, image=self.eraser_icon, width=0, border_width=0, border_spacing=0, text='', fg_color='transparent')
                    self.eraser_btn.grid(row=row, column=col + self.beats_per_measure + 1, sticky='w')
                    self.eraser_btns.append((self.eraser_btn, self.curr_measure - 1)) # subtract 1 so measure_idx is 0-indexed
                    
                    col += self.subdiv_per_measure
                    continue
                elif row == 1:
                    # BEAT LABELS
                    self.cell = ttk.Entry(self, width=2, font=('Arial', 16, 'bold'))

                    #check if this is the last beat of the measure
                    if col != 0 and col % self.subdiv_per_measure == 0:
                        # add a space afterwards
                        self.cell.grid(row=row, column=col, padx=(0, 30))
                    else:
                        self.cell.grid(row=row, column=col)

                    self.cell.insert(tk.END,
                                        self.beat_labels[(col - 1) % self.subdiv_per_measure])
                    
                    # disable entry
                    self.cell.config(state=tk.DISABLED)
                elif row == 2:
                    # CHORD INPUTS
                    self.cell = ttk.Entry(self, width=6, font=('Arial', 16))

                    self.cell.grid(row=row, column=col, sticky='w', columnspan=2)
                    self.chords_tab_order.append(self.cell)

                    self.cell.insert(tk.END, "")
                    col += 1
                elif row == 3:
                    # STRUM INPUTS
                    self.cell = ttk.Entry(self, width=2, font=('Arial', 16))

                    # check if this is the last beat of the measure
                    if col != 0 and col % self.subdiv_per_measure == 0:
                        # add a space afterwards
                        self.cell.grid(row=row, column=col, padx=(0, 30))
                    else:
                        self.cell.grid(row=row, column=col)

                    self.cell.insert(tk.END, "")

                    self.strums_tab_order.append(self.cell)
                col += 1

        # set default focus to first input of last measure
        self.grid_slaves(row=2, column=start_col + 1)[0].focus_set()

        # TODO add plus sign icon between measures
        # NOTE: this causes many problems with the layout of the bars/modular math/other measure-related functions
        # img = Image.open('UI/icons/plus-sign-24px.png')
        # self.plus_icon = ctk.CTkImage(img, size=(24, 24)) # this must be an instance variable so python doesn't garbage collect it
        # self.plus_btn = ctk.CTkButton(self, image=self.plus_icon, width=0, border_width=0, border_spacing=0, text='', fg_color='transparent')
        # self.plus_btn.grid(row=2, column=col, sticky='w', columnspan=1)

        # update last_column
        self.last_col = (self.subdiv_per_measure * self.num_measures) # add 1 to account for plus sign icon

        # set tabbing order
        self._set_tab_order()

    def clear_measure(self, measure_idx):
        #print(measure_idx)
        col = (self.subdiv_per_measure * measure_idx) + 1

        while col <= self.subdiv_per_measure * (measure_idx + 1):
            #print(col)
            # clear chord input
            self.grid_slaves(row=2, column=col)[0].delete(0, tk.END)

            # clear strum input
            self.grid_slaves(row=3, column=col)[0].delete(0, tk.END)

            col += 1

    # TODO: Generalization of remove from end function it overloads
    def remove_measure(self, measure_idx):
        pass
        # TODO: test, and modify further if needed
        # start_col = (measure_idx - 1) * self.subdiv_per_measure
        #
        # # minimum of 1 measure per section
        # if self.num_measures > 1:
        #     self.num_measures = self.num_measures - 1

        # # delete all components in last measure
        # for i in range(self.subdiv_per_measure):
        #     for j in range(5):
        #         for e in self.grid_slaves(column=start_col + i, row=j):
        #             e.grid_forget()

        #             # remove deleted cells from tab orders
        #             if j == 2:
        #                 self.chords_tab_order.pop(start_col + i)
        #             if j == 3:
        #                 self.strums_tab_order.pop(start_col + i)

        #             self._set_tab_order()

        # # update last column
        # self.last_col = self.last_col - self.subdiv_per_measure

        # # set default focus to first input of last measure
        # self.grid_slaves(row=2, column=self.last_col - self.subdiv_per_measure + 1)[
        #     0].focus_set()

        # # put bar labels back
        # self.cell = tk.Label(self, width=4, text="Bar " + str(self.num_measures))
        # self.cell.grid(row=0, column=self.last_col - self.beats_per_measure, sticky='w',
        #                 columnspan=self.subdiv_per_measure)

    def _set_tab_order(self):
        # NOTE: if user presses tab on last chord input in a section, focus will go to the first strum input on the next row
        
        # iterate through the "Chords" row, set tabbing order from left -> right
        for cell in self.chords_tab_order:
            cell.lift()

        # iterate through the "Strums" row, set tabbing order from left -> right
        for cell in self.strums_tab_order:
            cell.lift()

    def add_measure(self):
        self.num_measures += 1
        self.curr_measure += 1

        self.build_measure(self.last_col + 1)

    def remove_measure(self):
        # minimum of 1 measure per section
        if self.num_measures == 1:
            return
            
        self.num_measures -= 1
        self.curr_measure -= 1

        # delete all components in last measure
        for col in range(self.subdiv_per_measure):
            for row in range(4):
                for e in self.grid_slaves(column=self.last_col - col, row=row):
                    e.grid_forget()

                    # remove deleted cells from tab orders
                    if row == 2:
                        self.chords_tab_order.pop()
                    if row == 3:
                        self.strums_tab_order.pop()

        # reset tab order
        self._set_tab_order()

        # update last column
        self.last_col = self.last_col - self.subdiv_per_measure

        # set default focus to first input of last measure
        self.grid_slaves(row=2, column=self.last_col - self.subdiv_per_measure + 1)[
            0].focus_set()

    # called when time signature changes
    def rebuild_table(self, time_signature):
        # delete prev rows
        for w in self.grid_slaves():
            w.grid_forget()

        self._reset_instance_variables(time_signature)
        # add first measure back
        self.add_measure()

    def clear_table(self):
        for e in reversed(self.grid_slaves(row=2)):
            e.delete(0, tk.END)

        for e in reversed(self.grid_slaves(row=3)):
            e.delete(0, tk.END)

        # print("table cleared")
            
    def fill_strum_pattern(self, strum_pattern):
        # print(strum_pattern)
        # print(strum_patterns.get(strum_pattern))
        count = 0
        for e in reversed(self.grid_slaves(row=3)):
            e.delete(0, tk.END)

            if strum_pattern != "Custom":
                length = len(strum_patterns.get(strum_pattern))
                e.insert(tk.END, strum_patterns.get(strum_pattern)[count % length])

            count += 1

    def build_arm_lists(self):
        left_arm = []
        right_arm = []

        # generate left arm data
        curr_measure = []
        count = 1 # this must start at 1
        for e in reversed(self.grid_slaves(row=2)):
            # print("count: ", count)
            # print("value: ", e.get())
            # print("numbeats: ", numBeatsPerMeasure)

            curr_measure.append(e.get())
            if count == self.beats_per_measure:
                left_arm.append(curr_measure)
                curr_measure = []
                count = 1
                continue
            count += 1

        # generate right arm data
        curr_measure = []
        count = 1 # this must start at 1
        for e in reversed(self.grid_slaves(row=3)):
            curr_measure.append(e.get())
            if count == self.subdiv_per_measure:
                # start a new measure
                right_arm.append(curr_measure)
                curr_measure = []
                count = 1
                continue
            count += 1

        return (left_arm, right_arm)

    # Helper method to fill section with left_arm, right_arm data
    def insert_chord_strum_data(self, left_arm, right_arm):
        # flatten left_arm, right_arm lists to 1D lists
        left_arm = [item for sublist in left_arm for item in sublist]
        right_arm = [item for sublist in right_arm for item in sublist]

        # insert left arm (chord) data
        i = 0
        for e in reversed(self.grid_slaves(row=2)):
            # if i != 0:
            e.delete(0, tk.END)
            e.insert(0, left_arm[i])
            i += 1

        # insert right arm (strum) data
        i = 0
        for e in reversed(self.grid_slaves(row=3)):
            # if i != 0:
            e.delete(0, tk.END)
            e.insert(0, right_arm[i])
            i += 1

    def update_section_data(self, num_measures, left_arm, right_arm):
        for i in range(num_measures - 1):
            self.add_measure()

        self.insert_chord_strum_data(left_arm, right_arm)
