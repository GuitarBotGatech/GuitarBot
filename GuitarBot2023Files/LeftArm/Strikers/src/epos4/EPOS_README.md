Welcome to the deepest pits of GuitarBot! 

If you're opening this for the first time, your curiosity has either led you to the wrong place or you need to enter a rabbit hole that is way beyond your paygrade.
Either way, this file exists to tell you all about the magic of EPOS4 and the three files (at the time of writing) that exist in this directory. 
There's likely something you need to know that won't be covered here, in which case, please add it here if you find a solution. This stuff doesn't have much easily findable documentation and history tends to repeat itself.
I did NOT write 80 percent of the functions and definitions in these files, so you're getting second hand knowledge here from my own testing.

The files in this directory serve as the library to directly interact with the OpenCAN (Controller Area Network) messaging system for the EPOS4 boards.
  - This means all of these functions are extremely important and knowing how they work is fundamental to implementing new functions efficently.
  - Further documentation can be found here [EPOS4-Firmware-Specification-En.pdf](https://www.maxongroup.com/medias/sys_master/root/8834324856862/EPOS4-Firmware-Specification-En.pdf) this is your new holy text.
  - The official documentation is pretty thick and some functions may not make sense at the first glance even with it in hand. Thus, making new functions or changing old ones for the first time might be challenging. Make sure to look things over with a fresh set of eyes and try not to get tunnel visioned on a specific function.
  - It's also useful to have the Epos Studio in order to do initial startup and confirm the specs for your motors. To do so, simply connect the motor to the board, connect the board with USB to your computer, and power the board. Open Epos Studio and confirm that the node appears. Some useful tools you're gonna want to use are Startup Wizard, Object Dictionary, AutoTuning, and any positioning modes that fit your task. Below are some more detailed steps. 
  -  Good Luck!
---

## Definitions:
  - EPOS4: Refers to a modular, digital positioning controller by Maxon. They're the green boards behind the Guitar. The files in this directory interfaces with these boards directly.
  - CANOpen: Conroller Area Network. The protocol for messaging between EPOS nodes. It uses wired connections (CAN Cables) to connect EPOS4 nodes to the Master, an OpenCR board in our case.
  - SDO: Service Data Object, method for handling data from EPOS nodes with small delay (50ms). These are primarily used before `start()` is called in StrikerController, such as homing and enabling the motors.
  - PDO: Process Data Object, method for handling data from EPOS nodes in real time (1-5ms). These are primarily used after `start()` is called in StrikerController, such as moving the motors using `PDOsetPosition()` or `PDOsetTorque()`. PDO has two categories- RPDO and TPDO. 
  - NOTE: In practice, PDO is up to 50 times faster than SDO despite the small time frames. This makes it suitable for real time control. SDO is generally much easier to use so I'd recommend playing with that first if you want to get hands-on quicker. While SDO and PDO can be used at the same time, a few SDO messages in a short time frame can overload CAN traffic and put the boards in a fault state.
  - RPDO: Recieve Process Data Object, enables setting values to EPOS4 nodes in real time.
  - TPDO: Transmit Process Data Object, enables reading values from EPOS4 nodes in real time.

---
## Motor Specs
  - The first to anything involving this library is initialization. For successful initialization, it's important to know the name and type of motor you're working with. Please also take some time to familiarize yourself with the motor in Epos Studio if you haven't already. 
  - Each motor has its own set of data. Things like PID, nominal current, torque constant, etc. It's best to find the spec for the motor, provided by Maxon. For example, most motors at the time of writing are EC45 motors with encoders. The diagram for this motor looks like [this](https://www.maxongroup.com/medias/sys_master/root/8833813184542/19-EN-264.pdf)
  - 





