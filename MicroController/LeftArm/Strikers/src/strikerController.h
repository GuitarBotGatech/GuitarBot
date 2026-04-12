//
// Created by Raghavasimhan Sankaranarayanan on 03/30/22.
// Modified for plucking prototype, Marcus Parker
#ifndef STRIKERCONTROLLER_H
#define STRIKERCONTROLLER_H
#include <math.h>

#include "def.h"
#include "util.h"
#include "striker.h"
#include <HardwareTimer.h>
#include "Trajectory.h"
#include <ArduinoQueue.h>
#include <ArduinoEigen.h>
//#include "networkHandler.h"
#include <iostream>
#include "tune.h"

class StrikerController {
public:
    static StrikerController* createInstance() {
        pInstance = new StrikerController;
        return pInstance;
    }

    static void destroyInstance() {
        delete pInstance;
        pInstance = nullptr;
    }

//    using PresserCallbackType = void (StrikerController::*)(uint8_t, int);
//    void (StrikerController::* pPresserCallBack)(uint8_t, int) = &StrikerController::executePress;

    Error_t init(MotorSpec spec, bool bInitCAN = true) {
        LOG_LOG("Initializing Controller");
//        int err = 0;
        if (bInitCAN) {
            if (!CanBus.begin(CAN_BAUD_1000K, CAN_STD_FORMAT)) {
                LOG_ERROR("CAN open failed");
                return kFileOpenError;
            }
            CanBus.attachRxInterrupt(canRxHandle);
        }
        //TODO: Confirm initialization for Ethernet messaging
//        Error_t err = m_socket.init(&strikerController::packetCallback);
//        if (err != kNoError)
//            return err;

        RPDOTimer.setPeriod(PDO_RATE * 1000);
        RPDOTimer.attachInterrupt(RPDOTimerIRQHandler);
        LOG_LOG("Controller Initialized");

        return initStrikers(spec);
    }


    Error_t initStrikers(MotorSpec spec) {
        // HOME SLIDERS
        m_motorSpec = spec;
        Error_t err = kNoError;
        for (int i = 1; i < NUM_STRIKERS + 1; ++i) {
            //m_striker[i].setPInstance(pInstance);
            LOG_LOG("slider %i", i);
            err = m_striker[i].init(i, spec);
            delay(100);
            if (err != kNoError) {
                LOG_ERROR("Cannot initialize slider with id %i. Error: %i", i, err);
            }
            //m_strinitiker[i].setPresserCallback(pPresserCallBack);
        }

        // HOME PRESSERS
        MotorSpec spec2 = EC20;
        err = kNoError;
        for (int i = NUM_STRIKERS + 1; i < NUM_STRIKERS + NUM_PRESSERS + 1; ++i) {
            LOG_LOG("presser %i", i);
            err = m_striker[i].init(i, spec2);
            delay(100);
            if (err != kNoError) {
                LOG_ERROR("Cannot initialize presser with id %i. Error: %i", i, err);
            }
            else {
                LOG_LOG("Successfully initialized presser with id %i", i);
            }

        }
        // DEPRECATED
        //HOME STRUMMER SLIDER
        MotorSpec spec3 = EC45_StrummerSlider;
        err = kNoError;
        for (int i = NUM_STRIKERS + NUM_PRESSERS + 1; i < NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + 1; ++i) {
            LOG_LOG("StrummerSlider %i", i);
            err = m_striker[i].init(i, spec3);
            delay(100);
            if (err != kNoError) {
                LOG_ERROR("Cannot initialize plucker with id %i. Error: %i", i, err);
            }
            else {
                LOG_LOG("Successfully initialized plucker with id %i", i);
            }

        }
        // DEPRECATED
        // HOME STRUMMER PICKER
        MotorSpec spec4 = EC45_StrummerPicker;
        err = kNoError;

        for (int i = NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + 1; i < NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + 1; ++i) {
            LOG_LOG("StrummerPicker %i", i);
            err = m_striker[i].init(i, spec4);
            delay(100);
            if (err != kNoError) {
                LOG_ERROR("Cannot initialize strummer-picker with id %i. Error: %i", i, err);
            }
            else {
                LOG_LOG("Successfully initialized strummer-picker with id %i", i);
            }

        }

        //HOME PICKERS
        MotorSpec spec5 = EC45_Plucker_1024;
        MotorSpec spec6 = EC45_Plucker_2048;
        err = kNoError;
        for (int i = NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + 1; i < NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + NUM_PLUCKERS + 1; ++i) {
            LOG_LOG("Plucker %i", i);
            if(i == 13 || i == 16 || i == 18){ //
                err = m_striker[i].init(i, spec5);
            }
            else{
                err = m_striker[i].init(i, spec6);
            }
            delay(100);
            if (err != kNoError) {
                LOG_ERROR("Cannot initialize plucker with id %i. Error: %i", i, err);
            }
            else {
                LOG_LOG("Successfully initialized plucker with id %i", i);
            }

        }

//        delay(20000);
        for (int i = 1; i <= NUM_STRIKERS; ++i) {
            m_striker[i].startHome(i);
        }
        checkHomingInRange(1, NUM_STRIKERS);
        delay(500);

        LOG_LOG("Homing for sliders complete, starting pressers. ");
        for (int i = NUM_STRIKERS + 1; i <= NUM_PRESSERS + NUM_STRIKERS; ++i) {
            m_striker[i].startHome(i);
        }
        checkHomingInRange(NUM_STRIKERS + 1, NUM_PRESSERS  + NUM_STRIKERS);
        LOG_LOG("Homing for pressers complete, starting pluckers. ");
        for (int i = NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + 1; i <= NUM_PRESSERS + NUM_STRIKERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + NUM_PLUCKERS; ++i) {
            m_striker[i].startHome(i);
        }
        checkHomingInRange(NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + 1, NUM_PRESSERS + NUM_STRIKERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + NUM_PLUCKERS);

        Serial.println("finished initializing and homing all controllers.");
        //delay(45000); // Testing delay
        //Init all variables needed
        Util::fill(pickerStates, NUM_PLUCKERS, 0); // Initializes picker states to be 0 (pickers start at the up state)
        Util::fill(prev_frets, 6, 100); //Dummy inital values
        Util::fill(prev_playcommands, 6, 100); //Dummy inital values
        return kNoError;
    }

