# EncoderFeedback tools

This folder contains small utilities to help drive the robot using OSC and to capture encoder feedback over UDP.

Prereqs:
- Run `arm_list_recieverNN.py` (it listens for OSC on 127.0.0.1:12000)
- The robot firmware should include EncoderFeedbackCollector and send UDP feedback to your PC on port 8889 (see its `python_host_`)
- Python packages: `python-osc`

## Files
- `OSCClient.py`: tiny OSC sender.
- `EncoderUDPReceiver.py`: listens on UDP 8889 and prints/saves encoder packets.
- `FeedbackSession.py`: sends one OSC message then records encoder packets for a duration to CSV.

## Quick start
- Send a dynamics message:
  - Windows PowerShell:
    ```powershell
    python -m EncoderFeedback.OSCClient --preset dyn --args 40 45 50
    ```
- Record encoder data for 5s to CSV while sending /Dyn 40 45 50:
  - Windows PowerShell:
    ```powershell
    python -m EncoderFeedback.FeedbackSession --address /Dyn --args 40 45 50 --duration 5 --csv run.csv
    ```
- Just listen and log to CSV:
  - Windows PowerShell:
    ```powershell
    python -m EncoderFeedback.EncoderUDPReceiver --duration 10 --csv enc.csv
    ```

Notes:
- The packet format is 8 bytes per reading: 1 (motor_id) + 4 (int32 position LE) + 2 (uint16 status LE) + 1 (checksum).
- Some firmware may batch multiple packets per UDP datagram; the receiver parses them sequentially.
- Ensure `EncoderFeedbackCollector`'s `python_host_` is set to your machine's IP on the robot network.
