import numpy as np
import time
from queue import Queue
from GuitarBotUDP import GuitarBotUDP
# from xarm.wrapper import XArmAPI      TODO XARM
import threading
import logging

#### Definitions
# UDP_IP = "192.168.1.50"
UDP_IP = "10.2.1.177"
XARM_IP = '192.168.1.215'
UDP_PORT = 8888
INIT_POSE = [684.3, 246.8, 367.7, -90, 0, 0]
SYNC_RATE = 250
move_time = 0.1
ipickeracc = 200
ipickvel = 150
pgain = 8000
OFFSET = 20.5
STRUM_PT = [372.7, 357.7, 347.7, 337.7, 327.7, 317.7, 292.7]
PICK_PT = [371.6 - OFFSET, 362.4 - OFFSET, 351.4 - OFFSET, 340.8 - OFFSET, 331.3 - OFFSET, 321.4 - OFFSET]
INIT_POSE = [684.3, 246.8, 367.7, -90, 0, 0]
right_information = []

fretnum = []
fretplay = []
rhythm = []

firstc = []
left_arm = []

left_queue = Queue()
robot_queue = Queue()
comms_queue = Queue()

HEADER = '/guitar'
chords_dir = "Chords - Chords.csv"


class GuitarRobotController():
    def __init__(self):
        # self.cobot_controller = CobotController(250, INIT_POSE)
        # self.xarm = XArmAPI(XARM_IP)                                      TODO XARM
        self.guitarbot_udp = GuitarBotUDP(UDP_IP, UDP_PORT)
        self.left_thread = threading.Thread(target=self.lefthand_move)
        # self.right_thread = threading.Thread(target=self.robot_move)      TODO XARM
        # self.pick_thread = threading.Thread(target=self.pick_move)

    def robot_init(self):
        self.xarm.set_simulation_robot(on_off=False)
        self.xarm.motion_enable(enable=True)
        self.xarm.clean_warn()
        self.xarm.set_mode(0)
        self.xarm.set_state(0)
        self.xarm.set_position(*INIT_POSE, wait=True)

    def xarm_start(self):
        self.xarm.set_mode(1)
        self.xarm.set_state(0)

    def thread_start(self):
        self.left_thread.start()
        # self.right_thread.start()         TODO XARM
        # self.pick_thread.start()

    def thread_end(self):
        self.left_thread.join()
        # self.right_thread.join()          TODO XARM
        # self.pick_thread.join()

    def _fifth_poly(self, q_i, q_f, time):
        # for picking, try 100 or 150 ms
        traj_t = np.linspace(0, time, int(time * SYNC_RATE))
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

    def get_traj_p2p(self, note_i, note_f, move_time):
        pos_z = self._fifth_poly(note_i, note_f, move_time)

        pos_y = np.ones(len(pos_z)) * INIT_POSE[1]
        return pos_y, pos_z

    def get_traj_ellipse(self, note_i, note_f, length):
        elps_b = 10

        pos_z = self._fifth_poly(note_i, note_f, length)
        strum_range = note_i - note_f
        pos_y = -(abs((elps_b / (strum_range / 2)) * np.sqrt(
            abs((strum_range / 2) ** 2 - (pos_z - note_f - strum_range / 2) ** 2)))) + INIT_POSE[1]

        return pos_y, pos_z

    def lefthand_move(self):
        # First Two Measures
        # Figure out timing for each measure
        # Change chord shape at measure shift to inputted chord
        # Read from rhythms db to check muted

        # while not is_play:
        #     time.sleep(0.001)
        leftchord = cc.copy()
        timings = Events.copy()
        print("t: ", timings)
        print("firstc: ", firstc)
        #Test
        self.guitarbot_udp.send_msg_left(iplaycommand=firstc[1], ifretnumber=firstc[0])
        # self.guitarbot_udp.send_msg_arduino(iplaycommand=firstc[1], ifretnumber=firstc[0])

        bpm = 60
        bps = bpm / 60

        print("4")
        time.sleep(1 / bps)
        print("3")
        time.sleep(1 / bps)
        print("2")
        time.sleep(1 / bps)
        print("1")
        time.sleep((1 / bps) - .15)


        chordindex = 0

        ts = 0
        tbaseline = time.time()
        maxchords = len(left_arm) - 1
        strumindex = 0
        strumdebugtick = time.time()
        print("Timings: ", timings)
        for Event in timings:
            print("E: ", Event)
            tNextEvent = Event[0]
            type = Event[1]
            if chordindex > maxchords:
                chordindex = maxchords
            chordtoplay = left_arm[chordindex]
            # beat_duration = measure_time / 4

            while ts < tNextEvent:
                #TODO: Refactor to not constantly check, and add offset for changing chords
                ts = time.time() - tbaseline
                time.sleep(0.001)
            # print("we hit time", t_start_local)
            # sleep_time = leftchord[index] + t_start_local
            # print(chord)
            # if len(chord) > 0:
            #     print("Send)")
            if type > 0:  # TYPE 1 IS HERE AND IS STRUMMING
                comms_queue.put(1)
                strumtock = time.time()
                strumticktock = strumdebugtick - strumtock
                print("STRUM DELTA", strumdebugtick - strumtock)
                strumdebugtick = time.time()

                # SAKSHAM: TODO CHANGE
                # if strumchange[strumindex] == 'C':
                #     comms_queue.put(1)
                # strumindex += 1
                # print("array2", tNextEvent)
            else:  # TYPE 0 IS HERE AND IS PICKING
                # print("array1", tNextEvent)
                # Test
                self.guitarbot_udp.send_msg_left(iplaycommand=chordtoplay[1], ifretnumber=chordtoplay[0])
                # self.guitarbot_udp.send_msg_arduino(iplaycommand=chordtoplay[1], ifretnumber=chordtoplay[0])
                chordindex += 1
                # time.sleep(measure_time / 4)

        # Pass to tune
        time.sleep(2)
        self.guitarbot_udp.send_msg_left(iplaycommand=[1, 1, 1, 1, 1, 1], ifretnumber=firstc[0])
        # test
        # self.guitarbot_udp.send_msg_arduino(iplaycommand=[1, 1, 1, 1, 1, 1], ifretnumber=firstc[0])
        print("done")
        return 0

    def traj_generationUser(self, ri):

        print("hi")
        # Strum len will change according to different ranges of BPM
        strumlen = .15
        # strumlen = measure_time/(timeattopoftimesig)
        posZ = []
        trajectoryarrays = []
        slider = []
        angle = []
        prev = 0
        strumdirections = [[STRUM_PT[0], STRUM_PT[6]], [STRUM_PT[6], STRUM_PT[0]]]
        if ri[0][0][0] == 'D':
            time.sleep(3)
        # else:
        # pos_y, pos_z = self.get_traj_p2p(STRUM_PT[0],
        #                                  STRUM_PT[6], 3)
        # posZ.append(list(pos_z))
        # posY = np.append(posY, pos_y)
        # slider.append(-15)
        # angle.append(-15)
        # prev = 6
        rests = True
        print(strumOnsets[0])
        for i in range(len(strumOnsets) - 1):
            action = strumOnsets[i]
            t = action[0]
            tnext = strumOnsets[i + 1][0]
            deltat = tnext - t - strumlen
            if deltat > 0.75:
                deltat = 0.75

            if action[1] == 'U':
                direction = 1
                a = -15
                angle.append(a)
            else:
                direction = 0  ### DOWN STRUM
                a = 15
                angle.append(a)

            ### Now make trajectories accordingly
            if action[2] == 'N':
                change = 1
                pos_y, pos_z = self.get_traj_p2p(strumdirections[direction][0],
                                                 strumdirections[direction][1], strumlen)
                trajectoryarrays.append(list(pos_z))
                slider.append(-7)
                angle.append(a)

            else:
                change = 0
                if deltat < 0:
                    print('BAD WILL BREAK')
                    deltat = 0
                pos_y, pos_z = self.get_traj_p2p(strumdirections[direction][0],
                                                 strumdirections[direction][1], strumlen)
                pos_yc, pos_zc = self.get_traj_p2p(strumdirections[direction][1],
                                                   strumdirections[direction][0], deltat)
                trajectoryarrays.append(list(pos_z))
                slider.append(-7)
                angle.append(a)

                trajectoryarrays.append(list(pos_zc))
                slider.append(-15)
                angle.append(a)

        return trajectoryarrays, slider, angle

    def robot_move(self):

        # while not is_play:
        #     time.sleep(0.001)
        trajectories, slider, angle = self.traj_generationUser(right_information)
        # robot_queue.get()
        strum_end = time.time()
        strum_start = time.time()
        print("TRAJECTORIES ARE ", len(trajectories))
        for i in range(len(trajectories)):
            # if i%2 <1:
            comms_queue.get()
            posZ = trajectories[i]

            self.guitarbot_udp.send_msg_picker(ipickercommand=4, bstartpicker=1, pgain=1200, dgain=100,
                                               ipickerpos=4,
                                               ipickervel=ipickvel, ipickeracc=ipickeracc, isliderpos=slider[i])

            self.guitarbot_udp.send_msg_picker(ipickercommand=1, bstartpicker=1, pgain=1200, dgain=100,
                                               ipickerpos=1,
                                               ipickervel=ipickvel, ipickeracc=ipickeracc, isliderpos=angle[i])

            strumt = time.time() - strum_start
            print('positionNum', i)
            print('strum time: ', strumt)
            strum_start = time.time()

            for y in range(len(posZ)):
                start = time.time()
                new_pose = [INIT_POSE[0], INIT_POSE[1], posZ[y], INIT_POSE[3], INIT_POSE[4], INIT_POSE[5]]
                self.xarm.set_servo_cartesian(new_pose)
                tts = 0.004 - (time.time() - start)
                if tts > 0:
                    time.sleep(tts)
                # else:
                #     print("DELAYTJIEOFDSFDJGH")
            strum_end = time.time()


def main(ri, li, initStrum, mt, chord_change, strumO):
    global right_information
    global measure_time
    global firstc
    global left_arm
    global cc
    global strumOnsets
    global Events
    global strumchange
    strumOnsets = strumO
    Events = []
    strumchange = []
    for strums in strumOnsets:
        Events.append([strums[0], 1])
        if strums[2] == 'C':
            Events.append([strums[0] + 0.15, 1])
        strumchange.append(strums[2])
    print("strumOnsets", strumO)
    left_arm = li
    right_information = ri
    firstc = initStrum
    cc = chord_change
    for c in cc:
        Events.append([c, 0])
    Events.sort()

    measure_time = mt
    grc = GuitarRobotController()
    # osc_reader = OSCserver()
    # osc_reader.listen2max()

    # grc.traj_generation(rhythm)
    # grc.robot_init()          TODO XARM
    time.sleep(1)
    # grc.xarm_start()          TODO XARM
    time.sleep(1)
    grc.thread_start()


if __name__ == '__main__':
    main()
