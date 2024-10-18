import tkinter as tk

class SongBuilderDragAndDropFrame(tk.Canvas):
    def __init__(self, master, width, height):
        super().__init__(master=master, width=width, height=height)
        self.pack(fill="both", expand=1)
        self.dnd_accept = self.dnd_accept

    def dnd_accept(self, source, event):
        return self

    def dnd_enter(self, source, event):
        self.focus_set() # Show highlight border
        x, y = source.where(self, event)
        x1, y1, x2, y2 = source.canvas.bbox(source.id)
        dx, dy = x2-x1, y2-y1
        self.dndid = self.create_rectangle(x, y, x+dx, y+dy)
        self.dnd_motion(source, event)

    def dnd_motion(self, source, event):
        x, y = source.where(self, event)
        x1, y1, x2, y2 = self.bbox(self.dndid)
        self.move(self.dndid, x-x1, y-y1)

    def dnd_leave(self, source, event):
        # self.top.focus_set() # Hide highlight border
        self.delete(self.dndid)
        self.dndid = None

    def dnd_commit(self, source, event):
        self.dnd_leave(source, event)
        x, y = source.where(self, event)
        source.attach(self, x, False)