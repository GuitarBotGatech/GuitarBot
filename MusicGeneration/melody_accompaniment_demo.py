from transformers import AutoModelForCausalLM
from anticipation import ops
from anticipation.sample import generate
from anticipation.tokenize import extract_instruments
from anticipation.convert import events_to_midi, midi_to_events
from anticipation.config import *
from anticipation.vocab import *

from helpful import SMALL_MODEL, MEDIUM_MODEL, LARGE_MODEL, PIANO_CODE, add_rule_based_initial_chord
from mido import MidiFile

model = AutoModelForCausalLM.from_pretrained(SMALL_MODEL).cpu()

# MIDI file, a monophonic melody
name = 'twinkle'
filename = f'inputs/melody/{name}.mid'
midi = MidiFile(filename)

# get parameters to prompt generation
add_rule_based_initial_chord(midi)
events = midi_to_events(midi)
history, melody = extract_instruments(events, [PIANO_CODE])

accompaniment = generate(model, start_time=0, end_time=midi.length, inputs=history, controls=melody, top_p=.98)

# use results of generation
completed_events = ops.combine(accompaniment, melody)
mid = events_to_midi(completed_events)
mid.save(f'outputs/generated_accompaniment/{name}.mid')