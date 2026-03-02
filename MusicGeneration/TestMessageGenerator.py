import numpy as np
from pprint import pprint
# MNN defs and Guitarbot related defs
NUM_FRETS = 10
E_MNN = 40
A_MNN = 45
D_MNN = 50
G_MNN = 55
B_MNN = 59
e_MNN = 64
MAX_MNN = B_MNN + NUM_FRETS - 1
DUR_PAD = 1.0 # Time that is added to final duration to create empty chord message


class TestMessageGenerator:
    """
    A class for generating various test message patterns for the GuitarBot.
    
    Message format: [note (int), duration (float), speed (int), slide_toggle (int), timestamp (float)]
    """
    
    def __init__(self):
        self.final_dur = 0.0  # Total duration of the last generated message sequence
    
    def prepare_messages(self, msgs):
        """
        Pipeline helper: stack list/array messages then coerce field dtypes.
        Expects an iterable of message rows; returns a Python list of rows.
        """
        msgs = self.stack_and_list(msgs)
        msgs = self.coerce_message_types(msgs)
        return msgs

    def stack_and_list(self, msgs):
        """
        Vertically stack a sequence of 1-D / list rows using numpy, then to list.
        Input: iterable of homogeneous-length sequences. Output: list of lists.
        """
        msgs = np.vstack(msgs)
        msgs = msgs.tolist()
        return msgs

    def coerce_message_types(self, msgs):
        """
        In-place type casting: note, speed, slide_toggle -> int.
        Leaves duration & timestamp as floats. Returns msgs for chaining.
        """
        for r in msgs:
            r[0] = int(r[0])
            r[2] = int(r[2])
            r[3] = int(r[3])
        return msgs

    def string_sweep(self, string, duration=1.0, speed=0, slide_toggle=0, debug_flag=False):
        """Generate a sweep across all frets on a specified string."""
        if string == 'E':
            start_MNN = E_MNN
        elif string == 'D':
            start_MNN = D_MNN
        elif string == 'B':
            start_MNN = B_MNN
        else:
            raise ValueError("Unsupported string. Use 'E', 'D', or 'B'")
        
        np_messages = []
        for i in range(0, NUM_FRETS):
            timestamp = duration*i
            timestamp = round(timestamp, 5)
            message = [start_MNN + i, 0.1, speed, slide_toggle, timestamp]
            np_messages.append(message)
            
        pluck_messages = self.prepare_messages(np_messages)
        self.final_dur = pluck_messages[-1][-1] + DUR_PAD
        return pluck_messages
   
    def tremolo_random(self, lower_bound=E_MNN, upper_bound=B_MNN + NUM_FRETS - 1, num_notes=5, interval=1, slide_toggle=0, debug_flag=False):
        """Generate random tremolo patterns with varying speeds, notes, and durations."""
        #1. Generate random speeds
        speeds = np.arange(1, 11)
        rand_speeds = speeds[np.random.choice(len(speeds), num_notes)]
        if debug_flag:
            print("Speeds: ")
            print(rand_speeds)
            print("/===================")
        
        #2. Generate random MIDI values (for the 3 current strings)
        midi_notes = np.arange(lower_bound, upper_bound)
        rand_notes = midi_notes[np.random.choice(len(midi_notes), num_notes, replace=True)]
        if debug_flag:
            print("Notes: ")
            print(rand_notes)
            print("/===================")
        
        #3. Generate random durations
        durations = np.arange(1, 5)
        rand_durations = durations[np.random.choice(len(durations), num_notes)]
        if debug_flag:
            print("Durations: ")
            print(rand_durations)
            print("/===================")

        np_messages = []
        for i in range(len(rand_speeds)):
            timestamp = np.sum(rand_durations[0:i]) if i > 0 else 0
            timestamp = round(timestamp, 5)
            message = [rand_notes[i], rand_durations[i], rand_speeds[i], slide_toggle, timestamp]
            np_messages.append(message)

        pluck_messages = self.prepare_messages(np_messages)
        self.final_dur = pluck_messages[-1][-1] + DUR_PAD
        return pluck_messages

    def tremolo_speed_sweep(self, mnn=E_MNN, duration=2):
        """Generate tremolo with increasing speed values."""
        speed = np.arange(1, 11)
        
        np_messages = []
        
        for i in range(len(speed)):
            timestamp = duration * i
            timestamp = round(timestamp, 5)
            message = [mnn, duration, speed[i], 0, timestamp]
            np_messages.append(message)
            
        pluck_messages = self.prepare_messages(np_messages)
        self.final_dur = pluck_messages[-1][-1] + DUR_PAD
        return pluck_messages

    def scale(self, scale='chromatic', mnn=40, octaves=1, duration=1.0, reflect=True, slide_toggle=0, true_dur=0.1):
        """Generate a scale pattern (major, minor, or chromatic) with optional reflection."""
        if scale == 'maj':
            base_degrees = np.array([0, 2, 4, 5, 7, 9, 11, 12])  # include octave
        elif scale == 'min':
            base_degrees = np.array([0, 2, 3, 5, 7, 8, 10, 12])
        elif scale == 'chromatic':
            base_degrees = np.arange(0, 13)  # 0..12 inclusive
        else:
            raise ValueError("Unsupported scale. Use maj, min, chromatic")

        if octaves < 1:
            self.final_dur = 0.0
            return []

        # Repeat degrees for each octave, then shift each block
        # Shape: (octaves, len(base_degrees))
        octave_offsets = (12 * np.arange(octaves)).reshape(-1, 1)
        grid = mnn + octave_offsets + base_degrees  # broadcast add

        # Flatten
        notes = grid.ravel()

        # Remove duplicated shared octave roots between blocks
        # For scales with trailing 12: drop every internal 12 except last
        if base_degrees[-1] == 12 and octaves > 1:
            # Keep first block entirely, then skip the first element of subsequent blocks
            step = len(base_degrees)
            kept = [notes[:step]]
            for o in range(1, octaves):
                kept.append(notes[o*step + 1:(o+1)*step])
            notes = np.concatenate(kept)

        # Enforce MAX_MNN
        notes = notes[notes <= MAX_MNN]
        if notes.size == 0:
            self.final_dur = 0.0
            return []

        if reflect and notes.size > 1:
            notes = np.concatenate([notes, notes[-2:0:-1]])  # mirror without duplicating endpoints
            notes = np.append(notes, mnn)
        
        # Build messages
        np_messages = []
        for i in range(len(notes)):
            timestamp = duration * i
            message = [notes[i], true_dur, 0, slide_toggle, timestamp]
            np_messages.append(message)
            
        pluck_messages = self.prepare_messages(np_messages)
        self.final_dur = pluck_messages[-1][-1] + DUR_PAD
        return pluck_messages

    #TODO: Multiphrase test


# Example usage
if __name__ == "__main__":
    generator = TestMessageGenerator()
    
    # Generate a string sweep
    messages = generator.string_sweep('E', duration=0.5)
    print(f"String sweep generated {len(messages)} messages")
    print(f"Total duration: {generator.final_dur:.2f}s")
    pprint(messages)
    
    # Generate a scale
    scale_messages = generator.scale('maj', mnn=40, octaves=2, reflect=True)
    print(f"Scale generated {len(scale_messages)} messages")
    print(f"Total duration: {generator.final_dur:.2f}s")
    pprint(scale_messages)