    Error_t resetStrikers() {
        enablePDO(false);
        for (int i = 1; i < NUM_STRIKERS + NUM_PRESSERS + 1; ++i) {
            m_striker[i].reset();
        }
    }

    void reset(bool bTerminateCAN = true) {
        m_bPlaying = false;
        RPDOTimer.stop();
        // faultClearTimer.stop();
        auto err = resetStrikers();
        if (err != kNoError) {
            LOG_ERROR("Cannot reset strikers");
        }
        if (bTerminateCAN)
            CanBus.end();
        //m_socket.close();
    }

    Striker::Command getStrikerMode(char mode) {
        switch (mode) {
        case 's':
            return Striker::Command::Normal;
        case 't':
            return Striker::Command::Tremolo;
        case 'r':
            return Striker::Command::Restart;
        case 'q':
            return Striker::Command::Quit;
        case 'c':
            return Striker::Command::Choreo;
        default:
            LOG_ERROR("unknown command : %i", mode);
            return Striker::Command::Normal;
        }
    }

    uint8_t prepare(uint8_t idCode, char mode, int midiVelocity, uint8_t channelPressure) {
        return prepare(idCode, getStrikerMode(mode), midiVelocity, channelPressure);
    }

    Error_t restart() {
        auto spec = m_motorSpec;
        reset(false);
        Error_t err = init(spec, false);
        if (err != kNoError) {
            LOG_ERROR("Cannot init controller");
            return err;
        }

        start();

        return kNoError;
    }

    uint8_t prepare(uint8_t idCode, Striker::Command mode, int midiVelocity, uint8_t channelPressure) {
        uint8_t uiStrike = 0;

        switch (mode) {
        case Striker::Command::Restart:
            restart();
            break;

        case Striker::Command::Quit:
            for (int i = 1; i < NUM_STRIKERS + NUM_PRESSERS + 1; ++i) {
                m_striker[i].shutdown();
            }
            break;

        default:
            for (int i = 1; i < NUM_STRIKERS + NUM_PRESSERS + 1; ++i) {
                if (idCode == i ) {
                    bool bStrike = m_striker[i].prepare(mode, midiVelocity, channelPressure);
                    uiStrike = idCode;
//                    uiStrike += bStrike << (i - 1);
                }
            }
        }

        return uiStrike;
    }
    void executePress(uint8_t idCode, int command) {
        for (int i = 1; i < NUM_STRIKERS + NUM_PRESSERS + 1; ++i) {
            if (idCode == i) {
                m_striker[i].press(command);
            }
        }
    }
    void executeMove(uint8_t  idCode, int pos){
        for (int i = 1; i < NUM_STRIKERS + NUM_PRESSERS + 1; ++i) {
            if (idCode == i) {
                m_striker[i].testMove(pos);
            }
        }
    }

