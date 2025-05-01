## This file describes all of the relevant files within this directory other than EPOS4. For EPOS4 descriptions, refer to the EPOS4 folder README.
------
## StrikerController

The `StrikerController` class handles the initialization, homing, and motion of all actuators (strikers, pressers, pluckers, and strummer mechanisms) for GuitarBot.
It manages the communication with each actuator, handles trajectory execution, and provides interfaces for higher-level commands and event-driven actions for any given motor.

---

**Key Features**

- **Instancing**:
Only one instance of `StrikerController` exists at a time, managed via `createInstance()` and `destroyInstance()`.
- **Initialization and Homing**:
    - Initializes all actuators (sliders, pressers, strummer sliders, strummer pickers, and pluckers), each with appropriate motor specifications.
    - Executes homing procedures for each actuator type in the above sequence.
    - Homing status is checked in loops with timeouts at each level in the sequence.
- **Motor and Device Management**:
    - Each actuator is represented by a `Striker` object, which directly interacts with lower-level motor control via the `Epos4` functions.
    - Provides methods to enable/disable PDO (Process Data Object) communication and to enable/disable actuators.
- **Event Execution**:
    - handled by `processTrajPoints(float *trajPoint)`:
            - This function is called by the Strikers.ino script.
            - Points are expected to be in an array format, with x points where x is the combined number of motors.
            - The point of this function is to read points and push them to the queue.
- **Real-Time Control**:
    - Uses a hardware timer (e.g., `RPDOTimer`) to trigger periodic updates, dequeue trajectory points, and command actuators at a fixed rate (default: 5 ms,  don't change this definition unless you know what you're doing.).
    - Low level RPDO and TPDO specifications are handled in the README file within the EPOS folder.
    - In this file,  `RPDOTimerIRQHandler()` attaches a handles the loop that is refreshed every 5ms. If there is a point on the queue, it uses `.rotate()` or `.applyTorque()` to move the motors. on time.
    - Discontinuities are NOT handled to correct the motors. The motors will simply stop if any value in the previous point is beyond a certain threshold from the current point.
      - For example, [0,100,0] -> [0,1000, 1] would result in a discontinuity for values thresholds above 900.  
- **Fault Handling and Reset**:
    - Provides reset functions to reinitialize actuators and CAN communication.

---


**Initialization Sequence**

- **CAN Bus Setup:**
If enabled, initializes the CAN bus at 1 Mbps and attaches a receive interrupt handler.
- **Actuator Initialization:**
    - Sliders (NUM_STRIKERS)
    - Pressers (NUM_PRESSERS)
    - Strummer Sliders (NUM_STRUMMER_SLIDERS)
    - Strummer Pickers (NUM_STRUMMER_PICKERS)
    - Pluckers (NUM_PLUCKERS)
Each device is initialized with the correct `MotorSpec` and encoder resolution along with other motor data, then homed.
- **Homing:**
Each group of actuators is homed in sequence. The controller waits until all axes in a group report homing complete or a timeout occurs.

- **Start:**
  All motors will be enabled then engage PDO. The RPDO timer will start and the queue will start being read.

---

**Fault Tolerance and Reset**

- **Reset Functions:**
Allow for safe reinitialization of all actuators and CAN communication, either with or without terminating the CAN bus.
- **Fault Monitoring:**
Devices are checked for faults, and recovery routines can be triggered to clear errors and re-enable operation. 

---
**Testing**
- Interpolation functions are provided at the C level with example functions should you want to use them for testing or some complex motion that C affords. Though, it might be easier to try this in python since you'll have access to libraries that can graph the lines you make.
- The basic idea is to save empty arrays, put interpolated points into each array, then concatenate then rotate the matrix, and push each point to the queue. Local testing like this requires you to have a valid point for every motor or you'll run into discontinuities. 
- Check `executeSlide()` for a hint of what a slide motion would look like at the C level. It includes unpressing a set of motors, sliding, then pressing the motors.
- Good luck if you end up having to do this... 

---
**MISC and hints**

