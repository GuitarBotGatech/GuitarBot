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
            if(i == 13 || i == 16){ //
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
        homePressers();
        LOG_LOG("Homing for pressers complete, starting pluckers. ");
        for (int i = NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + 1; i <= NUM_PRESSERS + NUM_STRIKERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + NUM_PLUCKERS; ++i) {
            m_striker[i].startHome(i);
        }
        checkHomingInRange(NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + 1, NUM_PRESSERS + NUM_STRIKERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + NUM_PLUCKERS);

        LOG_LOG("Homing for pluckers complete, measuring pick release. ");
        homePluckers();

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
        int packetSize = 18;
        int curr_pos;
        // Serial.print("RECEIVED: ");
        // for (int i = 0; i < packetSize; i++) {
        //     Serial.print(trajPoint[i]);
        //     Serial.print(" ");
        // }
        // Serial.println();

        for (int x = 0; x < NUM_MOTORS; x++) {
            if (x < 18) {
                // Pressers included: park vs press is decided in the 5 ms loop
                // from the live encoder, including after this queue drains.
                all_Trajs[x][0] = trajPoint[x];
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
                if(i == 18){
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

    // Encoder ticks for nodeId in [1, NUM_MOTORS]. Used by UDP telemetry.
    float getMotorPosition(uint8_t nodeId) {
        if (nodeId < 1 || nodeId > NUM_MOTORS) {
            return 0.f;
        }
        return m_striker[nodeId].getPosition_ticks();
    }

//    void poll() {
//        m_socket.poll();
//    }

private:
    //NetworkHandler m_socket;
    Striker m_striker[NUM_MOTORS + 1]; // 0 is dummy
    int pickerStates[NUM_PLUCKERS]; // Array to hold state of each picker (0=up state, 1=down state)
    static constexpr int PRESSER_HOME_TICKS = 15;
    static constexpr int PRESSER_RELEASE_TORQUE = -650;

    // Presser homing. A cam has stalled once it moves less than PRESSER_STALL_TICKS
    // for PRESSER_STALL_MS. A midpoint spread above PRESSER_MIDPOINT_SPREAD_WARN
    // across the calibration frets means the cam or carriage is not symmetric.
    static constexpr int NUM_CAL_FRETS = sizeof(presser_cal_frets) / sizeof(presser_cal_frets[0]);
    static constexpr int PRESSER_STALL_TICKS = 3;
    static constexpr unsigned long PRESSER_STALL_MS = 500;
    static constexpr unsigned long PRESSER_TORQUE_RAMP_MS = 500;
    static constexpr unsigned long PRESSER_STALL_TIMEOUT_MS = 3000;
    // A full stall-to-stall range is roughly 50-100 ticks (a press moves ~30-50 ticks from rest).
    static constexpr int PRESSER_MIDPOINT_SPREAD_WARN = 8;
    static constexpr int PRESSER_MIN_RANGE_TICKS = 10;
    static constexpr uint32_t PRESSER_CAL_SPEED = 200; // rpm
    static constexpr uint32_t SLIDER_CAL_SPEED = 300; // rpm
    static constexpr int MOVE_ARRIVED_TICKS = 20;
    static constexpr unsigned long MOVE_TIMEOUT_MS = 5000;

    // Plucker release calibration. After the hard-stop home, each pick sweeps slowly
    // through the string; a sharp current drop marks release. Open string, then fret 9.
    // Thresholds are from the full-range SWEEP log: real plucks drop 270-530 mA and
    // fall to under ~65% of the prior sample; mid-stroke noise dips do not.
    static constexpr float PLUCK_CAL_BACKOFF_MM = 0.2f;
    static constexpr float PLUCK_CAL_MARGIN_MM = 0.3f;
    static constexpr uint32_t PLUCK_CAL_SPEED = 2; // rpm
    static constexpr int PLUCK_DROP_STRONG_MA = 200;
    static constexpr int PLUCK_LOADED_STRONG_MA = 400;
    static constexpr int PLUCK_REMAIN_STRONG_PCT = 65;
    static constexpr int PLUCK_DROP_MILD_MA = 150;
    static constexpr int PLUCK_LOADED_MILD_MA = 200;
    static constexpr int PLUCK_REMAIN_MILD_PCT = 40;

    // True after a press was accepted from home. Cleared on a lift, so the next
    // press waits until the cam is home again.
    bool m_pressFromHome[NUM_MOTORS + 1] = {};
    static StrikerController* pInstance;
    volatile bool m_bPlaying = false;
    MotorSpec m_motorSpec = MotorSpec::EC45_Slider;
    Trajectory<int32_t>::point_t m_currentPoint {};
    Trajectory<int32_t> m_traj;
    bool m_bSendDataRequest = true;
    bool m_bDataRequested = false;


    float all_Trajs[18][200]; //CHANGE FOR MORE TRAJS
    float curr_point[18];

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


        // Handle TPDO3 messages (0x380 + nodeID) — keep encoder positions fresh for all motors
//        Serial.println(rawId - 0x380);
        if((rawId & 0x780) == 0x380) { // Check TPDO range
//            Serial.println("TRIGGERED PDO");
            uint8_t nodeID = rawId - 0x380;
            if(nodeID > 0 && nodeID <= NUM_MOTORS) {
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

    // Presser torque is applied here, every PDO tick, from the encoder right now.
    // A lift parks once the cam is back within PRESSER_HOME_TICKS of rest
    // (encoder 0, set by presser homing; press stroke positive).
    // A new press is refused until that happens, so a sticky unpress cannot
    // keep the last torque running after the trajectory has moved on or ended.
    void drivePresser(int nodeId, int command) {
        Striker& motor = m_striker[nodeId];
        int ticks = (int)motor.getPosition_ticks();
        bool atHome = ticks <= PRESSER_HOME_TICKS;
        int park = 0;
        bool wantRelease = command <= 0;

        if (wantRelease) {
            m_pressFromHome[nodeId] = false;
            if (atHome) {
                if (motor.getPressState()) motor.setModePOSITION(park);
                else motor.rotate(park);
                return;
            }
            if (!motor.getPressState()) motor.setModeTORQUE();
            motor.applyTorque(command < 0 ? command : PRESSER_RELEASE_TORQUE);
            return;
        }

        if (atHome || m_pressFromHome[nodeId]) {
            if (!motor.getPressState()) motor.setModeTORQUE();
            m_pressFromHome[nodeId] = true;
            motor.applyTorque(command);
            return;
        }

        if (!motor.getPressState()) motor.setModeTORQUE();
        motor.applyTorque(PRESSER_RELEASE_TORQUE);
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
        // Serial.println("------------------");
        // Serial.print("Index: ");
        // Serial.println(idx);
        // Serial.print("Traj Point: ");
        // int curr_pos;
        // for (int i = 0; i < NUM_MOTORS; ++i) {
        //     Serial.print(point[i]);
        //     Serial.print(" ");
        // }
        // Serial.println(" ");


        bool run_bot = true; //false turns off motor, true turns on


        idx += 1;
        if (run_bot){
                // drive actuators here...
                for (int i = 1; i < NUM_MOTORS + 1; ++i){
                    if(i > 6 && i < 13){
                        pInstance->drivePresser(i, point[i - 1]);
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

    // Moves motors [first, first + count) to their targets and waits until all of them arrive.
    bool moveAndWait(int first, const int32_t* targets, int count, uint32_t speed, bool holdPress = false) {
        for (int k = 0; k < count; ++k) {
            if (m_striker[first + k].startMove(targets[k], speed) != kNoError) {
                LOG_ERROR("Motor %i could not start its move", first + k);
                return false;
            }
        }

        bool arrived[NUM_MOTORS] = {};
        int remaining = count;
        unsigned long startMs = millis();
        while (remaining > 0) {
            if (millis() - startMs > MOVE_TIMEOUT_MS) {
                for (int k = 0; k < count; ++k) {
                    if (arrived[k]) continue;
                    int32_t pos = 0;
                    _WORD stat = 0;
                    bool posOk = m_striker[first + k].readPosition(pos);
                    bool statOk = m_striker[first + k].readStatusWord(stat);
                    LOG_ERROR("Motor %i did not reach %i: position %i%s, status %h%s",
                              first + k, (int) targets[k],
                              (int) pos, posOk ? "" : " (read failed)",
                              (int) stat, statOk ? "" : " (read failed)");
                }
                return false;
            }
            for (int k = 0; k < count; ++k) {
                int32_t pos;
                if (arrived[k] || !m_striker[first + k].readPosition(pos)) continue;
                if (abs(pos - targets[k]) <= MOVE_ARRIVED_TICKS && m_striker[first + k].targetReached()) {
                    arrived[k] = true;
                    --remaining;
                }
            }
            if (holdPress) holdPressers(presser_cal_torque);
            delay(10);
        }
        return true;
    }

    // Turns every presser cam with the same torque until it stops against the fretboard.
    bool stallPressers(int16_t torque, int32_t* stall) {
        const int first = NUM_STRIKERS + 1;
        bool ok = true;
        for (int k = 0; k < NUM_PRESSERS && ok; ++k) {
            if (m_striker[first + k].startTorque() != kNoError) {
                LOG_ERROR("Presser %i could not start torque %i", first + k, torque);
                ok = false;
            }
        }

        int32_t last[NUM_PRESSERS] = {};
        unsigned long stillSince[NUM_PRESSERS];
        bool stalled[NUM_PRESSERS] = {};
        int remaining = NUM_PRESSERS;
        unsigned long startMs = millis();
        for (int k = 0; k < NUM_PRESSERS; ++k) {
            m_striker[first + k].readPosition(last[k]);
            stillSince[k] = startMs;
        }

        const unsigned long rampEndMs = startMs + PRESSER_TORQUE_RAMP_MS;
        while (ok && remaining > 0) {
            unsigned long now = millis();
            unsigned long elapsed = now - startMs;
            if (elapsed > PRESSER_STALL_TIMEOUT_MS) {
                for (int k = 0; k < NUM_PRESSERS; ++k) {
                    if (!stalled[k]) LOG_ERROR("Presser %i never stalled with torque %i", first + k, torque);
                }
                ok = false;
                break;
            }
            bool ramped = elapsed >= PRESSER_TORQUE_RAMP_MS;
            int16_t command = ramped ? torque : (int16_t) ((long) torque * (long) elapsed / (long) PRESSER_TORQUE_RAMP_MS);
            for (int k = 0; k < NUM_PRESSERS; ++k) {
                m_striker[first + k].holdTorque(command);
                int32_t pos;
                if (stalled[k] || !m_striker[first + k].readPosition(pos)) continue;
                // A stall only counts once full torque has been held without movement.
                unsigned long stillFrom = stillSince[k] > rampEndMs ? stillSince[k] : rampEndMs;
                if (abs(pos - last[k]) > PRESSER_STALL_TICKS) {
                    last[k] = pos;
                    stillSince[k] = now;
                } else if (ramped && now - stillFrom >= PRESSER_STALL_MS) {
                    stall[k] = pos;
                    stalled[k] = true;
                    --remaining;
                }
            }
            delay(10);
        }

        for (int k = 0; k < NUM_PRESSERS; ++k) m_striker[first + k].stopTorque();
        return ok;
    }

    // Finds each presser's rest as the midpoint between its two fretboard stalls,
    // averaged over the calibration frets, and makes that position encoder 0.
    void homePressers() {
        const int first = NUM_STRIKERS + 1;
        int32_t sliderTargets[NUM_STRIKERS];
        int32_t presserTargets[NUM_PRESSERS];
        int32_t plus[NUM_PRESSERS];
        int32_t minus[NUM_PRESSERS];
        int32_t mid[NUM_CAL_FRETS][NUM_PRESSERS];
        int32_t range[NUM_CAL_FRETS][NUM_PRESSERS];

        bool ok = true;
        int f = 0;
        for (; f < NUM_CAL_FRETS; ++f) {
            for (int s = 0; s < NUM_STRIKERS; ++s) sliderTargets[s] = presser_cal_slider_ticks[f][s];
            ok = moveAndWait(1, sliderTargets, NUM_STRIKERS, SLIDER_CAL_SPEED)
                && stallPressers(presser_cal_torque, plus)
                && stallPressers(-presser_cal_torque, minus);
            if (!ok) break;

            // Park each cam at this fret's midpoint so it clears the string while the slider moves.
            for (int k = 0; k < NUM_PRESSERS; ++k) {
                mid[f][k] = (plus[k] + minus[k]) / 2;
                range[f][k] = plus[k] - minus[k];
                presserTargets[k] = mid[f][k];
                if (range[f][k] < PRESSER_MIN_RANGE_TICKS) {
                    LOG_ERROR("Presser %i barely moved (range %i)", first + k, (int) range[f][k]);
                    ok = false;
                }
            }
            if (!ok) break;
            ok = moveAndWait(first, presserTargets, NUM_PRESSERS, PRESSER_CAL_SPEED);
            if (!ok) break;
        }

        for (int s = 0; s < NUM_STRIKERS; ++s) sliderTargets[s] = 0;

        if (!ok) {
            LOG_ERROR("Presser homing FAILED at fret %i. Presser positions will be wrong.", presser_cal_frets[f]);
            moveAndWait(1, sliderTargets, NUM_STRIKERS, SLIDER_CAL_SPEED);
            return;
        }

        moveAndWait(1, sliderTargets, NUM_STRIKERS, SLIDER_CAL_SPEED);

        for (int k = 0; k < NUM_PRESSERS; ++k) {
            int32_t sum = 0;
            for (int i = 0; i < NUM_CAL_FRETS; ++i) sum += mid[i][k];
            presserTargets[k] = sum / NUM_CAL_FRETS;
        }
        moveAndWait(first, presserTargets, NUM_PRESSERS, PRESSER_CAL_SPEED);

        Serial.print("Presser homing at frets");
        for (int i = 0; i < NUM_CAL_FRETS; ++i) {
            Serial.print(i ? " / " : " ");
            Serial.print(presser_cal_frets[i]);
        }
        Serial.println(" (midpoint offset from rest, stall-to-stall range):");

        for (int k = 0; k < NUM_PRESSERS; ++k) {
            if (m_striker[first + k].setZeroHere() != kNoError) {
                LOG_ERROR("Presser %i could not be zeroed at rest", first + k);
            }

            int32_t lo = mid[0][k], hi = mid[0][k];
            Serial.print("  Presser ");
            Serial.print(first + k);
            Serial.print(": midpoint");
            for (int i = 0; i < NUM_CAL_FRETS; ++i) {
                Serial.print(i ? " / " : " ");
                Serial.print(mid[i][k] - presserTargets[k]);
                if (mid[i][k] < lo) lo = mid[i][k];
                if (mid[i][k] > hi) hi = mid[i][k];
            }
            Serial.print(", range");
            for (int i = 0; i < NUM_CAL_FRETS; ++i) {
                Serial.print(i ? " / " : " ");
                Serial.print(range[i][k]);
            }
            if (hi - lo > PRESSER_MIDPOINT_SPREAD_WARN) Serial.print("  <- midpoints disagree");
            Serial.println();
        }
    }

    int pluckerNode(int index) const {
        return NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + 1 + index;
    }

    int32_t pickerTicks(int node, float mm) const {
        int32_t ticks = (int32_t)(mm * m_striker[node].encoderResolution() / mm_to_enc_conversion_factor + 0.5f);
        return ticks < 1 ? 1 : ticks;
    }

    // True when |I| falls sharply between cadence samples: either a strong unload
    // (high load, >=200 mA drop to <=65%) or a mild one (weaker back-stroke plucks).
    static bool isPluckRelease(int prevMag, int mag) {
        int drop = prevMag - mag;
        if (prevMag >= PLUCK_LOADED_STRONG_MA
            && drop >= PLUCK_DROP_STRONG_MA
            && mag <= prevMag * PLUCK_REMAIN_STRONG_PCT / 100) {
            return true;
        }
        if (prevMag >= PLUCK_LOADED_MILD_MA
            && drop >= PLUCK_DROP_MILD_MA
            && mag <= prevMag * PLUCK_REMAIN_MILD_PCT / 100) {
            return true;
        }
        return false;
    }

    // Sweeps every plucker until the pick releases (or travel ends). Travel is each
    // plucker's tuned up stroke plus 25%, floor a quarter turn. Current is sampled
    // every travel/16 ticks — the same spacing as the debug SWEEP log the thresholds
    // were fit to — so dense loop timing cannot turn a cliff into a ramp.
    // On release, nudges past by PLUCK_CAL_MARGIN_MM and stops that motor.
    // release[k] is absolute ticks from hard-stop home; 0 means no release found.
    bool measureSweep(const int* sign, bool outward, bool pressing, const char* label,
                      int32_t* release, int* peakMag) {
        const int n = NUM_PLUCKERS;
        int32_t pos[NUM_PLUCKERS];
        int32_t origin[NUM_PLUCKERS];
        int32_t target[NUM_PLUCKERS];
        int32_t lastSamplePos[NUM_PLUCKERS];
        int step[NUM_PLUCKERS];
        int blank[NUM_PLUCKERS];
        int margin[NUM_PLUCKERS];
        int prevMag[NUM_PLUCKERS];
        bool havePrev[NUM_PLUCKERS] = {};
        bool done[NUM_PLUCKERS] = {};
        int remaining = n;

        for (int k = 0; k < n; ++k) {
            int node = pluckerNode(k);
            int res = m_striker[node].encoderResolution();
            if (!m_striker[node].readPosition(pos[k])) {
                LOG_ERROR("Plucker %i position read failed", node);
                return false;
            }
            origin[k] = pos[k];
            lastSamplePos[k] = pos[k];
            prevMag[k] = 0;
            release[k] = 0;
            peakMag[k] = 0;
            blank[k] = res / 8;
            margin[k] = pickerTicks(node, PLUCK_CAL_MARGIN_MM);
            int32_t tuned = (int32_t)(fabs(start_state_PICK[k]) * res / mm_to_enc_conversion_factor);
            int32_t travel = tuned + tuned / 4;
            if (travel < res / 4) travel = res / 4;
            step[k] = travel / 16;
            if (step[k] < 1) step[k] = 1;
            target[k] = outward ? pos[k] + sign[k] * travel : 0;
            if (m_striker[node].startMove(target[k], PLUCK_CAL_SPEED) != kNoError) {
                LOG_ERROR("Plucker %i could not start its sweep", node);
                done[k] = true;
                --remaining;
            }
        }

        while (remaining > 0) {
            for (int k = 0; k < n; ++k) {
                if (done[k]) continue;
                int node = pluckerNode(k);
                if (!m_striker[node].readPosition(pos[k])) continue;

                bool arrived = outward
                    ? abs(pos[k] - target[k]) <= step[k]
                    : abs(pos[k]) <= step[k];
                if (arrived) {
                    LOG_ERROR("Plucker %i never released on %s %s (peak %i mA)",
                              node, label, outward ? "out" : "back", peakMag[k]);
                    done[k] = true;
                    --remaining;
                    continue;
                }

                if (abs(pos[k] - lastSamplePos[k]) < step[k]) continue;

                int current = 0;
                if (!m_striker[node].readCurrent(current)) continue;
                int mag = abs(current);
                lastSamplePos[k] = pos[k];

                Serial.print("SWEEP ");
                Serial.print(label);
                Serial.print(outward ? " out " : " back ");
                Serial.print(node);
                Serial.print(' ');
                Serial.print(pos[k]);
                Serial.print(' ');
                Serial.println(current);

                if (abs(pos[k] - origin[k]) < blank[k]) {
                    havePrev[k] = true;
                    prevMag[k] = mag;
                    continue;
                }

                if (mag > peakMag[k]) peakMag[k] = mag;

                if (havePrev[k] && isPluckRelease(prevMag[k], mag)) {
                    release[k] = pos[k];
                    Serial.print("RELEASE ");
                    Serial.print(label);
                    Serial.print(outward ? " out " : " back ");
                    Serial.print(node);
                    Serial.print(' ');
                    Serial.print(pos[k]);
                    Serial.print(" drop ");
                    Serial.print(prevMag[k] - mag);
                    Serial.print(" mA (");
                    Serial.print(prevMag[k]);
                    Serial.print(" -> ");
                    Serial.print(mag);
                    Serial.println(")");
                    m_striker[node].nudge(pos[k] + sign[k] * margin[k]);
                    done[k] = true;
                    --remaining;
                    continue;
                }

                havePrev[k] = true;
                prevMag[k] = mag;
            }
            if (pressing) holdPressers(presser_cal_torque);
            delay(2);
        }

        for (int k = 0; k < n; ++k) {
            if (release[k] == 0) return false;
        }
        return true;
    }

    bool movePluckersTo(const int32_t* targets, bool holdPress = false) {
        return moveAndWait(pluckerNode(0), targets, NUM_PLUCKERS, PLUCK_CAL_SPEED, holdPress);
    }

    void holdPressers(int16_t torque) {
        for (int k = 0; k < NUM_PRESSERS; ++k) m_striker[NUM_STRIKERS + 1 + k].holdTorque(torque);
    }

    // Measures both pick releases on an open string and with fret 9 pressed.
    // Playback still uses up_pluck_mm / down_pluck_mm; this prints measured ticks.
    void homePluckers() {
        const int n = NUM_PLUCKERS;
        int sign[NUM_PLUCKERS];
        int32_t home[NUM_PLUCKERS];
        int32_t backoff[NUM_PLUCKERS];
        int32_t farTick[2][NUM_PLUCKERS] = {};
        int32_t nearTick[2][NUM_PLUCKERS] = {};
        int farPeak[2][NUM_PLUCKERS] = {};
        int nearPeak[2][NUM_PLUCKERS] = {};
        bool okState[2] = {};
        const char* stateName[2] = {"open", "fret9"};

        int fret9 = -1;
        for (int i = 0; i < NUM_CAL_FRETS; ++i) {
            if (presser_cal_frets[i] == 9) fret9 = i;
        }

        for (int k = 0; k < n; ++k) {
            sign[k] = start_state_PICK[k] >= 0.f ? 1 : -1;
            home[k] = 0;
            int node = pluckerNode(k);
            backoff[k] = sign[k] * pickerTicks(node, PLUCK_CAL_BACKOFF_MM);
        }

        for (int state = 0; state < 2; ++state) {
            bool pressing = state == 1;
            if (pressing) {
                if (fret9 < 0) {
                    LOG_ERROR("Fret 9 is not in the slider table");
                    break;
                }
                int32_t sliderTargets[NUM_STRIKERS];
                for (int s = 0; s < NUM_STRIKERS; ++s) sliderTargets[s] = presser_cal_slider_ticks[fret9][s];
                if (!moveAndWait(1, sliderTargets, NUM_STRIKERS, SLIDER_CAL_SPEED)) {
                    LOG_ERROR("Sliders did not reach fret 9");
                    break;
                }
                bool pressed = true;
                for (int k = 0; k < NUM_PRESSERS && pressed; ++k) {
                    if (m_striker[NUM_STRIKERS + 1 + k].startTorque() != kNoError) pressed = false;
                }
                if (!pressed) {
                    LOG_ERROR("Pressers did not engage for fret 9");
                    for (int k = 0; k < NUM_PRESSERS; ++k) m_striker[NUM_STRIKERS + 1 + k].stopTorque();
                    break;
                }
                holdPressers(presser_cal_torque);
            }

            bool swept = movePluckersTo(backoff, pressing)
                && measureSweep(sign, true, pressing, stateName[state], farTick[state], farPeak[state]);
            for (int k = 0; k < n; ++k) sign[k] = -sign[k];
            // Fret 9 often has weaker / missing signatures; do not fail the whole state
            // if only the return stroke misses — still record what we got.
            bool backOk = measureSweep(sign, false, pressing, stateName[state],
                                       nearTick[state], nearPeak[state]);
            for (int k = 0; k < n; ++k) sign[k] = -sign[k];
            okState[state] = swept && backOk;
            if (!okState[state]) {
                LOG_ERROR("Pluck measurement incomplete for %s", stateName[state]);
            }

            movePluckersTo(home, pressing);
            if (pressing) {
                for (int k = 0; k < NUM_PRESSERS; ++k) m_striker[NUM_STRIKERS + 1 + k].stopTorque();
            }
        }

        int32_t sliderHome[NUM_STRIKERS] = {};
        moveAndWait(1, sliderHome, NUM_STRIKERS, SLIDER_CAL_SPEED);

        Serial.println("Plucker release ticks from hard stop (near / far), peak |I| in mA:");
        for (int state = 0; state < 2; ++state) {
            Serial.print("  ");
            Serial.print(stateName[state]);
            Serial.println(okState[state] ? ":" : " (incomplete):");
            for (int k = 0; k < n; ++k) {
                Serial.print("    Plucker ");
                Serial.print(pluckerNode(k));
                Serial.print(": ");
                if (nearTick[state][k] == 0) {
                    Serial.print("no release (");
                    Serial.print(nearPeak[state][k]);
                    Serial.print(")");
                } else {
                    Serial.print(nearTick[state][k]);
                    Serial.print(" (");
                    Serial.print(nearPeak[state][k]);
                    Serial.print(")");
                }
                Serial.print(" / ");
                if (farTick[state][k] == 0) {
                    Serial.print("no release (");
                    Serial.print(farPeak[state][k]);
                    Serial.print(")");
                } else {
                    Serial.print(farTick[state][k]);
                    Serial.print(" (");
                    Serial.print(farPeak[state][k]);
                    Serial.print(")");
                }
                Serial.println();
            }
        }
    }
    // static void clearFaultTimerIRQHandler() {
    //     for (int i = 1; i < NUM_STRIKERS + 1; ++i) {
    //         pInstance->m_striker[i].checkAndRecover();
    //     }
    // }
};

StrikerController* StrikerController::pInstance = nullptr;
#endif // STRIKERCONTROLLER_H