    /*
        Function: processTrajPoints
        Input: List of trajectory points for all motors
        Output: Pushes point to the queue
    */
    void processTrajPoints(float *trajPoint) {
        int packetSize = 15;
        int curr_pos;
        Serial.print("RECEIVED: ");
        for (int i = 0; i < packetSize; i++) {
            Serial.print(trajPoint[i]);
            Serial.print(" ");
        }
        Serial.println();

        for (int x = 0; x < NUM_MOTORS; x++) {
            if (x < 17) {
                if (x > 5 && x < 12) {
                    int curr_pos;
                    curr_pos = pInstance->m_striker[x + 1].getPosition_ticks();
                    //Serial.print("Current pos at ");
//                    Serial.print(x + 1);
//                    Serial.print(" ");
//                    Serial.print(curr_pos);
                    if (curr_pos <= 15 && trajPoint[x] <= 0) {
                        if (m_striker[x + 1].getPressState()) {
                            m_striker[x + 1].setModePOSITION();
                            //Serial.print(", Setting Position since ");
                        }
                        //Serial.println(", PRESS STATE FALSE");
                        all_Trajs[x][0] = 0;
                    } else {
                        if (!m_striker[x + 1].getPressState()) {
                            m_striker[x + 1].setModeTORQUE();
                            //Serial.print(", Setting Torque since ");
                        }
                        //Serial.print(", is already in Torque mode; ");
                    }
                    all_Trajs[x][0] = trajPoint[x];
                    //Serial.println(", PRESS STATE TRUE");
                } else {
                    all_Trajs[x][0] = trajPoint[x];
                }
            }
        }

        //Serial.println("PROCESSED TRAJ: ");

        //Serial.println();
        //Serial.println("PUSHING TO QUEUE: ");
        Trajectory<int32_t>::point_t temp_point;
        for (int x = 0; x < NUM_MOTORS; x++) {
            temp_point[x] = all_Trajs[x][0];
            //Serial.println(temp_point[x]);
        }
        //Serial.println("-------");
        m_traj.push(temp_point);
    }

    void processTrajChunk(char* buffer, int size) {
        // Each point consists of NUM_MOTORS floats.
        const int floats_per_point = NUM_MOTORS;
        const int bytes_per_point = floats_per_point * sizeof(float);

        // Check for corrupted data
        if (size % bytes_per_point != 0) {
            LOG_ERROR("Packet size %d is not divisible by point size %d. Corrupted data.", size, bytes_per_point);
            return;
        }

        int num_points_in_chunk = size / bytes_per_point;
        Trajectory<int32_t>::point_t temp_point;

        // Iterate through the buffer, one full point at a time
        for (int i = 0; i < num_points_in_chunk; ++i) {
            float* point_data_start = (float*)(buffer + i * bytes_per_point);

            for (int motor_idx = 0; motor_idx < floats_per_point; ++motor_idx) {
                // Cast the incoming float to the int32_t ticks the controller expects.
                temp_point[motor_idx] = static_cast<int32_t>(point_data_start[motor_idx]);
            }

            // Push the fully-formed point into the real-time playback queue
            m_traj.push(temp_point);
        }

        LOG_LOG("Pushed %d new points to the trajectory queue. Queue size is now: %d", num_points_in_chunk, m_traj.count());
    }

