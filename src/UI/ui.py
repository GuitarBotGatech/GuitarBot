import tkinter as tk
import tkinter.ttk as ttk
from tkinter import *
from tkinter.ttk import *
import tkinter.messagebox

# GuitarBot UI
# TODO: scrollbar, multiple phrases

window = tk.Tk(className=' GuitarBot')
window.geometry("1300x600")

timeFrame = Frame(window)
timeFrame.pack()
tabFrame = Frame(window)
tabFrame.pack()

timeSigs = [
    "2/4",
    "3/4",
    "4/4"
]

beats = {
    "2/4": ["1", "+", "2", "+"],
    "3/4": ["1", "+", "2", "+", "3", "+"],
    "4/4": ["1", "+", "2", "+", "3", "+", "4", "+"]
}

strumOptions = [
    "Custom",
    "Down/Up",
    "Downs",
    "Ups",
]
    
strumPatterns = {
    "Down/Up": ["D", "U"],
    "Downs": ["D", ""],
    "Ups": ["", "U"]
}

timeSelection = StringVar(window)
numMeasures = StringVar(window)
strumSelection = StringVar(window)

numPhrases = IntVar(window)

# class for the chart module with chords and strumming inputs
# TODO: save state
class Table:
    def __init__(self, root):
        self.root = root
        self.barCount = 0
        self.lastCol = 0
        self.name = ""
        
        # assign phrase number
        if numPhrases is None:
            numPhrases.set(0)

        self.phraseNum = numPhrases.get()
        numPhrases.set(numPhrases.get() + 1)

    def buildTable(self, num_cols, timeSelection, numMeasures, start, barCount):        
        # build chords/strum chart
        for i in range(4):
            j = start
            while j <= num_cols:
                if i == 0 and barCount <= int(numMeasures.get()):
                    # MEASURE LABELS
                    # account for bar label placement shift
                    if (j != 0 and j == start):
                        j -= 1

                    labelText = "Bar " + str(barCount)
                    self.cell = Label(self.root, width=4, text=labelText)
                    self.cell.grid(row=i, column=j + int(timeSelection.get()[0]), sticky=W, columnspan=int(timeSelection.get()[0]) * 2)
                    j += int(timeSelection.get()[0]) * 2
                    barCount += 1
                    continue
                elif i == 1:
                    # BEAT LABELS
                    if j == 0:
                        # add empty label at beginning of row (placeholder to align w/ below rows)
                        self.cell = Label(self.root, width=6, text="")
                        self.cell.grid(row=i, column=j)
                        j += 1
                        continue

                    self.cell = Entry(self.root, width=2, font=('Arial', 16, 'bold'))
                
                    # add space after last beat of measure
                    if j != 0 and j % len(beats.get(timeSelection.get())) == 0:
                        self.cell.grid(row=i, column=j, padx=(0, 30))
                    else:
                        self.cell.grid(row=i, column=j)

                    self.cell.insert(END, beats.get(timeSelection.get())[(j - 1) % len(beats.get(timeSelection.get()))])
                    self.cell.config(state=DISABLED)
                elif i == 2:
                        # CHORD INPUTS
                        if j == 0:
                            # add "Chords: " label at beginning of row
                            self.cell = Label(self.root, width=6, text="Chords: ")
                            self.cell.grid(row=i, column=j)
                            j += 1
                            continue

                        self.cell = Entry(self.root, width=6, font=('Arial',16))

                        # add <BackSpace> event handler to first chord input in each measure
                        if j == 1 or j == start:
                            self.cell.bind("<BackSpace>", backspace_pressed)

                        # add <Return> event handler to last chord input in each measure
                        if j != 0 and (j + 1) % len(beats.get(timeSelection.get())) == 0:
                            self.cell.bind("<Return>", ret_pressed)

                        self.cell.grid(row=i, column=j, sticky=W, columnspan=2)

                        self.cell.insert(END, "")
                        j += 1
                elif i == 3:
                    # STRUM INPUTS
                    if j == 0:
                        # add "Strum Pattern: " dropdown at beginning of row
                        if strumSelection.get() == "":
                            strumSelection.set("Custom")
                        
                        self.cell = OptionMenu(self.root, strumSelection, strumSelection.get(), *strumOptions, command=self.fillStrumPattern)
                        self.cell.grid(row=i, column=j)
                        j += 1
                        continue

                    self.cell = Entry(self.root, width=2, font=('Arial',16))

                    # add spacing after last beat of measure
                    if j != 0 and j % len(beats.get(timeSelection.get())) == 0:
                        self.cell.grid(row=i, column=j, padx=(0, 30))
                    else:
                        self.cell.grid(row=i, column=j)

                    if strumSelection.get() != "Custom":
                        self.cell.insert(END, strumPatterns.get(strumSelection.get())[(j + 1) % 2]) # autofill newly added cells with selected strum pattern
                    else:
                        self.cell.insert(END, "")
                j += 1

        # set default focus to first input of last measure
        self.root.grid_slaves(row=2, column=start + 1)[0].focus_set()
        
        # update table fields barCount, lastCol
        self.barCount = barCount - 1
        self.lastCol = num_cols

        # place clear button
        self.cell = Button(self.root, text="Clear", width=4, command=self.clearTable)
        self.cell.grid(row=5, column=j - 3, columnspan=2, sticky=W)

        # components for phrase name input
        self.cell = Label(self.root, width=5, text="Name:")
        self.cell.grid(row=5, column=j - 7, columnspan=2, sticky=E)
        nameInput = Entry(self.root, width=6, font=('Arial',14))
        nameInput.bind("<Key>", lambda c: self.__updateName(c, self, nameInput.get()))
        nameInput.grid(row=5, column=j - 5, columnspan=2, sticky=W)

    def __updateName(event, c, self, name):
        if c.keysym == "BackSpace":
            # slice off last char
            self.name = self.name[:len(self.name) - 1]
        else:
            # append pressed char
            self.name = name + c.char

    def addMeasure(self, num_cols):
        # delete previous clear button, name label/input (will get re-added during the buildTable() call)
        for e in self.root.grid_slaves(row=5):
            e.grid_forget()

        self.buildTable(num_cols, timeSelection, numMeasures, self.lastCol + 1, self.barCount + 1)
        # print("measure added")

    def removeMeasure(self):
        # delete all components in last measure
        for i in range(int(timeSelection.get()[0]) * 2):
            for e in self.root.grid_slaves(column=self.lastCol - i):
                e.grid_forget()

        # update last column
        self.lastCol = self.lastCol - int(timeSelection.get()[0]) * 2
        self.barCount -= 1

        # set default focus to first input of last measure
        self.root.grid_slaves(row=2, column=self.lastCol - int(timeSelection.get()[0]) * 2 + 1)[0].focus_set()

        # put bar label back
        labelText = "Bar " + str(self.barCount)
        self.cell = Label(self.root, width=4, text=labelText)
        self.cell.grid(row=0, column=self.lastCol - int(timeSelection.get()[0]), sticky=W, columnspan=int(timeSelection.get()[0]) * 2)

        # put clear button back
        self.cell = Button(self.root, text="Clear", width=4, command=self.clearTable)
        self.cell.grid(row=5, column=self.lastCol - 2, columnspan=2, sticky=W)

        # put components for phrase name input back
        self.cell = Label(self.root, width=5, text="Name:")
        self.cell.grid(row=5, column=self.lastCol - 6, columnspan=2, sticky=E)
        nameInput = Entry(self.root, width=6, font=('Arial',14))
        nameInput.bind("<Key>", lambda c: self.__updateName(c, self, nameInput.get()))
        nameInput.grid(row=5, column=self.lastCol - 4, columnspan=2, sticky=W)
        # print("measure removed")

    def editTable(self, num_cols, timeSelection, numMeasures):
        # delete prev rows
        for w in self.root.grid_slaves():
            w.grid_forget()
        
        self.buildTable(num_cols, timeSelection, numMeasures, 0, 1)

    def clearTable(self):
        count = 0
        for e in reversed(self.root.grid_slaves(row=2)):
            if count != 0:
                e.delete(0, END)
            count += 1

        count = 0
        for e in reversed(self.root.grid_slaves(row=3)):
            if count != 0:
                e.delete(0, END)
            count += 1

        # clear name input
        self.root.grid_slaves(row=5, column=self.lastCol-4)[0].delete(0, END)
        
        print("table cleared")

    def fillStrumPattern(self, strumSelection):
        # implementation choice: autofill entire table on selection? Or just set that selection for new bars?      
        count = 0

        for e in reversed(self.root.grid_slaves(row=3)):
            if count != 0:
                e.delete(0, END)
                if strumSelection != "Custom":
                    e.insert(END, strumPatterns.get(strumSelection)[(count + 1) % 2]) 
            count += 1 

    def buildChordStrumData(self, timeSelection):
        leftArm = []
        rightArm = []
        numBeatsPerMeasure = (int)(timeSelection.get()[0])
        bpm = (int)(bpmInput.get())
        
        # generate left arm data
        currMeasure = []
        count = 0
        for e in reversed(self.root.grid_slaves(row=2)):
            # print("count: ", count)
            # print("value: ", e.get())
            # print("numbeats: ", numBeatsPerMeasure)

            if count != 0:
                currMeasure.append(e.get())
                if count == numBeatsPerMeasure:
                    leftArm.append(currMeasure)
                    currMeasure = []
                    count = 1
                    continue

            count += 1

        # generate right arm data
        currMeasure = []
        count = 0
        duration = (60/bpm)/(numBeatsPerMeasure * 2) # calculate duration of each strum
        for e in reversed(self.root.grid_slaves(row=3)):
            # code for appending duration to each strum stroke:
            # if (e.get() != ""):
            #     currMeasure.append((e.get(), duration))
            # else:
            #     currMeasure.append("")

            if count != 0:
                currMeasure.append(e.get()) # delete this line if using above code
                if count == numBeatsPerMeasure * 2:
                    rightArm.append(currMeasure)
                    currMeasure = []
                    count = 1
                    continue

            count += 1

        return (leftArm, rightArm)

