from transformers import AutoModelForCausalLM
from anticipation import ops
from anticipation.sample import generate
from anticipation.tokenize import extract_instruments
from anticipation.convert import events_to_midi, midi_to_events
from anticipation.config import *
from anticipation.vocab import *

from helpful import SMALL_MODEL, MEDIUM_MODEL, LARGE_MODEL, GUITAR_CODE, add_rule_based_initial_note
from mido import MidiFile

model = AutoModelForCausalLM.from_pretrained(SMALL_MODEL).cpu()

# MIDI file, single track chord progression
name = '1_to_4'
filename = f'inputs/accompaniment/{name}.mid'
midi = MidiFile(filename)

add_rule_based_initial_note(midi)
midi.save('outputs/temp_melody.mid')
events = midi_to_events(midi)
chords, init_melody = extract_instruments(events, [GUITAR_CODE])

melody = generate(model, start_time=0, end_time=midi.length, inputs=init_melody, controls=chords, top_p=.98)

# use generated result
completed_events = ops.combine(chords, melody)
mid = events_to_midi(completed_events)
mid.save(f'outputs/generated_melody/{name}.mid')