- In my experience, float `all_Trajs[][]` might as well be magical. Why? Try changing the size and seeing what breaks (or what DOESN'T break). If you're adding to the queue, you should be using this array. Why? No clue. Is it fixable? Probably, but it is quite funny. 
- `canRxHandle()` and `RPDOTimer()` are very easy to overload. For example, trajectory generation functions do NOT belong in here, unless you find a way to make them belong there. Otherwise, you risk timing out the controllers.
- If the motors aren't moving the way you want, this is the best place to start looking if you think your trajectory looks correct in Python.
- If you want to read real time information, you need TPDO using `canRxHandle()`. If you want to move or otherwise adjust the motors in real time, you need RPDO with `RPDOTimer()`. Check out the EPOS4 folder for more information before adding to these functions, though. 
- Motors are referenced with an array of length x + 1 where x is the number of total motors and index 0 is a placeholder value since you can't have a board ID of 0.
- set `run_bot` to false if you need to check if points are being pushed and popped from the queue correctly. You should always do this anyway if you're doing something experimental. 
- This code is ultimately getting uploaded to an OpenCR; there are data restrictions. Exceeding these restrictions and other runtime errors result in very weird error messages that can be uninformative. If you run into these, double check the size of the variables you're making and that you're indexing properly first. 
---


## def.h

The `def.h` header is a central configuration file that defines key constants, macros, and lookup tables for the StrikerController system. It specifies the hardware layout, buffer sizes, actuator counts, and various parameters used in most files in this directory.

---

**Key Definitions and Constants**


| Name | Value / Description |
| :-- | :-- |
| `IP_ADDR` | "10.2.1.177" - Default IP address for the controller |
| `MASTER_ADDR` | "10.2.1.1" - Master device IP address |
| `PORT` | 8888 - Network port for communication |
| `CS_PIN` | 10 - Chip select pin for hardware interface |
| `MAX_BUFFER_SIZE` | 1024 - Maximum size for data buffers |
| `NUM_STRIKERS` | 6 - Number of striker actuators (sliders) |
| `NUM_PRESSERS` | 6 - Number of presser actuators |
| `NUM_PLUCKERS` | 3 - Number of plucker actuators |
| `NUM_STRUMMER_SLIDERS` | 1 - Number of strummer slider actuators |
| `NUM_STRUMMER_PICKERS` | 1 - Number of strummer picker actuators |
| `NUM_MOTORS` | Sum of all actuators (strikers, pressers, strummer sliders, strummer pickers, pluckers) |
| `NUT_POS` | 0 - Reference position (nut) for the Guitar |
| `NUM_BYTES_PER_VALUE` | `sizeof(uint16_t)` - Data size per value |
| `ENCODER_DIR` | 1 - Encoder direction multiplier |
| `kStrikerDirection` | Lookup table for direction inversion per actuator (0: normal, 1: flipped) |
| `FRET_LENGTHS` | `{0, 43, 76, 107, 134, 163, 187, 210, 234, 256}` - Fret positions in mm for the Guitar. Only needed for local trajectory generation. |
| `HOME_POSITION` | 25 (degrees) - Default home position for actuators. Unused |
| `P2P_MULT` | 100.f - Point-to-point multiplier for motion scaling. Unused |
| `MAX_TRAJ_POINTS` | 20 - Maximum trajectory points per movement. Unused |
| `SCALE_LENGTH` | 645 (mm) - Scale length of the instrument. Only needed for local trajectory generation |
| `NUM_POINTS_IN_TRAJ_FOR_HIT` | 4 - Number of points for the "hit" phase of a trajectory. Unused |
| `NUM_POINTS_IN_TRAJ_FOR_UP` | 0 - Number of points for the "up" phase of a trajectory. Unused |
| `DISCONTINUITY_THRESHOLD` | 10000 - Threshold for detecting trajectory discontinuities in RPDOtimer within `StrikerController` |
| `BUFFER_TIME` | 1 - Time buffer for trajectory planning. Unused |
| `CLEAR_FAULT_TIMER_INTERVAL` | 100 (ms) - Interval for clearing faults. Unexplored, probably useful |
| `MAX_STRIKER_ANGLE_DEG` | 180 - Maximum angle for striker movement (degrees). Unused |


---

**Usage Notes**

- **Actuator Indexing**:
The constants for actuator counts (`NUM_STRIKERS`, `NUM_PRESSERS`, etc.) are used throughout the code to size arrays and iterate over actuator groups. The `NUM_MOTORS` macro provides the total count for unified loops and buffer allocations.
- **Direction Table**:
The `kStrikerDirection` array allows the system to account for mechanical inversion in certain actuators f they're flipped in an opposite direction for example
- **Fret Positioning**:
The `FRET_LENGTHS` array provides precomputed fret positions for precise slider targeting, enabling accurate musical pitch control.
- **Trajectory Planning**:
Parameters such as `MAX_TRAJ_POINTS`, `NUM_POINTS_IN_TRAJ_FOR_HIT`, and `NUM_POINTS_IN_TRAJ_FOR_UP` are critical for defining the resolution and phases of actuator movements.
- **Safety and Fault Handling**:
The `DISCONTINUITY_THRESHOLD` and `CLEAR_FAULT_TIMER_INTERVAL` constants are used to detect and recover from motion errors or hardware faults.

---

**Example Inclusion**

```cpp
#include "def.h"

// Example: Using NUM_STRIKERS to initialize an array
Striker strikers[NUM_STRIKERS];
```


---

**Summary**

`def.h` provides foundational hardware and motion parameters, ensuring consistency and maintainability across the StrikerController codebase. Adjustments to this file allow for quick adaptation to different hardware configurations or performance requirements[^1].

<div style="text-align: center">⁂</div>

[^1]: def.h

[^2]: ErrorDef.h

[^3]: striker.h

[^4]: strikerController.h

[^5]: epos4_def.h

[^6]: epos4.h

[^7]: epos4.cpp

[^8]: strikerController.h