tab = Table(tabFrame)

def create_table(timeSelection, numMeasures):
    # set default values if needed
    if len(timeSelection.get()) == 0:
        timeSelection.set("4/4")
    if len(numMeasures.get()) == 0:
        numMeasures.set("1")

    num_cols = int(timeSelection.get()[0]) * (int)(numMeasures.get()) * 2
    tab.buildTable(num_cols, timeSelection, numMeasures, 0, 1)
    print("table created")

def update_table(event):
    # print("got these values",timeSelection.get(), numMeasures.get())
    # set default values if needed
    if len(timeSelection.get()) == 0:
        timeSelection.set("4/4")
    if len(numMeasures.get()) == 0:
        numMeasures.set("4")

    # reset number of measures back to 1
    numMeasures.set(1)

    # update measures display
    measuresDisplay.config(state="ENABLED")
    measuresDisplay.delete(0, END)
    measuresDisplay.insert(END, numMeasures.get())
    measuresDisplay.config(state=DISABLED)

    num_cols = int(timeSelection.get()[0]) * (int)(numMeasures.get()) * 2
    tab.editTable(num_cols, timeSelection, numMeasures)
    print("table updated")

def ret_pressed(event):
    add_measure()

def backspace_pressed(event):
    remove_measure()

def add_measure():
    numMeasures.set(int(numMeasures.get()) + 1)
    num_cols = int(timeSelection.get()[0]) * (int)(numMeasures.get()) * 2

    tab.addMeasure(num_cols)

    # update display
    measuresDisplay.config(state="ENABLED")
    measuresDisplay.delete(0, END)
    measuresDisplay.insert(END, numMeasures.get())
    measuresDisplay.config(state=DISABLED)