    void start() {
        //float start_state_PICK = 8;
        float pos2pulse = 0;

        float temp_traj_1[50];
        float temp_traj_2[50];
        float temp_traj_3[100];
        float temp_traj_4[5];
        float temp_traj_5[95];

        Trajectory<int32_t>::point_t temp_point;

        for(int i = 1;i < NUM_MOTORS + 1 ;i++) {
            temp_point[i - 1] = 0;
            kInitials[i - 1] = 0;

            float q0 = 0;
            float qf = pos2pulse;

            if(i >= 13){ //Picker
                float this_state_PICK = start_state_PICK[i - 13];
                pos2pulse = (this_state_PICK * EC45_ENC_RES_PLUCKER1) / mm_to_enc_conversion_factor; //9.4
                if(i == 14){
                    pos2pulse = (this_state_PICK * EC45_ENC_RES_PLUCKER2) / mm_to_enc_conversion_factor;
                    }
                if(i == 15){
                    pos2pulse = (this_state_PICK * EC45_ENC_RES_PLUCKER2) / mm_to_enc_conversion_factor;
                }
                if(i == 16){
                    pos2pulse = (this_state_PICK * EC45_ENC_RES_PLUCKER1) / mm_to_enc_conversion_factor;
                }
                if(i == 17){
                    pos2pulse = (this_state_PICK * EC45_ENC_RES_PLUCKER2) / mm_to_enc_conversion_factor;
                }

                qf = pos2pulse;
                temp_point[i - 1] = pos2pulse;
                //Interpolate Line
                const int line_length = 50;
                Util::interpWithBlend(q0, qf, line_length, .25, temp_traj_1);
                Util::fill(temp_traj_2, line_length, qf);
                // Put line into list of trajs
                int index = 0;
                // TODO: make this one loop
                for (int x = 0; x < 50; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_1[x];
                }
                for (int x = 0; x < 50; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_2[x];
                }
            }
            else
            {
                Util::interpWithBlend(q0, -1, 100, .05, temp_traj_3);
                int index = 0;
                for (int x = 0; x < 100; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_3[x];
                }
            }

            m_currentPoint[i - 1] = kInitials[i - 1];
        }

        for (int i = 0; i < 100; i++) {
            for(int x = 0; x < NUM_MOTORS; x++){
                temp_point[x] = all_Trajs[x][i];
            }
            m_traj.push(temp_point);
        }



            //PLUCKER PROTOTYPE:
//        float offset = 7; //MINIMUM needed to go from home to top of string!
//        float pos2pulse = (offset * 1024) / mm_to_enc_conversion_factor;
//        for(int i = 1;i < NUM_MOTORS + 1 ;i++){
//            temp_point[i - 1] = pos2pulse;
//            kInitials[i - 1] = pos2pulse;
//            m_currentPoint[i - 1] = kInitials[i - 1];
//        }

        //m_traj.push(temp_point);

        Error_t err = enablePDO();
        if (err != kNoError) {
            LOG_ERROR("cannot enable PDO");
            return;
        }
        err = enableStrikers();
        if (err != kNoError) {
            LOG_ERROR("cannot enable Strikers");
            return;
        }
        CanBus.attachRxInterrupt(canRxHandle);

        m_bPlaying = true;
        RPDOTimer.start();
        //faultClearTimer.start();
        delay(1000);

    }



    void stop() {
        Error_t err;
        err = enablePDO(false);
        if (err != kNoError) {
            LOG_ERROR("cannot disable PDO");
            return;
        }

        err = enableStrikers(false);
        if (err != kNoError) {
            LOG_ERROR("cannot disable Strikers");
            return;
        }

        m_bPlaying = false;
        RPDOTimer.stop();
        // faultClearTimer.stop();
    }

    Error_t enablePDO(bool bEnable = true) {
        Error_t err;
        for (int i = 1; i < NUM_MOTORS + 1; ++i) {
            if(i > 6 && i < 13){
                err = m_striker[i].enablePDOEC20(bEnable);
                LOG_LOG("Enabling PDO for torque motor %i", i);
            }
            else{
                err = m_striker[i].enablePDO(bEnable);
                LOG_LOG("Enabling PDO for motor %i", i);
            }

            delay(100);
            if (err != kNoError) {
                LOG_ERROR("EnablePDO failed. Error Code %i", err);
                return err;
            }
        }
        return kNoError;
    }

    Error_t enableStrikers(bool bEnable = true) {
        int err;
        for (int i = 1; i < NUM_MOTORS + 1; ++i) {
            LOG_LOG("Enabling controller %i", i);
            err = m_striker[i].enable(bEnable);
            delay(300);
            if (err != 0) {
                LOG_ERROR("Enable failed. Error Code %h", err);
                return kSetValueError;
            }
        }

        return kNoError;
    }

//    void poll() {
//        m_socket.poll();
//    }

private:
    //NetworkHandler m_socket;
    Striker m_striker[NUM_MOTORS + 1]; // 0 is dummy
    int pickerStates[NUM_PLUCKERS]; // Array to hold state of each picker (0=up state, 1=down state)
    static StrikerController* pInstance;
    volatile bool m_bPlaying = false;
    MotorSpec m_motorSpec = MotorSpec::EC45_Slider;
    Trajectory<int32_t>::point_t m_currentPoint {};
    Trajectory<int32_t> m_traj;
    bool m_bSendDataRequest = true;
    bool m_bDataRequested = false;


