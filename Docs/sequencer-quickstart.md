# GuitarBot Sequencer UI — Quickstart Guide

The **GuitarBot Sequencer** (`sequencer.html`) is a web-based timeline editor for composing robot guitar performances. Arrange pluck notes and chord symbols in a single interface, then export as JSON or send directly to the robot.

## Quick Launch

### Reset the Hardware

Before starting, ensure the picker motors are depressed all the way down. This can be done with a light pat.

### Start the OpenCR board

Arduino IDE path as of March 2026:
```/home/guitarbot/Apps/Arduino IDE/arduino-ide_2.3.7_Linux_64bit```

Launch the IDE, open ```Strikers.ino```, and upload it to the OpenCR board at ```dev/ttyACM0```. If this errors out, try again. If it continues to error out, unplug the USB and plug it back in.

Uploading is only necessary if the C++/Arduino code has been changed. Instead, you can simply press the reset button on the OpenCR board, which is located close to the microUSB port.

Once ready, the PSU's can be switched on. Finally, open the Arduino Serial Monitor to start the homing sequence.

Ensure the ethernet cable is connected from the computer to the board, and this step is done!

### Start the Python Code

All other code can then be initialized via the launch script:
```
conda activate guitarbot_env
python launch.py
```

This starts a single Flask process that serves the sequencer UI and accepts:

- `POST /play` — arrangement JSON, planned and sent to OpenCR
- `POST /reset` — home motors

Plan without moving the robot:
```
python launch.py --dry-run
```

The UI is at [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

## Manual Launch

Equivalent to `python launch.py --no-browser`:
```
python launch.py --no-browser
```

Then open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). You will be prompted to start a new project, open an example, or import a JSON/MIDI file.

The sequencer's **Send to Robot** button POSTs the current arrangement to `POST /play` on the same origin. **Reset Bot** calls `POST /reset`.

## GUI Reference

UI details have been moved into dedicated documentation:

- [GUI Overview](gui/overview.md)

The GUI overview includes:

- Interface layout and toolbar elements.
- Event editing workflows (pluck, chord, MIDI).
- Playback, navigation, and JSON preview behavior.
- Keyboard shortcuts and UI tips.
- GUI-specific troubleshooting.

## Next Steps

- See [Song Format & Schema](song-format/schema.md) for detailed JSON structure.
- Review [Arrangement Plan](song-format/arrangement-plan.md) for timeline transforms and composition strategies.

---

**Last Updated:** September 2026  
**Version:** 1.1
