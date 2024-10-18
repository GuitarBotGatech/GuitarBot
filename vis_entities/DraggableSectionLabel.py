import tkinter as tkinter
# import tkinter.dnd as Tkdnd # I copied the source code instead of importing this the sane way?

__all__ = ["dnd_start", "DndHandler"]


# The factory function

def dnd_start(source, event):
    h = DndHandler(source, event)
    if h.root is not None:
        return h
    else:
        return None


class DndHandler:

    root = None

    def __init__(self, source, event):
        if event.num > 5:
            return
        root = event.widget._root()
        try:
            root.__dnd
            return # Don't start recursive dnd
        except AttributeError:
            root.__dnd = self
            self.root = root
        self.source = source
        self.target = None
        self.initial_button = button = event.num
        self.initial_widget = widget = event.widget
        self.release_pattern = "<B%d-ButtonRelease-%d>" % (button, button)
        self.save_cursor = widget['cursor'] or ""
        widget.bind(self.release_pattern, self.on_release)
        widget.bind("<Motion>", self.on_motion)
        widget['cursor'] = "hand2"

    def __del__(self):
        root = self.root
        self.root = None
        if root is not None:
            try:
                del root.__dnd
            except AttributeError:
                pass

    def on_motion(self, event):
        x, y = event.x_root, event.y_root
        target_widget = self.initial_widget.winfo_containing(x, y)
        source = self.source
        new_target = None
        while target_widget is not None:
            try:
                attr = target_widget.dnd_accept
            except AttributeError:
                pass
            else:
                new_target = attr(source, event)
                if new_target is not None:
                    break
            target_widget = target_widget.master
        old_target = self.target
        if old_target is new_target:
            if old_target is not None:
                old_target.dnd_motion(source, event)
        else:
            if old_target is not None:
                self.target = None
                old_target.dnd_leave(source, event)
            if new_target is not None:
                new_target.dnd_enter(source, event)
                self.target = new_target

    def on_release(self, event):
        self.finish(event, 1)

    def cancel(self, event=None):
        self.finish(event, 0)

    def finish(self, event, commit=0):
        target = self.target
        source = self.source
        widget = self.initial_widget
        root = self.root
        try:
            del root.__dnd
            self.initial_widget.unbind(self.release_pattern)
            self.initial_widget.unbind("<Motion>")
            widget['cursor'] = self.save_cursor
            self.target = self.source = self.initial_widget = self.root = None
            if target is not None:
                if commit:
                    target.dnd_commit(source, event)
                else:
                    target.dnd_leave(source, event)
        finally:
            source.dnd_end(target, event)


class DraggableSectionLabel:
    existing_draggables_list = []
    LEFTMOST_X_POS = 30
    insert_x_pos = LEFTMOST_X_POS
    separation = 80

    def __init__(self, name, mid_height_y, section_id):
        DraggableSectionLabel.existing_draggables_list.append(self)

        self.name = name
        self.mid_height_y = mid_height_y
        self.section_id = section_id

        self.canvas = self.label = self.id = None

    def attach_at_end(self, canvas):
        self.attach(canvas, self.insert_x_pos, True)
        DraggableSectionLabel.insert_x_pos += DraggableSectionLabel.separation
    
    def attach(self, canvas, x, initial_add):
        if canvas is self.canvas:
            new_x = self.shift_others_to_accomodate_drop(x)
            self.canvas.coords(self.id, new_x, self.mid_height_y)
            return
        if self.canvas is not None:
            self.detach()
        if canvas is None:
            return
        label = tkinter.Label(canvas, textvariable=self.name,
                              borderwidth=2, relief="raised", bg='navy blue', fg='white', width=6, cursor='hand2')
        id = canvas.create_window(x, self.mid_height_y, window=label, anchor="nw")
        self.canvas = canvas
        self.label = label
        self.id = id
        # left-click to drag section
        label.bind("<ButtonPress-1>", self.press) # was ButtonPress
        
        # right-click to remove section (needs two bindings to work on both trackpad and mouse)
        label.bind("<ButtonRelease-2>", self.destroy)
        label.bind("<ButtonRelease-3>", self.destroy)

    # Shifts other boxes and returns new x-coord
    def shift_others_to_accomodate_drop(self, x):
        new_x = round((x - DraggableSectionLabel.LEFTMOST_X_POS) / DraggableSectionLabel.separation) * DraggableSectionLabel.separation # reorients about leftmost x=0

        if (new_x < 0):
            new_x = 0
        else:
            new_x = min(new_x, DraggableSectionLabel.separation * (len(DraggableSectionLabel.existing_draggables_list) - 1))

        old_x = self.canvas.coords(self.id)[0]
        old_idx = int((old_x - DraggableSectionLabel.LEFTMOST_X_POS) / DraggableSectionLabel.separation)
        new_idx = int(new_x / DraggableSectionLabel.separation)
        
        del DraggableSectionLabel.existing_draggables_list[old_idx]

        if new_idx < old_idx: # shifted left, others go right
            for i in range(new_idx, old_idx):
                DraggableSectionLabel.existing_draggables_list[i].shift_box_right()
        else: # shifted right or now shift
            for i in range(old_idx, new_idx):
                DraggableSectionLabel.existing_draggables_list[i].shift_box_left()

        DraggableSectionLabel.existing_draggables_list.insert(new_idx, self)

        new_x += DraggableSectionLabel.LEFTMOST_X_POS
        return new_x

    def shift_box_left(self):
        old_x = self.canvas.coords(self.id)[0]
        self.canvas.coords(self.id, old_x - DraggableSectionLabel.separation, self.mid_height_y)

    def shift_box_right(self):
        old_x = self.canvas.coords(self.id)[0]
        self.canvas.coords(self.id, old_x + DraggableSectionLabel.separation, self.mid_height_y)

    def destroy(self, event):
        self.detach()
        DraggableSectionLabel.insert_x_pos -= DraggableSectionLabel.separation

        i = 0

        while i < len(DraggableSectionLabel.existing_draggables_list):
            if DraggableSectionLabel.existing_draggables_list[i] == self:
                DraggableSectionLabel.existing_draggables_list.pop(i)
                shift_left = True
                break
            i += 1

        while i < len(DraggableSectionLabel.existing_draggables_list):
            DraggableSectionLabel.existing_draggables_list[i].shift_box_left()
            i += 1

    def detach(self):
        canvas = self.canvas
        if canvas is None:
            return
        id = self.id
        label = self.label
        self.canvas = self.label = self.id = None
        canvas.delete(id)
        label.destroy()

    def press(self, event):
        if dnd_start(self, event):
            # where the pointer is relative to the label widget:
            self.x_off = event.x
            self.y_off = event.y
            # where the widget is relative to the canvas:
            self.x_orig, self.y_orig = self.canvas.coords(self.id)

    def move(self, event):
        x, y = self.where(self.canvas, event)
        self.canvas.coords(self.id, x, y)

    def putback(self):
        self.canvas.coords(self.id, self.x_orig, self.y_orig)

    def where(self, canvas, event):
        # where the corner of the canvas is relative to the screen:
        x_org = canvas.winfo_rootx()
        y_org = canvas.winfo_rooty()
        # where the pointer is relative to the canvas widget:
        x = event.x_root - x_org
        y = event.y_root - y_org
        # compensate for initial pointer offset
        return x - self.x_off, y - self.y_off

    def dnd_end(self, target, event):
        pass