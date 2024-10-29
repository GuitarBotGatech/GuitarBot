import socket
import struct
import time

from matplotlib.cbook import flatten

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_ip = "10.2.1.177"
udp_port = 8888
LH = bytes('L', 'utf8')
strum = bytes('S', 'utf8')

def send_msg(type, command):
    message = None
    flattened = []
    if type == 'LH':
        message = LH
        flattened = [i for list in command for i in list]
    elif type == 'strum':
        message = strum
        flattened.append(command)
    # arr = []
    # index = 0
    # for c in command:
    #     for i in c:
    #         print(i)
    #         arr[index] = i
    #         index += 1
    print("command: ", flattened)
    pCommand = struct.pack(f'<{len(flattened)}b', *flattened)
    packed_data = message + pCommand
    time.sleep(0.005)
    # self.sock.sendto(bytes(msg, 'utf8'), (self.udp_ip, self.udp_port))
    sock.sendto(packed_data, (udp_ip, udp_port))

    time.sleep(0.01)
    return 0

def main():
    #Add/remove any LH/strum events as desired to test
    #Format of event is:
    # [event type (LH/strum/pick),
    # properties (LH can be slide+press lists, strum can be pick angle--45==down strum, -45==up strum, pick can be pick/don't pick),
    # time]
    LH = [['LH', [[1, 2, 2, 1, 1, 1], [1, 2, 2, 1, 1, 1]], 0], ['LH', [[1, 1, 1, 2, 3, 2], [3, 3, 1, 2, 2, 2]], 1.193478260869565], ['LH', [[1, 1, 5, 4, 3, 3], [3, 3, 2, 2, 2, 2]], 3.130434782608695]]
    strum = [['strum', -45, 0.5217391304347826], ['strum', 45, 1.565217391304348]]

    Events = []
    for event in LH:
        Events.append(event)

    for event in strum:
        Events.append(event)

    Events.sort(key=lambda x: x[2])

    start = time.time()
    for e in Events:
        tNextEvent = e[2]
        eventType = e[0]
        if eventType == 'LH':
            send_msg(type= 'LH', command=e[1])
        elif eventType == 'strum':
            send_msg(type= 'strum', command=e[1])
        tElapsed = time.time() - start
        while tElapsed < tNextEvent:
            time.sleep(0.0001)
            tElapsed = time.time() - start

if __name__ == "__main__":
    main()