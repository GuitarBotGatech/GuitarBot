import socket
from messaging.udp_definitions import * # NOTE: ignore any red squiggles, this works fine

class ArmListSender:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_ip = DESTINATION_IP
        self.udp_port = UDP_PORT
        self.left_arm_header = LEFT_ARM_HEADER
        self.right_arm_header = RIGHT_ARM_HEADER
        self.measure_time_header = MEASURE_TIME_HEADER
        self.header_delimiter = HEADER_DELIMITER

        self.socket.connect((self.udp_ip, self.udp_port))
        
    def send_arm_lists_to_reciever(self, left_arm, right_arm, measure_time):
        # send left arm data
        msg = self.left_arm_header + self.header_delimiter + str(left_arm)
        self.socket.send(msg.encode("utf-8"))

        # send right arm data
        msg = self.right_arm_header + self.header_delimiter + str(right_arm)
        self.socket.send(msg.encode("utf-8"))

        # send measure time
        msg = self.measure_time_header + self.header_delimiter + str(measure_time)
        self.socket.send(msg.encode("utf-8"))