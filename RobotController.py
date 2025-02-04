import socket
import struct
import time

strumPos = -45       #position of strummer for next strum (-45 = top, 45 = bottom) TODO: In the long run, strum position should be handled in armlistreceiver or another script that is not constantly reinstantiated

def send_msg(type, command):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_ip = "10.2.1.177"
    udp_port = 8888
    LH = bytes('L', 'utf8')
    strum = bytes('S', 'utf8')
    pick = bytes('P', 'utf8')

    global strumPos
    message = None
    flattened = []
    if type == 'LH':
        message = LH
        flattened = [i for list in command for i in list]
    elif type == 'strum':
        message = strum
        strumPos = command[0]
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

def main(strum, LH):
    #Format of event is:
    # [event type (LH/strum/pick),
    # properties (LH can be press, slide lists, strum can be pick angle, strum speed, deflect, pick can be pick type, tremolo length, tremolo speed),
    # time]

    Events = []
    for event in LH:
        Events.append(event)

    for event in strum:
        #print("rh event", event)
        Events.append(event)

    # TODO: When UI adds picking, uncomment code below
    # for event in pick:
    #     Events.append(event)

    Events.sort(key=lambda x: x[2])

    for event in Events:
        if event[0] == 'strum':
            if event[1][0] == strumPos:
                if event[1][0] == 45:  # if initial strum is a downstrum, make sure strummer is positioned at top
                    send_msg(type='strum', command=[-45, 75, 1])
                else:  # if initial strum is an upstrum, make sure strummer is positioned at bottom
                    send_msg(type='strum', command=[45, 75, 1])
            break

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

    print("done, exiting song")
    time.sleep(2)
    lastLHidx = len(LH) - 1
    lastLHCommand = LH[lastLHidx]
    print("This is the last command: ", lastLHCommand)
    send_msg(type='LH', command= [lastLHCommand[1][0], [1,1,1,1,1,1]])
    return 0