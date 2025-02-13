//
// Created by Raghavasimhan Sankaranarayanan on 03/30/22.
// Modified for plucking prototype, Marcus Parker
#ifndef STRIKERCONTROLLER_H
#define STRIKERCONTROLLER_H
#include <math.h>

#include "def.h"
#include "striker.h"
#include <HardwareTimer.h>
#include "Trajectory.h"
#include <ArduinoQueue.h>
#include <ArduinoEigen.h>
#include "networkHandler.h"
#include <iostream>


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
        MotorSpec spec2 = EC20;
        err = kNoError;
        for (int i = NUM_STRIKERS + 1; i < NUM_PRESSERS + NUM_STRIKERS + 1; ++i) {
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
        MotorSpec spec3 = EC45_StrummerSlider;
        err = kNoError;
        for (int i = NUM_STRIKERS + NUM_PRESSERS + 1; i < NUM_PRESSERS + NUM_STRIKERS + NUM_STRUMMER_SLIDERS + 1; ++i) {
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

        MotorSpec spec4 = EC45_StrummerPicker;
        err = kNoError;
        for (int i = NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + 1; i < NUM_PRESSERS + NUM_STRIKERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + 1; ++i) {
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

        MotorSpec spec5 = EC45_Plucker_1024;
        MotorSpec spec6 = EC45_Plucker_2048;
        err = kNoError;
        for (int i = NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + 1; i < NUM_PRESSERS + NUM_STRIKERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + NUM_PLUCKERS + 1; ++i) {
            LOG_LOG("Plucker %i", i);
            if(i == 15){
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
        for (int i = 1; i < NUM_STRIKERS + 1; ++i) {
            m_striker[i].startHome(i);
            }
        int ii = 0;
        bool isHoming_all = true;
        bool isHoming_1 = true;
        bool isHoming_2 = true;
        bool isHoming_3 = true;
        bool isHoming_4 = true;
        bool isHoming_5 = true;
        bool isHoming_6 = true;

        while (isHoming_all) {
            delay(50);
            isHoming_1 = m_striker[1].homingStatus();
            isHoming_2 = m_striker[2].homingStatus();
            isHoming_3 = m_striker[3].homingStatus();
            isHoming_4 = m_striker[4].homingStatus();
            isHoming_5 = m_striker[5].homingStatus();
            isHoming_6 = m_striker[6].homingStatus();
            isHoming_all = isHoming_1 || isHoming_2 || isHoming_3 || isHoming_4 || isHoming_5 || isHoming_6;

            if (ii++ > 200) break;
        }
        delay(500);

        LOG_LOG("Homing for sliders complete, starting pressers. ");
        for (int i = NUM_STRIKERS + 1; i < NUM_PRESSERS + NUM_STRIKERS + 1; ++i) {
            m_striker[i].startHome(i);
            }
        while (isHoming_all) {
            delay(50);
            isHoming_1 = m_striker[7].homingStatus();
            isHoming_2 = m_striker[8].homingStatus();
            isHoming_3 = m_striker[9].homingStatus();
            isHoming_4 = m_striker[10].homingStatus();
            isHoming_5 = m_striker[11].homingStatus();
            isHoming_6 = m_striker[12].homingStatus();
            isHoming_all = isHoming_1 || isHoming_2 || isHoming_3 || isHoming_4 || isHoming_5 || isHoming_6;

            //if (ii++ > 200) break;
        }
        LOG_LOG("Homing for pressers complete, starting pluckers. ");
        for (int i = NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + 1; i < NUM_PRESSERS + NUM_STRIKERS + NUM_STRUMMER_SLIDERS + NUM_STRUMMER_PICKERS + NUM_PLUCKERS + 1; ++i) {
            m_striker[i].startHome(i);
        }
        while (isHoming_all) {
            delay(50);
            //CHANGE ME
            isHoming_1 = m_striker[15].homingStatus();
            isHoming_2 = m_striker[16].homingStatus();
            isHoming_all = isHoming_1 || isHoming_2;
            if (ii++ > 200) break;
        }
        LOG_LOG("Homing for pluckers complete, starting strummer. ");
//        delay(20000);
        for (int i = NUM_STRIKERS + NUM_PRESSERS + NUM_STRUMMER_SLIDERS + 1; i < NUM_PRESSERS + NUM_STRIKERS + NUM_STRUMMER_SLIDERS +NUM_STRUMMER_PICKERS + 1; ++i) {
            m_striker[i].startHome(i);
        }
        bool checkHome = false;
        isHoming_2 = true;
        isHoming_all = isHoming_1 || isHoming_2;
        while (isHoming_all) {
            delay(50);
            isHoming_1 = m_striker[14].homingStatus();
            if(!checkHome && !isHoming_1){
                checkHome = true;
                m_striker[13].startHome(13);
            }

            if(checkHome){
                isHoming_2 = m_striker[13].homingStatus();
            }

            isHoming_all = isHoming_1 || isHoming_2;

            //Serial.println(ii);

            if (ii++ > 200) break;
        }

        Serial.println("finished initializing and homing all controllers.");
//        delay(45000);
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
    void executeStrumTest(int strumType, int speed, int deflect) {
//        while(pInstance->m_traj.count() > 1) {
//            delay(10); //test with 1ms later
//            Serial.println("Waiting until event complete....");
//        }

        //Slider
        float strummerIdle[5];
        float strummerMove[speed];
        //Picker
        float pickerMoving_1[5];
        float pickerMoving_2[speed];
        //Other motors
        float non_strummerIdle[speed + 5];
        int strum_mm_qf = -115;
        float picker_mm_qf_1 = 8; //UPSTRUM: 8 -> 9, DOWNSTRUM: 10 -> 9
        float picker_mm_qf_2 = 10;
        switch(strumType){
            case -45:
                //upstrum, point picker down
                picker_mm_qf_1 = 8;
                picker_mm_qf_2 = 8;
                strum_mm_qf = -115;
                Serial.println("Recieved Upstrum"); //passed, same result
                if(deflect == 1){
                    picker_mm_qf_1 = 4;
                    picker_mm_qf_2 = 4;
                }
            break;

            case 45:
                //downstrum, point picker up
                picker_mm_qf_1 = 10;
                picker_mm_qf_2 = 10;
                strum_mm_qf = -15;
                Serial.println("Recieved Downstrum"); // passed, same result
                if(deflect == 1){
                    picker_mm_qf_1 = 4;
                    picker_mm_qf_2 = 4;
                }
                break;
        }
        //Check if elements exist in the queue here, set list of q0's.

        for(int i = 1; i < NUM_MOTORS + 1; i++) {
            float q0 = m_striker[i].getPosition_ticks();

            if (i == 13) {
                // Get initial position in position ticks
                //Translate pluckType to position ticks and assign to qf
                float qf_strummerSlider = (strum_mm_qf * 2048) / 9.4;
                //Interpolate Line
                Util::fill(strummerIdle, 5, q0);
                Util::interpWithBlend(q0, qf_strummerSlider, speed, .05, strummerMove);
                // Put line into list of trajs
                int index = 0;
                for (int x = 0; x < 5; x++) {
                    all_Trajs[i - 1][index++] = strummerIdle[x];
                    //Serial.println(strummerIdle[x]); //doesn't get properly pushed to the queue... but values are correct
                }
                //was not supposed to be a 0 for x = _
                for (int x = 0; x < speed; x++) {
                    all_Trajs[i - 1][index++] = strummerMove[x];
                    //Serial.println(strummerMove[x]);
                }

            }
            else if (i == 14) {
                // Get initial position in position ticks
                //
                float pos2pulse = (picker_mm_qf_1 * 2048) / 9.4;
                float qf_1 = pos2pulse;
                pos2pulse  = (picker_mm_qf_2 * 2048) / 9.4;
                float qf_2 = pos2pulse;
                //Interpolate Line
                Util::interpWithBlend(q0, qf_1, 5, .25, pickerMoving_1);
                Util::interpWithBlend(qf_1, qf_2, speed, .05, pickerMoving_2);

                // Put line into list of trajs
                int index = 0;
                for (int x = 0; x < 5; x++) {
                    all_Trajs[i - 1][index++] = pickerMoving_1[x];
                    //Serial.println(temp_traj_1[x]);
                }
                for (int x = 0; x < speed; x++) {
                    all_Trajs[i - 1][index++] = pickerMoving_2[x];
                    //Serial.println(temp_traj_1[x]);
                }
            } else {
                    Util::fill(non_strummerIdle, speed + 5, q0);
                    int index = 0;
                    for (int x = 0; x < speed + 5; x++) {
                        all_Trajs[i - 1][index++] = non_strummerIdle[x];
                    }
                }
            }
        //TODO: add to queue
        //Make and push traj points to queue
        Trajectory<int32_t>::point_t temp_point;
        for (int i = 0; i < speed + 5; i++) {
            for(int x = 0; x < NUM_MOTORS; x++){
                temp_point[x] = all_Trajs[x][i];
//                Serial.print(all_Trajs[x][i]);
//                Serial.print(" ");
            }
//            Serial.println("");
            m_traj.push(temp_point);
        }

    }
    void executeSetPickerTest(char position){
        float temp_traj_1[5];
        int picker_mm_qf = 9;
        switch(position){
            case 'D':
                //prepare for upstrum
                picker_mm_qf = 8;
                break;
            case 'U':
                //prepare for downstrum
                picker_mm_qf = 10;
                break;
        }

        for(int i = 1; i < NUM_MOTORS + 1; i++) {
            float q0 = m_striker[i].getPosition_ticks();
            if(i == 15){
                // Get initial position in position ticks

                float pos2pulse = (picker_mm_qf * 2048) / 9.4;
                float qf = pos2pulse;
                //Interpolate Line
                Util::interpWithBlend(q0, qf, 5, .25, temp_traj_1);
                // Put line into list of trajs
                int index = 0;
                for (int x = 0; x < 5; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_1[x];
                    //Serial.println(temp_traj_1[x]);
                }

            } else {
                Util::fill(temp_traj_1, 5, q0);
                int index = 0;
                for (int x = 0; x < 5; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_1[x];
                }
            }
        }

        //TODO: add to picker queue
        //Make and push traj points to queue
        Trajectory<int32_t>::point_t temp_point;
        for (int i = 0; i < 5; i++) {
            for(int x = 0; x < NUM_MOTORS; x++){
                //I'd like to seperate all_trajs between left and right hand at some point.
                temp_point[x] = all_Trajs[x][i];
            }
            m_traj.push(temp_point);
        }

    }




    void executeSlideTest(int string_1, int string_2, int string_3, int string_4, int string_5, int string_6, int frets_1, int frets_2) {

        strings[1] = string_1;
        strings[2] = string_2;
        strings[3] = string_3;
        strings[4] = string_4;
        strings[5] = string_5;
        strings[6] = string_6;
        strings[7] = frets_1;
        strings[8] = frets_2;

        float fretLength;
        float pos2pulse;
        float temp_traj_1[40];
        float temp_traj_2[20];
        float q0;
        float qf;

        for(int i = 1; i < NUM_MOTORS + 1; i++) {
            int mult = -1;
            if (i == 2 || i == 3 || i == 6) {
                mult = 1;
            }
            if (i < 7) {
                fretLength = (SCALE_LENGTH - (SCALE_LENGTH / pow(2, (strings[i] / 12.f)))) - 12;
                pos2pulse = (mult * fretLength * 2048) / 10;
                q0 = m_striker[i].getPosition_ticks();
                qf = (i > 6) ? strings[i] : pos2pulse;
            } else {
                q0 = m_striker[i].getPosition_ticks();
                qf = (i > 6) ? strings[i] : -5;
            }

            if (i < 7) {
                Util::fill(temp_traj_1, 40, q0);
                Util::interpWithBlend(q0, qf, 20, .05, temp_traj_2);
            } else {
                Util::interpWithBlend(q0, -5, 40, .25, temp_traj_1);
                Util::interpWithBlend(-5, qf, 20, .25, temp_traj_2);
            }

            for (int x = 0; x < 40; x++) {
                all_Trajs[i - 1][x] = temp_traj_1[x];
            }
            for (int x = 0; x < 20; x++) {
                all_Trajs[i - 1][x + 40] = temp_traj_2[x];
            }
        }

        Trajectory<int32_t>::point_t temp_point;
        for (int i = 0; i < 60; i++) {
            for(int x = 0; x < NUM_MOTORS; x++){
                Serial.println(all_Trajs[x][i]);
                temp_point[x] = all_Trajs[x][i];
            }
            m_traj.push(temp_point);

        }
    }

    /*
        Function: processTrajPoints
        Input: List of trajectory points for all motors
        Output: Pushes point to the queue
    */
    void processTrajPoints(float *trajPoint)
    {
        int packetSize = 13;
        Serial.print("RECEIVED: ");
        for(int i = 0; i<packetSize; i++)
        {
            Serial.print(trajPoint[i]);
            Serial.print(" ");
        }
        Serial.println();

        for(int x = 0; x < NUM_MOTORS; x++){
            if(x < 14)
            {
                all_Trajs[x][0] = trajPoint[x];
            }
            else if(x == 14 || x == 15) // picker set to default number for now
            {
                all_Trajs[x][0] = 762; //default value in encoder ticks, same as in start()
            }
        }

        //Serial.println("PROCESSED TRAJ: ");

        //Serial.println();
        //Serial.println("PUSHING TO QUEUE: ");
        Trajectory<int32_t>::point_t temp_point;
        for(int x = 0; x < NUM_MOTORS; x++){
            temp_point[x] = all_Trajs[x][0];
            //Serial.println(temp_point[x]);
        }
        //Serial.println("-------");
        m_traj.push(temp_point);

    }

    


    /*
        Function: Execute Event
        Inputs: uint8_t playcommand[6], uint8_t fret[6], uint8_t pickings[6], int strumAngle
        Outputs: Calls executeSlide(), executeStrum(), executePluckTest() which fills allTrajs with all trajectories
    */
    void executeEvent(char eventType,uint8_t *frets, uint8_t *playcommands, uint8_t *pickings, int tremLength, int tremSpeed, int strumAngle, int strumSpeed, int deflect)
    {//Add variable to check message type.
       //Making sure we receive all necessary data properly
//        for(int i = 0; i<6; i++)
//        {
//            LOG_LOG("fret: %i", frets[i]);
//            LOG_LOG("playcommand: %i ", playcommands[i]);
//            LOG_LOG("pickings: %i", pickings[i]);
//        }
//        LOG_LOG("strumAngle: %i", strumAngle);



        while(pInstance->m_traj.count() > 1) {
            delay(10); //test with 1ms later
            Serial.println("Waiting until event complete....");
        }


        if(eventType == 'L'){
        //1
            LOG_LOG("LH message received.");
            // 1a. Call executeSlide() to process LH events -- fills all_Trajs[0-12] with trajectories
            //executeSlideDEMO(frets, playcommands); //(Rename to 'getSlideTraj' when this function no longer pushes to the queue.)
            executeSlideDEMO(frets, playcommands);
            // 1b. Fill other motors with current value
        }
        else if(eventType == 'S'){
        //2
            LOG_LOG("Strum message received.");
            executeStrumTest(strumAngle, strumSpeed, deflect);

        //
        }
        else if(eventType == 'P'){
        //3
            LOG_LOG("Pluck message received.");
            //1. Pass all pickings
            //2.
            executePluckTest(pickings, tremLength, tremSpeed);

            //3a. Call getPickTraj
            //3b. Call Fill_LH to fill LH with current value or 38 for pressing motors.
        }
        else{
            LOG_LOG("Message unhandled, skipping.");
        }

//        // 4. Append trajectories to super queue
//        Trajectory<int32_t>::point_t temp_point;
//        for (int i = 0; i < 60; i++) {
//            for(int x = 0; x < NUM_MOTORS; x++){
//                temp_point[x] = all_Trajs[x][i];
//            }
//            m_traj.push(temp_point);
//        }

    }


    void executeSlideDEMO(uint8_t *frets, uint8_t *playcommands) {
        int mult = -1;


        strings[1] = fminf(frets[0], 9); // setting to max out at 9 for now
        strings[2] = fminf(frets[1], 9);
        strings[3] = fminf(frets[2], 9);
        strings[4] = fminf(frets[3], 9);
        strings[5] = fminf(frets[4], 9);
        strings[6] = fminf(frets[5], 9);

        strings[7] = playcommands[0];
        strings[8] = playcommands[1];
        strings[9] = playcommands[2];
        strings[10] = playcommands[3];
        strings[11] = playcommands[4];
        strings[12] = playcommands[5];
        while(pInstance->m_traj.count() > 1) {
            delay(10); //test with 1ms later
            Serial.println("Waiting until event complete....");
        }

        strings[13] = 0;
        for(int i = 0; i < 6; i++){
            //Serial.println(strings[i+7]);
            switch (strings[i + 7]) {
                case 1:
                    strings[i + 7] = -10;
                    break;
                case 2:
                    strings[i + 7] = 38;
                    break;
                case 3:
                    strings[i + 7] = 23;
                    break;
                default:
                    strings[i + 7] = -10;
                    break;
            }
            //Serial.println(strings[i+7]);
        }

        //Unpress -> Slide -> Press
        //Sliders:
        float q0_traj[20];
        float move_traj[20];
        float qf_traj[20];


        //Pressers:
        float unpress_traj[20];
        float hold_traj[20];
        float press_traj[20];

        float sixty_traj[60];


        for(int i = 1; i< NUM_MOTORS + 1; i++) {
            mult = -1;
            //float fretLength = (SCALE_LENGTH - (SCALE_LENGTH / pow(2, (((strings[i])) / 12.f)))) - 20;

            float fretLength = FRET_LENGTHS[strings[i]] - 20;
            float pos2pulse = (fretLength * 2048) / 9.4;
            if (i == 2 || i == 3 || i == 6) {
                mult = 1;
            }
//            Serial.print("Fret Length at Slider ");
//            Serial.println(i);
//            Serial.println()
            pos2pulse = mult * pos2pulse;
            float q0 = m_striker[i].getPosition_ticks();
            float qf = pos2pulse;
            if (i > 6) {
                qf = strings[i];
            }
            if (i < 7) { // SLIDERS: q0 for 20, Slide for 20, qf for 20
                Util::fill(q0_traj, 20, q0);
                Util::interpWithBlend(q0, qf, 20, .05, move_traj);
                Util::fill(qf_traj, 20, qf);
                int index = 0;
                for (int x = 0; x < 20; x++) {
                    all_Trajs[i - 1][index++] = q0_traj[x];
                }
                for (int x = 0; x < 20; x++) {
                    all_Trajs[i - 1][index++] = move_traj[x];
                }
                for (int x = 0; x < 20; x++) {
                    all_Trajs[i - 1][index++] = qf_traj[x];
                }

            } else if( i > 6 && i < 13) { //PRESSERS
                if(frets[i - 7] == prev_frets[i - 7]) //IF NO SLIDING
                {
                    Serial.print("No fret change on string ");
                    Serial.println(i-6);
                    Serial.print("The previous fret at ");
                    Serial.print(i-6);
                    Serial.print(" is ");
                    Serial.println(prev_frets[i - 7]);
                    Serial.print("The fret at ");
                    Serial.print(i);
                    Serial.print(" is ");
                    Serial.println(frets[i - 7]);
//                    Serial.println(i);

                    if(playcommands[i-7] != prev_playcommands[i-7]) //IF NO SLIDING AND NEED TO PRESS/UNPRESS
                    {
                        Serial.println("Same fret press/unpress on string ");
//                        Serial.println(prev_playcommands[i-7]);
//                        Serial.println(playcommands[i-7]);
                        Serial.println(q0);
                        Serial.println(qf);

                        Util::interpWithBlend(q0, qf, 60, .05, sixty_traj);
                        int index = 0;
                        for (int x = 0; x < 60; x++) {
                            all_Trajs[i - 1][index++] = sixty_traj[x];
                        }
                    }
                    else // NO SLIDING OR CHANGE IN PRESSING
                    {
                        Util::fill(sixty_traj, 60, q0);
                        int index = 0;
                        for (int x = 0; x < 60; x++) {
                            all_Trajs[i - 1][index++] = sixty_traj[x];
                        }
                    }

                }
                else //SLIDING
                {//PRESSERS: Unpress for 20, hold for 20, press for 20;
                    Serial.print("Tripped regular change on string ");
                    Serial.println(i);
                    Serial.print("The previous fret at ");
                    Serial.print(i);
                    Serial.print(" is ");
                    Serial.println(prev_frets[i - 7]);
                    Serial.print("The fret at ");
                    Serial.print(i);
                    Serial.print(" is ");
                    Serial.println(frets[i - 7]);

                    Util::interpWithBlend(q0, -10, 20, .25, unpress_traj);
                    Util::fill(hold_traj, 20, -10);
                    Util::interpWithBlend(-10, qf, 20, .25, press_traj);
                    int index = 0;
                    for (int x = 0; x < 20; x++) {
                        all_Trajs[i - 1][index++] = unpress_traj[x];
                    }
                    for (int x = 0; x < 20; x++) {
                        all_Trajs[i - 1][index++] = hold_traj[x];
                    }
                    for (int x = 0; x < 20; x++) {
                        all_Trajs[i - 1][index++] = press_traj[x];
                    }
                }
            } else {
                Util::fill(sixty_traj, 60, q0);
                int index = 0;
                for (int x = 0; x < 60; x++) {
                    all_Trajs[i - 1][index++] = sixty_traj[x];
                }
            }
        }

        Trajectory<int32_t>::point_t temp_point;
        for (int i = 0; i < 60; i++) {
        Serial.print(i);
        Serial.print(": ");
            for(int x = 0; x < NUM_MOTORS; x++){
                temp_point[x] = all_Trajs[x][i];
                Serial.print(temp_point[x]);
                Serial.print(" ");
            }
            Serial.println();
            m_traj.push(temp_point);
        }

        //Set previous trajectories
        for(int i = 0; i<6; i++)
        {
            prev_frets[i] = frets[i];
        }

    }


        void executeSlide(uint8_t *frets, uint8_t *playcommands) {
        int mult = -1;

        strings[1] = fminf(frets[0], 9); // setting to max out at 9 for now
        strings[2] = fminf(frets[1], 9);
        strings[3] = fminf(frets[2], 9);
        strings[4] = fminf(frets[3], 9);
        strings[5] = fminf(frets[4], 9);
        strings[6] = fminf(frets[5], 9);

        strings[7] = playcommands[0];
        strings[8] = playcommands[1];
        strings[9] = playcommands[2];
        strings[10] = playcommands[3];
        strings[11] = playcommands[4];
        strings[12] = playcommands[5];

        strings[13] = 0;
        for(int i = 0; i < 6; i++){
            //Serial.println(strings[i+7]);
            switch (strings[i + 7]) {
                case 1:
                    strings[i + 7] = -10;
                    break;
                case 2:
                    strings[i + 7] = 36;
                    break;
                case 3:
                    strings[i + 7] = 23;
                    break;
                default:
                    strings[i + 7] = -10;
                    break;
            }
            //Serial.println(strings[i+7]);
        }

        float temp_traj_1[40];
        float temp_traj_2[20];

        for(int i = 1; i < NUM_MOTORS + 1; i++) {
            mult = -1;
            float fretLength = (SCALE_LENGTH - (SCALE_LENGTH / pow(2, (((strings[i])) / 12.f)))) - 20;
            float pos2pulse = (fretLength * 2048) / 9.4;
            if (i == 2 || i == 3 || i == 6) {
                mult = 1;
            }
            pos2pulse = mult * pos2pulse;
            float q0 = m_striker[i].getPosition_ticks();
            float qf = pos2pulse;
            if (i > 6) {
                qf = strings[i];
            }
            if (i < 7) {
                Util::fill(temp_traj_1, 40, q0);
                Util::interpWithBlend(q0, qf, 20, .05, temp_traj_2);
                int index = 0;
                for (int x = 0; x < 40; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_1[x];
                }
                for (int x = 0; x < 20; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_2[x];
                }
            } else if( i > 6 && i < 13) {
                Util::interpWithBlend(q0, -10, 40, .25, temp_traj_1);
                Util::interpWithBlend(-10, qf, 20, .25, temp_traj_2);
                int index = 0;
                for (int x = 0; x < 40; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_1[x];
                }
                for (int x = 0; x < 20; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_2[x];
                }
            } else {
                Util::fill(temp_traj_1, 40, q0);
                Util::fill(temp_traj_2, 20, q0);
                int index = 0;
                for (int x = 0; x < 40; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_1[x];
                }
                for (int x = 0; x < 20; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_2[x];
                }
            }
        }

        Trajectory<int32_t>::point_t temp_point;
        for (int i = 0; i < 60; i++) {
//        Serial.print(i);
//        Serial.print(": ");
            for(int x = 0; x < NUM_MOTORS; x++){
                temp_point[x] = all_Trajs[x][i];
//                Serial.print(temp_point[x]);
//                Serial.print(" ");
            }
//            Serial.println();
            m_traj.push(temp_point);
        }

    }

    void executePluckTest(uint8_t *pluckType, int tremLength, int tremSpeed) {
//        LOG_LOG("EXECUTE_PLUCK");
        // Make space for temporary trajs
        int tremTraj;

        //Setting the pluck type to be the same for all strings for now, if there is a pluck/tremolo. 0 Still turns off the plucker.
        int pt = pluckType[0];
        if (pt == 1)
        {
            tremLength = 5;
            tremTraj = 5;
        }
        else if (pt == 2)
        {
            tremTraj = (tremSpeed * 2) + 10;
        }
        float temp_traj_1[tremTraj];
        float pluckLength = -1;

        //handle direction
        if (pt == 1 || pt == 2){  //If command is pick/tremolo
            if (!pickerStates[0]){
                pluckLength = 3;    //downstrum
            } else {
                pluckLength = 7;    //upstrum
            }
        } else {
            return;
        }
        //TODO: change for picker
        for(int i = 1; i < NUM_MOTORS + 1; i++) {
            float q0 = m_striker[i].getPosition_ticks();
            if(i >= 15 && (pluckType[i-15] != 0)){
                // Get initial position in position ticks
                //Translate pluckType to position ticks and assign to qf
                float pos2pulse = (pluckLength * 1024) / 9.4;
                if(i == 16){
                    pos2pulse = ((pluckLength - 3) * 2048) / 9.4;
                }
                float qf = pos2pulse;
                //Interpolate Line

                Util::interpWithBlend(q0, qf, 5, .25, temp_traj_1);
                pickerStates[i-15] = !pickerStates[i-15];
                // Put line into list of trajs
                int index = 0;
                for (int x = 0; x < 5; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_1[x];
                }

                if (pt == 2) {
                    Util::fill(temp_traj_1, tremSpeed, qf);
                    for (int x = 0; x < tremSpeed; x++) {
                        all_Trajs[i - 1][index++] = temp_traj_1[x];
                    }

                    Util::interpWithBlend(qf, q0, 5, .25, temp_traj_1);
                    pickerStates[i-15] = !pickerStates[i-15];
                    // Put line into list of trajs
                    for (int x = 0; x < 5; x++) {
                        all_Trajs[i - 1][index++] = temp_traj_1[x];
                    }

                    Util::fill(temp_traj_1, tremSpeed, q0);
                    for (int x = 0; x < tremSpeed; x++) {
                        all_Trajs[i - 1][index++] = temp_traj_1[x];
                    }
                }
            } else {
                Util::fill(temp_traj_1, tremTraj, q0);
                int index = 0;
                for (int x = 0; x < tremTraj; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_1[x];
                }
            }
        }

        //TODO: add to picker queue
        //Make and push traj points to queue
        Trajectory<int32_t>::point_t temp_point;
        for (int t = 0; t < tremLength/tremTraj; t++){
            for (int i = 0; i < tremTraj; i++) {
                for(int x = 0; x < NUM_MOTORS; x++){
                    //I'd like to seperate all_trajs between left and right hand at some point.
                    temp_point[x] = all_Trajs[x][i];
                    Serial.print(temp_point[x]);
                    Serial.print(" ");
                }
                Serial.println();
                m_traj.push(temp_point);
            }
        }
//        LOG_LOG("END_EXECUTE_PLUCK_TEST");
    }



    void executeCommand(uint8_t idCode, char mode, int midiVelocity, uint8_t channelPressure) {

        if (midiVelocity >= 10 || midiVelocity <= 0){
            midiVelocity = 1;
        }
        int mult = -1;
        if(idCode == 2 || idCode == 3 || idCode == 4|| idCode == 6){
            mult = 1;
        }

        float fretLength = (SCALE_LENGTH - (SCALE_LENGTH / pow(2, (((midiVelocity)) / 12.f)))) - 12;
        //float fretLength = (SCALE_LENGTH - (SCALE_LENGTH / pow(2, (((midiVelocity)) / 12.f))));
        float pos2pulse = (fretLength * 2048) / 10;
        //pos2pulse = (360 * pos2pulse) / 2048;
//        Serial.print("Position is: ");
//        Serial.print(" ");
//        Serial.print(fretLength);
//        Serial.print(" ");
//        Serial.print("pulse is: ");
//        Serial.print(" ");
//        Serial.println(pos2pulse);
        midiVelocity = mult*pos2pulse;

        if(idCode > 6){
            pos2pulse = (360 * 23) / 1024;
        }

        float m_afTraj[20];
        Trajectory<int32_t>::point_t temp_point;
        float q0 = m_striker[1].getPosition_ticks();
//        Serial.println("q0, qf, and midivelocity");
//        Serial.println(q0);
        float qf = pos2pulse;
//        Serial.println(qf);
//        Serial.println(midiVelocity);
        Util::interpWithBlend(q0,midiVelocity, 20,.05, m_afTraj);
        for (int i = 0; i < 20; i++) {
            temp_point[0] = m_afTraj[i];
            //Serial.println(m_afTraj[i]);
            m_traj.push(temp_point);
        }


        //uint8_t uiStrike = prepare(idCode, mode, midiVelocity, channelPressure);
        //strike(uiStrike);

    }
    //TODO: picker queue?
    void start() {
        float start_state_SS = -110;
        float start_state_SP = 9;
        float start_state_PICK = 7;
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

            if(i >= 15){ //Picker
                pos2pulse = (start_state_PICK * 1024) / 9.4;
                if(i == 16){
                    start_state_PICK = 4;
                    pos2pulse = (start_state_PICK * 2048) / 9.4;
                }
                qf = pos2pulse;
                temp_point[i - 1] = pos2pulse;
                //Interpolate Line
                Util::interpWithBlend(q0, qf, 50, .25, temp_traj_1);
                Util::fill(temp_traj_2, 50, qf);
                // Put line into list of trajs
                int index = 0;
                for (int x = 0; x < 50; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_1[x];
                }
                for (int x = 0; x < 50; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_2[x];
                }
            }
            else if(i == 13){ //Strum Slider
                pos2pulse = (start_state_SS * 2048) / 9.4;
                qf = pos2pulse;
                temp_point[i - 1] = pos2pulse;

                Util::interpWithBlend(q0, qf, 50, .05, temp_traj_1);
                Util::fill(temp_traj_2, 50, qf);
                int index = 0;
                for (int x = 0; x < 50; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_1[x];
                }
                for (int x = 0; x < 50; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_2[x];
//                    Serial.println(index);
//                    Serial.println(temp_traj_2[x]);
                }
            }
            else if(i == 14){ // Strum Picker
                pos2pulse = (start_state_SP * 2048) / 9.4;
                qf = pos2pulse;
                temp_point[i - 1] = pos2pulse;
                Util::fill(temp_traj_1, 50, q0);
                Util::interpWithBlend(q0, qf, 50, .05, temp_traj_2);

                int index = 0;
                for (int x = 0; x < 50; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_1[x];
                }
                for (int x = 0; x < 50; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_2[x];
                }
            }
            else
            {
                Util::fill(temp_traj_3, 100, q0);
                int index = 0;
                for (int x = 0; x < 100; x++) {
                    all_Trajs[i - 1][index++] = temp_traj_3[x];
                }
            }

            m_currentPoint[i - 1] = kInitials[i - 1];
        }


        //Trajectory<int32_t>::point_t temp_point;
        for (int i = 0; i < 100; i++) {
            for(int x = 0; x < NUM_MOTORS; x++){
                temp_point[x] = all_Trajs[x][i];
            }
            m_traj.push(temp_point);
        }



            //PLUCKER PROTOTYPE:
//        float offset = 7; //MINIMUM needed to go from home to top of string!
//        float pos2pulse = (offset * 1024) / 9.4;
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

        m_bPlaying = true;
        RPDOTimer.start();
        // faultClearTimer.start();
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
            err = m_striker[i].enablePDO(bEnable);
            LOG_LOG("Enabling PDO for motor %i", i);
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


    int strike(uint8_t idCode) {
        for (int i = 1; i < NUM_STRIKERS + NUM_PRESSERS + 1; ++i) {
            if (idCode == i) {
                // LOG_LOG("(idcode: %h) Striking: %i", idCode, i);
                m_striker[i].strike();
                //(pInstance->pPresserCallBack)(8, 400);
            }
        }
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


    float all_Trajs[15][200]; //CHANGE FOR MORE TRAJS
    float curr_point[15];

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
        auto id = arg->id - COB_ID_SDO_SC;
        if (id > 0 && id < NUM_MOTORS + 1) {
            //LOG_LOG("controller %i, if statement 1", id);
            pInstance->m_striker[id].setRxMsg(*arg);
        }

        id = arg->id - COB_ID_TPDO3;
        if (id > 0 && id < NUM_MOTORS + 1) {
            //LOG_LOG("controller %i, if statement 2", id);
            pInstance->m_striker[id].PDO_processMsg(*arg);
        }

        id = arg->id - COB_ID_EMCY;
        if (id > 0 && id < NUM_MOTORS + 1) {
            //LOG_LOG("controller %i, if statement 3", id);
            pInstance->m_striker[id].handleEMCYMsg(*arg);
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
                Serial.println("HERE: TRAJ COUNT IS ");
                Serial.println(pInstance->m_traj.count());

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
        Serial.println("------------------");
        Serial.print("Index: ");
        Serial.println(idx);
        Serial.print("Traj Point: ");
        for (int i = 0; i < NUM_MOTORS; ++i) {

                Serial.print(point[i]);
                Serial.print(" ");
        }
        Serial.println(" ");


        bool run_bot = true; //false turns off motor, true turns on


        idx += 1;
        if (run_bot){
                // drive actuators here...
                for (int i = 1; i < NUM_MOTORS + 1; ++i)
                pInstance->m_striker[i].rotate(point[i - 1]);
        }

        // Set sendRequest flag if total trajectory time is less than the buffer time.
        //pInstance->m_bSendDataRequest = (pInstance->m_traj.count() * PDO_RATE / 1000.f) < BUFFER_TIME;
        pInstance->m_currentPoint = point;
    }

    // static void clearFaultTimerIRQHandler() {
    //     for (int i = 1; i < NUM_STRIKERS + 1; ++i) {
    //         pInstance->m_striker[i].checkAndRecover();
    //     }
    // }
};

StrikerController* StrikerController::pInstance = nullptr;
#endif // STRIKERCONTROLLER_H
