import socket
from ast import literal_eval
import RobotController
from UI.messaging.udp_definitions import *
from parsing.ArmListParser import ArmListParser

# Define ip/port/headers
udp_ip = RECEIVER_IP
udp_port = UDP_PORT
left_arm_header = LEFT_ARM_HEADER
right_arm_header = RIGHT_ARM_HEADER
measure_time_header = MEASURE_TIME_HEADER
header_delimiter = HEADER_DELIMITER

# Create socket
socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
socket.bind((udp_ip, udp_port))

left_arm = None
right_arm = None
measure_time = None
pickings = None

# loop to recieve messages and send to robot controller
# TODO run the message recieving/robot controller call on separate threads with a queue of messages
while True:
    recieved_msg = socket.recv(1024) # 1024 byte buffer size
    recieved_msg = recieved_msg.decode("utf-8")

    # parse UDP message
    split = recieved_msg.split(header_delimiter)
    msg_header = split[0]
    msg_body = split[1]

    if msg_header == left_arm_header:
        left_arm = literal_eval(msg_body)
    elif msg_header == right_arm_header:
        right_arm = literal_eval(msg_body)
    elif msg_header == measure_time_header:
        measure_time = float(msg_body)
    else:
        print("Message header not recognized: ", msg_header)

    # print message info
    print("message header: ", msg_header)
    print("message body: ", msg_body)

    print("recieved left arm: ", left_arm)
    print("recieved right arm: ", right_arm)
    print("recieved measure time: ", measure_time)

    # Check that all 3 components have been recieved
    if left_arm is not None and right_arm is not None and measure_time is not None:
        # parse arm lists
        # left_arm_info, first_c, m_timings = ArmListParser.parseleft_M(left_arm, measure_time)
        #lh_info = ArmListParser.parseleft_M(left_arm, measure_time)
        # right_arm_info, initial_strum, strum_onsets = ArmListParser.parseright_M(right_arm, measure_time)
        # rh_info = ArmListParser.parseright_M(right_arm, measure_time)

        #New function to combine matricies
        song_trajectories_dict = ArmListParser.parseAll(left_arm, right_arm,measure_time)

        #print("right_arm_info", right_arm_info)
        # print("left_arm_info", left_arm_info)
        # print("picking_info", pickings)
        # print("first_c: ", first_c)
        # print("m_timings: ", m_timings)
        #print("initial_strum: ", initial_strum)
        #print("strum_onsets: ", strum_onsets)

        song_trajectories_list = []
        for key, value in song_trajectories_dict.items():
            song_trajectories_list.append(value)

        # send song data to robot controller
        # TODO: once picking is a feature of UI, we will use pickings as well
        #RobotController.main(right_arm_info, left_arm_info)
        RobotController.main(song_trajectories_list)

        # reset variables so that they're ready to accept new message
        left_arm, right_arm, measure_time = None, None, None