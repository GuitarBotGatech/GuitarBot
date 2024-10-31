import socket
import struct
import time

from matplotlib.cbook import flatten

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_ip = "10.2.1.177"
udp_port = 8888
LH = bytes('L', 'utf8')
strum = bytes('S', 'utf8')
pick = bytes('P', 'utf8')

def send_msg(type, command):
    message = None
    flattened = []
    if type == 'LH':
        message = LH
        flattened = [i for list in command for i in list]
    elif type == 'strum':
        message = strum
        flattened.append(command)
    elif type == 'pick':
        message = pick
        flattened = [i for i in command]

    print(type, ": ", flattened)
    pCommand = struct.pack(f'<{len(flattened)}b', *flattened)
    packed_data = message + pCommand
    time.sleep(0.005)
    # self.sock.sendto(bytes(msg, 'utf8'), (self.udp_ip, self.udp_port))
    sock.sendto(packed_data, (udp_ip, udp_port))

    time.sleep(0.01)
    return 0

def main():
    #Add/remove any LH/strum/pick events as desired to test
    #Format of event is:
    # [event type (LH/strum/pick),
    # properties (LH can be press, slide lists, strum can be pick angle--45==down strum, -45==up strum, pick can be pick/don't pick),
    # time]
    LH = [['LH', [[1, 2, 2, 1, 1, 1], [1, 2, 2, 1, 1, 1]], 0],
          ['LH', [[3, 3, 1, 2, 2, 2], [1, 1, 1, 2, 3, 2]], 2.6086956521739126],
          ['LH', [[3, 3, 2, 2, 2, 2], [1, 1, 5, 4, 3, 3]], 4.173913043478261],
          ['LH', [[1, 1, 1, 1, 1, 1], [1, 1, 5, 4, 3, 3]], 8]]
    strum = [['strum', -45, 1.0434782608695652],
             ['strum', 45, 3.173913043478261]]
    pick = [['pick', [1, 1, 1, 1, 1, 1], 5.217391304347825],
            ['pick', [0, 1, 1, 0, 0, 1], 6.26086956521739]]

    Events = []
    for event in LH:
        Events.append(event)

    for event in strum:
        Events.append(event)

    for event in pick:
        Events.append(event)

    Events.sort(key=lambda x: x[2])

    print("4")
    time.sleep(1)
    print("3")
    time.sleep(1)
    print("2")
    time.sleep(1)
    print("1")
    time.sleep(1)

    start = time.time()
    for e in Events:
        tNextEvent = e[2]
        eventType = e[0]
        # if eventType == 'LH':
        #     send_msg(type= 'LH', command=e[1])
        # elif eventType == 'strum':
        #     send_msg(type= 'strum', command=e[1])
        # elif eventType == 'pick':
        #     send_msg(type= 'pick', command=e[1])
        # tElapsed = time.time() - start
        # print(tElapsed)
        # while tElapsed < tNextEvent:
        #     time.sleep(0.0001)
        #     tElapsed = time.time() - start

        # Calculate the target time for the next event
        target_time = start + tNextEvent

        # Wait until the target time
        tElapsed = time.time()
        while tElapsed < target_time:
            time.sleep(0.0001)  # Small sleep to avoid busy waiting
            tElapsed = time.time()  # Update elapsed time

        # Send the event message
        if eventType == 'LH':
            send_msg(type='LH', command=e[1])
        elif eventType == 'strum':
            send_msg(type='strum', command=e[1])
        elif eventType == 'pick':
            send_msg(type='pick', command=e[1])

        # Print elapsed time for debugging
        tElapsed = time.time() - start
        print("Elapsed time:", tElapsed)

if __name__ == "__main__":
    main()