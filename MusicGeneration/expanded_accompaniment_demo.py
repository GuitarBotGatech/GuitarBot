from transformers import AutoModelForCausalLM
from anticipation import ops
from anticipation.sample import generate
from anticipation.convert import events_to_midi, midi_to_events
from anticipation.config import *
from anticipation.vocab import *

from helpful import SMALL_MODEL, MEDIUM_MODEL, LARGE_MODEL, GUITAR_CODE, get_tempo_from_midi
from mido import MidiFile, Message, tick2second

model = AutoModelForCausalLM.from_pretrained(SMALL_MODEL).cpu()

# MIDI file, single track chord progression, set_tempo metadata required
name = '1-1-4'
filename = f'inputs/accompaniment/{name}.mid'
midi = MidiFile(filename)

# input details
beats_per_bar = 4
num_input_bars = 3

# get usable parameters for generation
events = midi_to_events(midi)
bar_duration = tick2second(beats_per_bar*midi.ticks_per_beat, ticks_per_beat=midi.ticks_per_beat, tempo=get_tempo_from_midi(midi))
input_bars = ops.clip(events, 0, num_input_bars*bar_duration, clip_duration=False)

num_output_bars = 12
extended_accompaniment = generate(model, start_time=num_input_bars*bar_duration, end_time=num_output_bars*bar_duration, inputs=input_bars, controls=None, top_p=.95)

# use generated result
mid = events_to_midi(extended_accompaniment)
mid.tracks[0].insert(0, Message('program_change', program=GUITAR_CODE, channel=0))
mid.save(f'outputs/expanded_accompaniment/{name}.mid')