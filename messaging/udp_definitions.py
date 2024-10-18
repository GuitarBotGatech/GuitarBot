# INSTRUCTIONS:
# IP address of computer used to send messages must be configured to "169.254.244.xxx" (first 9 digits must be the same as GuitarBot computer)
# Subnet mask must also be set to "255.255.255.0"
# Both of these should be set in network settings for the specific ethernet LAN network connecting the sender to the GuitarBot computer

# IP/PORTS
GUITARBOT_UDP_IP = "169.254.244.221"
LOCAL_UDP_IP = "127.0.0.1"
UDP_PORT = 4268 # (GBOT)

# SENDING/RECEIVING IPS
# NOTE: change DESTINATION_IP depending on whether sending locally or from laptop to lab computer
DESTINATION_IP = LOCAL_UDP_IP

# Don't modify this
RECEIVER_IP = "0.0.0.0" # open to all sources

# HEADER DEFINITIONS
LEFT_ARM_HEADER = "l_arm_guitar"
RIGHT_ARM_HEADER = "r_arm_guitar"
MEASURE_TIME_HEADER = "measure_time_guitar"
HEADER_DELIMITER = '%'