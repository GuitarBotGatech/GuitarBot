# GuitarBot Sequencer UI — Quickstart Guide

The **GuitarBot Sequencer** (`sequencer.html`) is a web-based timeline editor for composing robot guitar performances. Arrange pluck notes, chord symbols, and MIDI effects in a single interface, then export as JSON or send directly to the robot.

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

This launches ```OSC_Message_Receiver.py```, ```send_song_arrangement.py```, and serves the UI via localhost by using python subprocesses.

## Manual Launch

It can be useful to run each component individually for testing.

### Start GUI

1. From the GuitarBot root directory, start a simple HTTP server:
   ```bash
   python -m http.server 8000
   ```
2. Open your browser and navigate to: [http://localhost:8000/](http://localhost:8000/)

3. You will be prompted to start a new project, open an example, or import a JSON/MIDI file.
### Start GUI → GuitarBot Bridge

In a separate terminal, start the bridge that forwards arrangements from the sequencer to the robot via UDP/OSC:

```bash
python send_song_arrangement.py --serve
```

This starts an HTTP server on `localhost:8765`. The sequencer's **Send to Robot** button POSTs the current arrangement to this bridge, which converts it and sends OSC messages to the robot at `127.0.0.1:12000`.

Optional flags:
```bash
# Use a different robot IP/port
python send_song_arrangement.py --serve --ip [ip] --port 12000

# Use a different bridge port
python send_song_arrangement.py --serve --serve-port 9000
```

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
- Integrate with [OSC_Message_Send.py](../OSC_Message_Send.py) to transmit to the robot in real time.

---

**Last Updated:** March 2026  
**Version:** 1.0
