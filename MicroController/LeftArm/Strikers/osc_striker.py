import numpy as np
from pythonosc.dispatcher import Dispatcher
from pythonosc import osc_server
import serial
import time

striker_controller = serial.Serial('/dev/tty.usbmodemFFFFFFFEFFFF1', baudrate=115200, timeout=0.1)


def handle_strike(addr, id, velocity):
    id_code = 1 << id
    msg = f"s{chr(id_code - 1)}{chr(velocity)}\n"
    striker_controller.write(bytes(msg, 'utf-8'))
    # while (striker_controller.in_waiting > 0):
    #         print(striker_controller.readline().decode())

if __name__ == "__main__":
    ip = "127.0.0.1"
    port = 5001

    dispatcher = Dispatcher()
    dispatcher.map("/striker", handle_strike)

    server = osc_server.ThreadingOSCUDPServer((ip, port), dispatcher)
    print("Serving on {}".format(server.server_address))

    try:
        server.serve_forever()
    except KeyboardInterrupt:
         print("\ncleaning up...")
         striker_controller.close()