    float all_Trajs[17][200]; //CHANGE FOR MORE TRAJS
    float curr_point[17];

    int prev_frets[6];
    int prev_playcommands[6];




    //Serial.println(all_Trajs);

    float m_afTraj_string_1[60];
    float m_afTraj_string_2[60];
    float m_afTraj_string_3[60];
    float m_afTraj_string_4[60];
    float m_afTraj_string_5[60];
    float m_afTraj_string_6[60];
// Make new float array w/ pressers. Fill with current 20 vals that are current and 1 val that is TRACE_ME
    float m_afTraj_fret_1[60];
    float m_afTraj_fret_2[60];
    float m_afTraj_fret_3[60];
    float m_afTraj_fret_4[60];
    float m_afTraj_fret_5[60];
    float m_afTraj_fret_6[60];


    float m_afTraj_pluck_1[60];

    int strings[NUM_MOTORS + 1];
    uint32_t kInitials[NUM_MOTORS];

//    Epos4 m_epos[NUM_MOTORS];
    bool m_bInitialized = false;


    HardwareTimer RPDOTimer;//, faultClearTimer;

    StrikerController(): RPDOTimer(TIMER_CH1) {}
    // , faultClearTimer(TIMER_CH3) {}

    ~StrikerController() {
        reset();
        destroyInstance();
    }

    //TODO: confirm implementation for ethernet messaging
//    static void packetCallback(char* packet, size_t packetSize) {
//        float point = 0;
//        if (packetSize == 1) {
//            // Commands
//        } else if (packetSize == sizeof(point)) {
//            // int32_t point = 0;
//            // for (int i = 0; i < NUM_BYTES_PER_VALUE; ++i)
//            //     point = point | ((packet[i] & 0xFF) << (8 * i));
//            memcpy(&point, packet, sizeof(point));
//            //TODO: how does setPoint(VVVV) vs currentPoint work for GuitarBot?
//            pInstance->m_iSetPoint = point;
//        } else {
//            LOG_ERROR("Packet Corrupted. Received %i bytes", packetSize);
//        }
//    }

    static void canRxHandle(can_message_t* arg) {
        uint32_t rawId = arg->id & 0x7FF;
//        Serial.printf("CAN ID: 0x%03X | Data: ", rawId);
//        for(int i=0; i<arg->length; i++) Serial.printf("%02X ", arg->data[i]);
//        Serial.println();


        // Handle TPDO3 messages (0x480 + nodeID)
//        Serial.println(rawId - 0x380);
        if((rawId & 0x780) == 0x380) { // Check TPDO range
//            Serial.println("TRIGGERED PDO");
            uint8_t nodeID = rawId - 0x380;
            if(nodeID > 6 && nodeID <= 12) {
                pInstance->m_striker[nodeID].PDO_processMsg(*arg);
            }
            return;
        }

        // Handle SDO responses
        if((rawId & 0x780) == 0x580) { // SDO server response range
//            Serial.println("TRIGGERED SDO");
            uint8_t nodeID = rawId - 0x580;
            if(nodeID > 0 && nodeID <= NUM_MOTORS) {
                pInstance->m_striker[nodeID].setRxMsg(*arg);
            }
            return;
        }

        // Handle EMCY messages
        if((rawId & 0x780) == 0x080) { // EMCY message range
            uint8_t nodeID = rawId - 0x080;
            if(nodeID > 0 && nodeID <= NUM_MOTORS) {
                pInstance->m_striker[nodeID].handleEMCYMsg(*arg);
            }
        }
    }

