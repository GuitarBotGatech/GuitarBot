# IP/PORTS
GUITARBOT_UDP_IP = "192.168.1.205"
LOCAL_UDP_IP = "127.0.0.1"
UDP_PORT = 4268 # (GBOT)

# NOTE: change this depending on whether sending locally or from laptop to lab computer
SENDER_IP = LOCAL_UDP_IP
RECEIVER_IP = "0.0.0.0" # open to all sources. Should remain constant

# HEADER DEFINITIONS
LEFT_ARM_HEADER = "l_arm_guitar"
RIGHT_ARM_HEADER = "r_arm_guitar"
MEASURE_TIME_HEADER = "measure_time_guitar"
HEADER_DELIMITER = '%'