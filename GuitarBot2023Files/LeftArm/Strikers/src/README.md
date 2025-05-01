## This file describes all the files within this directory other than EPOS4. For EPOS4 descriptions, refer to the EPOS4 folder README
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



