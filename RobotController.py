import socket
import struct
import time

# def send_msg(type, command):
#     sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     udp_ip = "10.2.1.177"
#     udp_port = 8888
#     LH = bytes('L', 'utf8')
#     strum = bytes('S', 'utf8')
#     pick = bytes('P', 'utf8')
#
#     message = None
#     flattened = []
#     if type == 'LH':
#         message = LH
#         flattened = [i for list in command for i in list]
#     elif type == 'strum':
#         message = strum
#         flattened.append(command)
#     elif type == 'pick':
#         message = pick
#         flattened = [i for i in command]
#
#     print(type, ": ", flattened)
#     pCommand = struct.pack(f'<{len(flattened)}b', *flattened)
#     packed_data = message + pCommand
#     time.sleep(0.005)
#     sock.sendto(packed_data, (udp_ip, udp_port))
#
#     time.sleep(0.01)
#     return 0

# def main(strum, LH):
#     #Format of event is:
#     # [event type (LH/strum/pick),
#     # properties (LH can be press, slide lists, strum can be pick angle--45==down strum, -45==up strum, pick can be pick/don't pick),
#     # time]
#
#     Events = []
#     for event in LH:
#         Events.append(event)
#
#     for event in strum:
#         #print("rh event", event)
#         Events.append(event)
#
#     # TODO: When UI adds picking, uncomment code below
#     # for event in pick:
#     #     Events.append(event)
#
#     Events.sort(key=lambda x: x[2])
#
#     print("4")
#     time.sleep(1)
#     print("3")
#     time.sleep(1)
#     print("2")
#     time.sleep(1)
#     print("1")
#     time.sleep(1)
#
#     start = time.time()
#     for e in Events:
#         tNextEvent = e[2]
#         eventType = e[0]
#
#         # Calculate the target time for the next event
#         target_time = start + tNextEvent
#
#         # Wait until the target time
#         tElapsed = time.time()
#         while tElapsed < target_time:
#             time.sleep(0.0001)  # Small sleep to avoid busy waiting
#             tElapsed = time.time()  # Update elapsed time
#
#         # Send the event message
#         if eventType == 'LH':
#             send_msg(type='LH', command=e[1])
#         elif eventType == 'strum':
#             send_msg(type='strum', command=e[1])
#         elif eventType == 'pick':
#             send_msg(type='pick', command=e[1])
#
#         # Print elapsed time for debugging
#         tElapsed = time.time() - start
#         print("Elapsed time:", tElapsed)
#
#     print("done, exiting song")
#     time.sleep(2)
#     lastLHidx = len(LH) - 1
#     lastLHCommand = LH[lastLHidx]
#     print("This is the last command: ", lastLHCommand)
#     send_msg(type='LH', command= [lastLHCommand[1][0], [1,1,1,1,1,1]])
#     return 0

def send_msg(pos):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_ip = "10.2.1.177"
    udp_port = 8888

    # print("pos: ", pos)
    pCommand = struct.pack('f' * len(pos), *pos)
    sock.sendto(pCommand, (udp_ip, udp_port))

    return 0

def main(song_trajs):
    # left = [x for pos in song_trajs for x in pos]
    # print("left: ", len(left))
    # print(left)

    print("4")
    time.sleep(1)
    print("3")
    time.sleep(1)
    print("2")
    time.sleep(1)
    print("1")
    time.sleep(1)

    # size = 360
    # toSend = [left[i:i+size] for i in range(0, len(left), size)]
    # for pos in toSend:
    #     send_msg(pos)

    # print("SONG TRAJS: ", song_trajs)
    interval = 0.005 
    total_start_time = time.time()

    for i, point in enumerate(song_trajs):
        start_time = time.time()
        print(f"Sending {i}")
        send_msg(point)

        elapsed_time = time.time() - start_time
        sleep_time = max(0, interval - elapsed_time)
        time.sleep(sleep_time)

    total_elapsed_time = time.time() - total_start_time
    print(f"Total elapsed time: {total_elapsed_time:.4f} seconds")
    return 0