def remove_measure():
    if int(numMeasures.get()) > 1:
        numMeasures.set(int(numMeasures.get()) - 1)

        tab.removeMeasure()

        # update display
        measuresDisplay.config(state="ENABLED")
        measuresDisplay.delete(0, END)
        measuresDisplay.insert(END, numMeasures.get())
        measuresDisplay.config(state=DISABLED)

# load default table
create_table(timeSelection, numMeasures)

# time signature / bpm / measure dropdowns
timeMenu = OptionMenu(timeFrame, timeSelection, "4/4", *timeSigs, command=update_table)
timeLabel = Label(timeFrame, text="Time Signature: ")
timeLabel.pack(side=LEFT)
timeMenu.pack(side=LEFT)

bpmInput = Entry(timeFrame, width=2, font=('Arial',16))
bpmInput.insert(END, "60") # set default bpm
bpmLabel = Label(timeFrame, text="bpm: ")
bpmLabel.pack(side=LEFT)
bpmInput.pack(side=LEFT)

measuresLabel = Label(timeFrame, text="Measures: ")
measuresDisplay = Entry(timeFrame, width=2, font=('Arial',16))

# set default numMeasures to 1 if not initialized
if numMeasures.get() == "":
    numMeasures.set("1")

measuresDisplay.insert(END, numMeasures.get())
measuresDisplay.config(state=DISABLED)

removeMeasureBtn = Button(timeFrame, text="-", width=1, command=remove_measure)
addMeasureBtn = Button(timeFrame, text="+", width=1, command=add_measure)

measuresLabel.pack(side=LEFT)
removeMeasureBtn.pack(side=LEFT)
measuresDisplay.pack(side=LEFT)
addMeasureBtn.pack(side=LEFT)

def collect_chord_strum_data():
    # build lists with chord/strum info
    lists = tab.buildChordStrumData(timeSelection)
    left_arm = lists[0]
    right_arm = lists[1]
    song = songInput.get()

    # commands for getting the below values:
    # time signature -> timeSelection.get()
    # number of measures -> numMeasures.get()
    # bpm -> bpmInput.get()
    # duration of each strum = (60/bpm)/(numBeatsPerMeasure * 2)

    # save prev state
    # prevStrum = right_arm
    # prevChords = left_arm

    print("left arm: ", left_arm)
    print("right arm: ", right_arm)
    print("song: ", song)
    tkinter.messagebox.showinfo("Alert", "Song sent to GuitarBot.")

# create label and input for song to send to bot
# song components should be comma delimited (Ex: Verse, Chorus, Bridge)
songFrame = Frame(window)

songInput = Entry(songFrame, width=12, font=('Arial',14))
songLabel = Label(songFrame, text="Input: ")
songLabel.pack(side=LEFT)
songInput.pack(side=LEFT)

songFrame.pack(pady=(20,5))

send = Button(window, text="Send", width=4, command=collect_chord_strum_data)
send.pack()

window.mainloop()

# vars for saving state when window is re-opened
# prevStrum
# prevChords