    static void RPDOTimerIRQHandler() {
        static bool errorAtPop = false;
        static ulong idx = 0;




        if (pInstance == nullptr)
            return;

        Trajectory<int32_t>::point_t point { pInstance->m_currentPoint };

        // If new point is available, grab it. Else keep using last point

        // If there was an error, this new point might not be continuous.
        if (errorAtPop) {
            // TODO: Form a trajectory from current point to this new point and then move using the new point.
            errorAtPop = false;
        } else {
            if (pInstance->m_traj.count() > 0) {
//                Serial.println("TRAJ COUNT IS ");
//                Serial.println(pInstance->m_traj.count());

                //slider array.count() == 0 && press

                Trajectory<int32_t>::point_t pt { pInstance->m_currentPoint };
                auto err = pInstance->m_traj.peek(pt);
                if (err)
                    LOG_ERROR("Error peeking trajectory. Code %i", (int) err);

                // If the point is not close to the previous point, generate transition trajectory
                if (!pt.isClose(pInstance->m_currentPoint, DISCONTINUITY_THRESHOLD)) {
                    LOG_WARN("Trajectory discontinuous. Generating Transitions...");
                    Serial.print("Current Point: ");
                    for (int x = 0; x<NUM_MOTORS; x++)
                    {
                        Serial.print(pInstance->m_currentPoint[x]);
                        Serial.print(" ");
                    }
                    Serial.println();
                    Serial.print("Next Point: ");
                    for (int x = 0; x<NUM_MOTORS; x++)
                    {
                        Serial.print(pt[x]);
                        Serial.print(" ");
                    }
                    Serial.println();
                    delay(30000); 

                    // pInstance->m_traj.generateTransitions(pInstance->m_currentPoint, pt, TRANSITION_LENGTH);
                }
                // Pop from traj queue. If transition was added, this point is from the generated transition
                err = pInstance->m_traj.pop(point);
                if (err != kNoError) {
                    errorAtPop = true;
                    LOG_ERROR("Error getting value from trajectory. Code %i", (int) err);
                    // TODO: If we cannot obtain a datapoint, there will be a discontinuity.
                    // In that case, form a trajectory to go to the last point and stay.
                }
            }
        }
//        Serial.println("------------------");
//        Serial.print("Index: ");
//        Serial.println(idx);
//        Serial.print("Traj Point: ");
//        int curr_pos;
//        for (int i = 0; i < NUM_MOTORS; ++i) {
//            Serial.print(point[i]);
//            Serial.print(" ");
//        }
//        Serial.println(" ");


        bool run_bot = true; //false turns off motor, true turns on


        idx += 1;
        if (run_bot){
                // drive actuators here...
                for (int i = 1; i < NUM_MOTORS + 1; ++i){
                    if(i > 6 && i < 13){
                        if(!pInstance->m_striker[i].getPressState()){
                            pInstance->m_striker[i].rotate(0);
                        }
                        else{
                            pInstance->m_striker[i].applyTorque(point[i - 1]);
                        }
                    }
                    else{
                        pInstance->m_striker[i].rotate(point[i - 1]);
                    }
                }
        }

        // Set sendRequest flag if total trajectory time is less than the buffer time.
        //pInstance->m_bSendDataRequest = (pInstance->m_traj.count() * PDO_RATE / 1000.f) < BUFFER_TIME;
        pInstance->m_currentPoint = point;
    }

    int checkHomingInRange(uint8_t start, uint8_t end) {
        // dummy-proof so that end >= start
        if (end < start) std::swap(start, end);

        // Bound check
        if (start < 1 || end > NUM_MOTORS || start > end) {
            Serial.println("Homing Error: Invalid motor range");
            return 2;
        }

        // Build queue of motors that still need homing
        ArduinoQueue<uint8_t> q;
        for (uint8_t i = start; i <= end; ++i) q.enqueue(i);

        const unsigned long pollDelayMs = 50;

        while (!q.isEmpty()) {
            // Grab first motor in queue
            uint8_t node = q.getHead();
            // Pop it off. We will push it back into queue if it is not done homing.
            q.dequeue();

            // Check homing status; if still homing, requeue; if finished, it is already out of the queue
            bool isHoming = m_striker[node].homingStatus();
            if (isHoming) {
                q.enqueue(node);
            } 
            else {
                // finished homing for this node; do not requeue
                // Serial.print("Node "); Serial.print(node); Serial.println(" homed.");
            }

            // Polling delay
            delay(pollDelayMs);
        }

        // all finished
        return 0;
    }
    // static void clearFaultTimerIRQHandler() {
    //     for (int i = 1; i < NUM_STRIKERS + 1; ++i) {
    //         pInstance->m_striker[i].checkAndRecover();
    //     }
    // }
};

StrikerController* StrikerController::pInstance = nullptr;
#endif // STRIKERCONTROLLER_H
