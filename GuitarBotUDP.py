import socket
import struct
import time
import serial
import numpy as np


class GuitarBotUDP:
    def fifth_poly(self, q_i, q_f, time):
        # np.linspace
        # time/0.005
        traj_t = np.arange(0, time, 0.005)
        dq_i = 0
        dq_f = 0
        ddq_i = 0
        ddq_f = 0
        a0 = q_i
        a1 = dq_i
        a2 = 0.5 * ddq_i
        a3 = 1 / (2 * time ** 3) * (20 * (q_f - q_i) - (8 * dq_f + 12 * dq_i) * time - (3 * ddq_f - ddq_i) * time ** 2)
        a4 = 1 / (2 * time ** 4) * (
                30 * (q_i - q_f) + (14 * dq_f + 16 * dq_i) * time + (3 * ddq_f - 2 * ddq_i) * time ** 2)
        a5 = 1 / (2 * time ** 5) * (12 * (q_f - q_i) - (6 * dq_f + 6 * dq_i) * time - (ddq_f - ddq_i) * time ** 2)
        traj_pos = a0 + a1 * traj_t + a2 * traj_t ** 2 + a3 * traj_t ** 3 + a4 * traj_t ** 4 + a5 * traj_t ** 5
        return traj_pos

    def __init__(self, UDP_IP, UDP_PORT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_ip = UDP_IP
        self.udp_port = UDP_PORT
        self.router_left = bytes('/lguitar', 'utf8')
        self.router_picker = bytes('/rguitar', 'utf8')

    def send_msg_left(self, iplaycommand, ifretnumber):
        # stringCount = 6
        # iplaycommand_byte = [b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00']
        # ifretnumber_byte = [b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00']
        # # tnotelen_byte = [b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00']
        # for i in range(stringCount):
        #     # print('ifrenumber[i]', ifretnumber[i])
        #     # print('ifrenumber[i] type', type(ifretnumber[i]))
        #     ifretnumber_byte[i] = int(ifretnumber[i]).to_bytes(1, 'little')
        #     iplaycommand_byte[i] = int(iplaycommand[i]).to_bytes(1, 'little')
        #     # tnotelen_byte[i] = tnotelen[i].to_bytes(2, 'little')
        # print(ifretnumber)
        # router = self.router_left
        #
        # ifretnumber_merge = ifretnumber_byte[0]
        # iplaycommand_merge = iplaycommand_byte[0]
        # # tnotelen_merge = tnotelen_byte[0]
        #
        # for i in range(stringCount - 1):
        #     ifretnumber_merge += ifretnumber_byte[i + 1]
        #     iplaycommand_merge += iplaycommand_byte[i + 1]
        #     # tnotelen_merge += tnotelen_byte[i + 1]
        #
        # message = router
        # message += iplaycommand_merge
        # message += ifretnumber_merge
        #
        # # message += tnotelen_merge
        # message += b'\x00'
        # time.sleep(0.005)
        # self.sock.sendto(message, (self.udp_ip, self.udp_port))
        # time.sleep(0.001)
        # return 0

        data = (iplaycommand, ifretnumber)

        arr = [0] * 12
        index = 0
        for d in data:
            for i in d:
                arr[index] = i
                index += 1

        packed_data = struct.pack(f'<{len(arr)}b',*arr)
        time.sleep(0.005)
        # self.sock.sendto(bytes(msg, 'utf8'), (self.udp_ip, self.udp_port))
        self.sock.sendto(packed_data, (self.udp_ip, self.udp_port))

        time.sleep(0.01)
        return 0

    def send_msg_picker(self, ipickercommand, bstartpicker, pgain, dgain, ipickerpos, ipickervel, ipickeracc,
                        isliderpos):
        router = self.router_picker
        ipickercommand_byte = ipickercommand.to_bytes(1, 'little')
        bstartpicker_byte = bstartpicker.to_bytes(1, 'little')
        pgain_byte = pgain.to_bytes(2, 'little')
        dgain_byte = dgain.to_bytes(1, 'little')
        ipickerpos_byte = ipickerpos.to_bytes(1, 'little', signed=True)
        ipickervel_byte = ipickervel.to_bytes(1, 'little')
        ipickeracc_byte = ipickeracc.to_bytes(2, 'little')
        isliderpos_byte = isliderpos.to_bytes(1, 'little', signed=True)

        message = router
        message += ipickercommand_byte
        message += bstartpicker_byte
        message += pgain_byte
        message += dgain_byte
        message += ipickerpos_byte
        message += ipickervel_byte
        message += ipickeracc_byte
        message += isliderpos_byte
        time.sleep(0.005)
        self.sock.sendto(message, (self.udp_ip, self.udp_port))
        return 0

    def send_msg_arduino(self, iplaycommand, ifretnumber):
        slider_controller = serial.Serial('/dev/ttyACM0', baudrate=115200, timeout=0.1)
        time.sleep(.01)
        print(slider_controller.read_all().decode())

        data = (iplaycommand, ifretnumber)

        arr = [0] * 12
        index = 0
        for d in data:
            for i in d:
                arr[index] = i
                index += 1

        msg = f"{chr(arr[0])}{chr(arr[1])}{chr(arr[2])}{chr(arr[3])}{chr(arr[4])}{chr(arr[5])}{chr(arr[6])}{chr(arr[7])}{chr(arr[8])}{chr(arr[9])}{chr(arr[10])}{chr(arr[11])}\n"
        slider_controller.write(bytes(msg, encoding='utf-8'))
        time.sleep(.02)

        while (slider_controller.in_waiting > 0):
            print(slider_controller.readline().decode().strip('\n\r'))

        time.sleep(0.1)

        while (slider_controller.in_waiting > 0):
            print(slider_controller.readline().decode().strip('\n\r'))
            time.sleep(0.0011)

        slider_controller.close()




def main():
    # initialize UDP socket for guitar robot
    # UDP_IP = "169.254.60.100"
    UDP_IP = "10.2.1.177"
    # UDP_PORT = 1001
    UDP_PORT = 8888
    guitarbot_udp = GuitarBotUDP(UDP_IP, UDP_PORT)

    # example to control left hand
    # ifretnumber - fret number from 1 to 10
    # iplaycommand
    # 0: idle, placeholder
    # 1: open string (will not move fret)
    # 2: press - move to the commanded fret and press
    # 3: damp - move to the commanded fret and mute
    # 4: hammer on - move to the commanded fret, and hammer onto the string
    # 5: slide - half press, move to the commanded fret, then press

    ifretnumber = [1, 2, 2, 1, 1, 1]
    iplaycommand = [1, 2, 2, 2, 1, 1]
    guitarbot_udp.send_msg_left(iplaycommand, ifretnumber)
    guitarbot_udp.send_msg_arduino(iplaycommand, ifretnumber)

    # example to control pick
    # ipickercommand
    # 1: move
    # 2: tremolo - move back and forth continuously
    # bstartpicker
    # 1: start, 0: stop. for move, it should always be set to 1. set to 0 to stop the tremolo
    # pgain - p gain value, default is 5000
    # dgain - d gain value, default is 50
    # ipickerpos - in degree. negative is clockwise, positive is counter-clockwise.
    # ipickervel - velocity of the pick, default 5
    # ipickeracc - acceleration of the pick, default  100
    guitarbot_udp.send_msg_picker(ipickercommand=1, bstartpicker=1, pgain=5000, dgain=20, ipickerpos=-30, ipickervel=5,
                                  ipickeracc=100, isliderpos=-14)


if __name__ == '__main__':
    main()
