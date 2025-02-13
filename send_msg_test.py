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
        flattened = [i for i in command]
    elif type == 'pick':
        message = pick
        flattened = [i for list in command for i in list]

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
    # properties (LH can be slide, press lists, strum can be pick angle--45==down strum, -45==up strum, pick can be don't pick (0), pick (1), tremolo (2) + length of a quarter note IN TRAJ POINTS + speed of tremolo IN TRAJ POINTS),
    # time]

    # [command type, [[Slide list], [press list]], timestamp]

    # Base Demo
    #LH = [['LH', [[1, 3, 2, 1, 1, 1], [3, 2, 2, 1, 2, 1]], 0], ['LH', [[3, 2, 2, 1, 1, 3], [2, 2, 1, 1, 1, 2]], 3], ['LH', [[1, 1, 2, 2, 1, 1], [3, 1, 2, 2, 2, 1]], 6], ['LH', [[1, 1, 3, 2, 1, 1], [3, 3, 2, 2, 2, 2]], 9], ['LH', [[1, 3, 2, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 12]]
    #strum = [['strum', [45, 75, 0], 0], ['strum', [-45, 75, 0], 3], ['strum', [45, 75, 0], 6], ['strum', [-45, 75, 0], 9]] # 0, 3, 6, 9
    # pick = [['pick', [[1, 1, 1, 2, 1, 1], [120, 5]], 1], ['pick', [[1, 1, 1, 2, 1, 1], [120, 5]], 4], ['pick', [[1, 1, 1, 2, 1, 1], [120, 5]], 7], ['pick', [[1, 1, 1, 2, 1, 1], [120, 5]], 10]]

    # Smoke on the Water Demo
    # LH = [['LH', [[1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 0], ['LH', [[1, 1, 1, 3, 1, 1], [1, 1, 1, 2, 1, 1]], 0.5],
    #       ['LH', [[1, 1, 1, 5, 1, 1], [1, 1, 1, 2, 1, 1]], 1], ['LH', [[1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 1.75],
    #       ['LH', [[1, 1, 1, 3, 1, 1], [1, 1, 1, 2, 1, 1]], 2.25], ['LH', [[1, 1, 1, 6, 1, 1], [1, 1, 1, 2, 1, 1]], 2.75],
    #       ['LH', [[1, 1, 1, 5, 1, 1], [1, 1, 1, 2, 1, 1]], 2.85], ['LH', [[1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 4],
    #       ['LH', [[1, 1, 1, 3, 1, 1], [1, 1, 1, 2, 1, 1]], 4.5], ['LH', [[1, 1, 1, 5, 1, 1], [1, 1, 1, 2, 1, 1]], 5],
    #       ['LH', [[1, 1, 1, 3, 1, 1], [1, 1, 1, 2, 1, 1]], 5.75], ['LH', [[1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 6],
    #       ['LH', [[1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 8], ['LH', [[1, 1, 1, 3, 1, 1], [1, 1, 1, 2, 1, 1]], 8.5],
    #       ['LH', [[1, 1, 1, 5, 1, 1], [1, 1, 1, 2, 1, 1]], 9], ['LH', [[1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 9.75],
    #       ['LH', [[1, 1, 1, 3, 1, 1], [1, 1, 1, 2, 1, 1]], 10.25], ['LH', [[1, 1, 1, 6, 1, 1], [1, 1, 1, 2, 1, 1]], 10.75],
    #       ['LH', [[1, 1, 1, 5, 1, 1], [1, 1, 1, 2, 1, 1]], 10.85], ['LH', [[1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 12],
    #       ['LH', [[1, 1, 1, 3, 1, 1], [1, 1, 1, 2, 1, 1]], 12.5], ['LH', [[1, 1, 1, 5, 1, 1], [1, 1, 1, 2, 1, 1]], 13],
    #       ['LH', [[1, 1, 1, 3, 1, 1], [1, 1, 1, 2, 1, 1]], 13.75], ['LH', [[1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 14]]
    # pick = [['pick', [[1, 1, 1, 1, 1, 1], [5, 5]], 0], ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 0.5],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [60, 5]], 1], ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 1.75],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 2.25], ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 2.75],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [60, 5]], 2.85], ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 4],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 4.5], ['pick', [[1, 1, 1, 2, 1, 1], [60, 5]], 5],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 5.75], ['pick', [[1, 1, 1, 2, 1, 1], [80, 5]], 6],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 8], ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 8.5],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [60, 5]], 9], ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 9.75],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 10.25], ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 10.75],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [60, 5]], 10.85], ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 12],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 12.5], ['pick', [[1, 1, 1, 2, 1, 1], [60, 5]], 13],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 13.75], ['pick', [[1, 1, 1, 2, 1, 1], [80, 5]], 14]]
    # strum = []

    #Tremolo demo
    LH = [['LH', [[1, 1, 1, 1, 1, 1], [2, 1, 1, 1, 1, 1]], 0], ['LH', [[2, 1, 1, 1, 1, 1], [2, 1, 1, 1, 1, 1]], 1], ['LH', [[3, 1, 1, 1, 1, 1], [2, 1, 1, 1, 1, 1]], 2], ['LH', [[4, 1, 1, 1, 1, 1], [2, 1, 1, 1, 1, 1]], 3], ['LH', [[5, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 5]]
    pick = [['pick', [[2, 2, 1, 1, 1, 1], [120, 5]], 0]]
    # strum = [][[1, 3, 2, 1, 1, 1], [3, 2, 2, 1, 2, 1]]

    # Extra Demo
    # LH = [['LH', [[1, 1, 3, 2, 1, 1], [3, 3, 2, 2, 2, 2]], 0],
    #       ['LH', [[1, 3, 2, 1, 1, 1], [3, 2, 2, 1, 2, 1]], 2.5],
    #       ['LH', [[3, 2, 2, 1, 1, 3], [2, 2, 1, 1, 1, 2]], 5.5],
    #       ['LH', [[1, 3, 2, 1, 1, 1], [3, 2, 2, 1, 2, 1]], 9],
    #       ['LH', [[1, 1, 1, 5, 1, 1], [1, 1, 1, 1, 1, 1]], 10],
    #       ['LH', [[1, 1, 1, 3, 1, 1], [1, 1, 1, 2, 1, 1]], 11],
    #       ['LH', [[1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 11.5]]
    # pick = [['pick', [[1, 1, 1, 1, 1, 1], [5, 5]], 1], ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 1.5],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [120, 15]], 2],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 4], ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 4.5],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [120, 10]], 5],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 6.5], ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 7],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 7.5], ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 8],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [120, 5]], 8.5],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 10], ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 10.5],
    #         ['pick', [[1, 1, 1, 2, 1, 1], [20, 5]], 11], ['pick', [[1, 1, 1, 2, 1, 1], [120, 5]], 11.5]]
    # strum = [['strum', [45, 75, 0], 0], ['strum', [-45, 75, 0], 2.5], ['strum', [45, 75, 0], 3], ['strum', [-45, 75, 0], 5.5], ['strum', [45, 75, 0], 9]]


    # Slide Testing
    # LH = [['LH', [[1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 0], ['LH', [[5, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 2], ['LH', [[3, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 4], ['LH', [[1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 6], ['LH', [[6, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 8], ['LH', [[7, 5, 5, 1, 1, 1], [1, 1, 1, 1, 1, 1]], 10]]
    # LH = [['LH', [[1, 1, 1, 2, 3, 2], [3, 3, 1, 2, 2, 2]], 0], ['LH', [[1, 1, 1, 2, 3, 2], [1, 1, 1, 1, 1, 1]], 2]]
    # LH = []
    # strum = [['strum', [45, 45, 0], 0]]
    strum = []
    # pick = []
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