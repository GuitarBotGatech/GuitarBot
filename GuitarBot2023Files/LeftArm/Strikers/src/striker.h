//
// Created by Raghavasimhan Sankaranarayanan on 03/30/22.
//

#ifndef STRIKER_H
#define STRIKER_H

#include "def.h"
#include "epos4/epos4.h"
#include "util.h"
#include "ErrorDef.h"

class Striker {
public:
    using strikerFunctionCallbackType = int (Striker::*)(int);
    int (Striker::* pPresserCallBackPointer)(int) = &Striker::press;
    Striker* presserPointer = nullptr;

    enum class Command {
        Normal,
        Tremolo,
        StopTremolo,
        Restart,
        Quit,
        Choreo
    };


    ~Striker() {
        reset();
    }


    Error_t init(int iNodeId, MotorSpec spec) {
        LOG_LOG("%i", iNodeId);
        int err = epos.init(iNodeId, spec, kStrikerDirection[1], 2000);
        if (err != 0) {
            LOG_ERROR("Epos init failed for node id: %i", iNodeId);
            return kSetValueError;
        }



        m_iCurrentIdx = kTotalPoints;
        m_mode = Command::Restart;
//        if (spec==EC45) {
//            LOG_LOG("Start Homing");
//            Error_t e = home(iNodeId);
//            if (e != kNoError) return e;
//        }
//        if (spec==EC20) {
//            LOG_LOG("Start Homing");
//            Error_t e = home(iNodeId);
//            if (e != kNoError) return e;
//        }
        stopStrike();

        m_bInitialized = true;
//        Serial.println(m_afTraj[0]);
//        Serial.println(m_afTraj[1]);
//        Serial.println(m_afTraj[2]);
//        Serial.println(m_afTraj[3]);

        LOG_LOG("init passed for %i", iNodeId);

        return kNoError;
    }
    float getPosition(){
        return epos.getCurrentPosition_deg();
    }
    float getPosition_ticks(){
        return epos.getCurrentPosition_ticks();
    }

    void rotate(int pos){
        epos.PDO_setPosition(pos);
    }


    void reset() {
        epos.reset();
        stopStrike();
        m_bInitialized = false;
    }
    bool homingStatus(){
        return epos.getHomingStatus() == InProgress;
    }

    Error_t startHome(int iNodeID) {
//        int err = epos.SetHomePosition(0);
//        if (err != 0) return kSetValueError;
//        return prepToGoHome();
        // Added Homing compatible w/ epos
        int err = epos.setOpMode(OpMode::Homing, HomingMethod::CurrentThresholdNegative);
        if( iNodeID == 2 || iNodeID == 3 || iNodeID == 6 || iNodeID > 6){
            //LOG_LOG("Passed");
            err = epos.setHomingMethod(HomingMethod::CurrentThresholdPositive);
        }
        if(iNodeID > 12){
            err = epos.setHomingMethod(HomingMethod::CurrentThresholdNegative);
        }
        //CHANGE ME
        //err = epos.setHomingMethod(HomingMethod::CurrentThresholdPositive);


        if (err != 0) {
            LOG_ERROR("setOpMode");
            return kSetValueError;
        }

        err = epos.setEnable();
        if (err != 0) {
            LOG_ERROR("setEnable");
            return kSetValueError;
        }

        err = epos.startHoming();
        if (err != 0) {
            LOG_ERROR("startHoming");
            return kSetValueError;
        }

        return kNoError;
    }

    Error_t home(int iNodeID) {
//        int err = epos.SetHomePosition(0);
//        if (err != 0) return kSetValueError;
//        return prepToGoHome();
        // Added Homing compatible w/ epos
        //CHANGE ME
        //int err = epos.setOpMode(OpMode::Homing, HomingMethod::CurrentThresholdNegative);
        int err = epos.setOpMode(OpMode::Homing, HomingMethod::CurrentThresholdPositive);
        if( iNodeID == 2 || iNodeID == 3 || iNodeID == 6 || iNodeID > 6){
            //LOG_LOG("Passed");
            err = epos.setHomingMethod(HomingMethod::CurrentThresholdPositive);
        }
        if (err != 0) {
            LOG_ERROR("setOpMode");
            return kSetValueError;
        }

        err = epos.setEnable();
        if (err != 0) {
            LOG_ERROR("setEnable");
            return kSetValueError;
        }

        err = epos.startHoming();
        if (err != 0) {
            LOG_ERROR("startHoming");
            return kSetValueError;
        }

        int ii = 0;
        bool isHoming = true;
        while (isHoming) {
            isHoming = (epos.getHomingStatus() == InProgress);
            delay(50);
//            int32_t pos = epos.getEncoderPosition();
//            Serial.println(pos);

            if (ii++ > 200) break;
        }

        if (epos.getHomingStatus() == Completed) LOG_LOG("Homing complete");
        delay(500);

        return kNoError;
    }
    Error_t testMove(int32_t pos ){
        int err = epos.moveToPosition(pos, false);
        if(err != 0){
            LOG_ERROR("SDO move error");
            return kSetValueError;
        }
        return kNoError;
    }



    void setPresserPointer(Striker* p) {
        presserPointer = p;
    }

//    void setPresserCallback(PresserCallbackType callback) {
//        pPresserCallback = callback;
//    }
//
//    void executePress(uint8_t buttonId, int force) {
//        if (pPresserCallback)
//            controllerInstance->pPresserCallback(buttonId, force);
//    }

    Error_t prepToGoHome() {
        m_mode = Command::Restart;
        Error_t err = generateTraj(0);
        m_iCurrentIdx = 0;
        return err;
    }

    // Prepare and return true if should striker, false if shouldn't strike
    bool prepare(Command mode, int midiVelocity, uint8_t channelPressure) {
        if (!m_bInitialized) return false;

        // If current mode is tremolo
        // If incoming mode is tremolo, dont do anything
        // if incoming mode is different, first stop tremolo
        if (m_mode == Striker::Command::Tremolo) {
            // If mode is already Tremolo, don't generate new traj
            if (mode == m_mode) return false;
            else stopTremolo();
        }

        m_mode = mode;

        if (m_mode == Command::StopTremolo || (m_mode == Command::Tremolo && midiVelocity == 0)) {
            stopTremolo();
            return false;
        }

        if (m_iCurrentIdx <= m_iEndIdx) {
            LOG_WARN("Command arrived early. CurrentIdx: %i, endIdx: %i", m_iCurrentIdx, m_iEndIdx);
            // If a new command arrives, quick stop current motion and start new trajectory
            int e = epos.PDO_quickStop();
            if (e != 0) {
                LOG_ERROR("PDO Quick stop command failed");
            }
        }

        Error_t err = generateTraj(midiVelocity, channelPressure);
        if (err != 0) {
            LOG_ERROR("Error preparing striker %i with mode %i and velocity %i", epos.getNodeId(), mode, midiVelocity);
            return false;
        }

        return true;
    }
    int press(int command){
        //Non PDO Pressing
        int err = epos.setTargetTorque(command);
        if (err != 0){
            LOG_ERROR("Error setting torque");
        }
    }

    uint8_t getNodeId() const {
        if (!m_bInitialized) return 0;
        return epos.getNodeId();
    }

    void update() {
        if (!m_bInitialized) return;

        // Check if device is in fault state
        if (!epos.isDeviceReady()) {
            stopStrike();
            return;
        }

        // if (m_iCurrentIdx == 0 || m_iCurrentIdx == kTotalPoints - 1) {
        //     LOG_LOG("%i", epos.getCurrentPosition_ticks());
        // }

        if (m_mode == Command::Tremolo) {
            if (m_iCurrentIdx > m_iEndIdx) { // Keep looping after trajectory ends until stop tremolo is called
                m_iCurrentIdx = m_iTremoloStartIdx;
            }
        } else {
            if (m_iCurrentIdx > m_iEndIdx) {    // Trajectory complete
                m_iCurrentIdx = MAX_TRAJ_POINTS;
//                Serial.print(epos.getNodeId());
//                Serial.print(" reached an end at");
//                Serial.print(m_iCurrentIdx);
//                Serial.print(" ");
//                Serial.println(epos.angle2Pos(m_afTraj[m_iCurrentIdx], false));
                //Serial.println(epos.getCurrentPosition_deg(), false);
                epos.PDO_rotate(epos.getCurrentPosition_deg(), false);  // keep sending last postion to avoid 0x8250 - RPDO Timeout Error

                return;
            }
        }

//         Serial.print(epos.getNodeId());
//         Serial.print(" ");
//         Serial.print(m_iCurrentIdx);
//         Serial.print(" ");
//         Serial.print(m_afTraj[m_iCurrentIdx]);
//         Serial.print(" ");
//         Serial.println(epos.angle2Pos(m_afTraj[m_iCurrentIdx], false));

//         if(epos.angle2Pos(m_afTraj[m_iCurrentIdx], false) < -2147483646 || epos.angle2Pos(m_afTraj[m_iCurrentIdx], false) > 2147483646) {
//             Serial.println("Overflow, skipping");
//             ++m_iCurrentIdx;
//             return;
//         }

        int err = epos.PDO_rotate(m_afTraj[m_iCurrentIdx], false);



//        if(m_iCurrentIdx == 99 && presserPointer != nullptr){
//            Serial.println("End Reached");
//            presserPointer->press(400);
//              //Causes RPDO timeout
//        }
        ++m_iCurrentIdx;
    }

    Error_t setRxMsg(can_message_t& msg) {
        int err = epos.setRxMsg(msg);
        if (err != 0) return kSetValueError;
        return kNoError;
    }

    Error_t PDO_processMsg(can_message_t& msg) {
        int err = epos.PDO_processMsg(msg);
        if (err != 0) return kSetValueError;
        return kNoError;
    }

    void handleEMCYMsg(can_message_t& msg) {
        epos.handleEMCYMsg(msg);
    }
    Error_t enablePDOEC20(bool bEnable) {
        int err = 0;

        if (bEnable) {
            err = epos.setOpMode(OpMode::CyclicSyncPosition);
            err = epos.setNMTState(NMTState::Operational);
        } else {
            err = epos.setNMTState(NMTState::PreOperational);
        }

        if (err != 0) return kSetValueError;

        return kNoError;
    }



    Error_t enablePDO(bool bEnable) {
        int err = 0;

        if (bEnable) {
            err = epos.setOpMode(OpMode::CyclicSyncPosition);
            err = epos.setNMTState(NMTState::Operational);
        } else {
            err = epos.setNMTState(NMTState::PreOperational);
        }


        if (err != 0) return kSetValueError;

        return kNoError;
    }

    Error_t enable(bool bEnable) {
        int err = epos.setEnable(bEnable);
        if (err != 0) return kSetValueError;
        return kNoError;
    }

    void strike() {
        m_iCurrentIdx = 0;  // This will trigger the update
    }

    void stopStrike() {
        m_iCurrentIdx = MAX_TRAJ_POINTS;   // This will stop the trajectory update
        Util::fill(m_afTraj, MAX_TRAJ_POINTS, 0);  // reset trajectory array
    }

    void shutdown() {
        reset();
    }

    void startTremolo(uint8_t midiVelocity) {
        m_mode = Command::Tremolo;
        m_iCurrentIdx = MAX_TRAJ_POINTS;
        generateTraj(midiVelocity);
        //strike();
    }

    void stopTremolo() {
        m_mode = Command::Normal;
        stopStrike();
        m_iTremoloStartIdx = 0;
        m_iEndIdx = MAX_TRAJ_POINTS;
    }

    void checkAndRecover() {
        // This function uses SDO (very expensive). 
        // Dont do anything if device is ready.
        if (epos.isDeviceReady()) return;

        LOG_LOG("Recovering node %i from error %h", epos.getNodeId(), epos.getDeviceError());
        Error_t err = enablePDO(false);
        if (err != kNoError) {
            LOG_ERROR("Node %i: Cannot Disable PDO", epos.getNodeId());
            return;
        }

        int e = epos.clearFault();
        if (e != 0) {
            LOG_ERROR("Node %i: Cannot clear fault", epos.getNodeId());
            return;
        }

        err = enablePDO(true);
        if (err != kNoError) {
            LOG_ERROR("Node %i: Cannot Enable PDO", epos.getNodeId());
            return;
        }

        err = enable(true);
        if (err != kNoError) {
            LOG_ERROR("Node %i: Cannot Enable Device", epos.getNodeId());
            return;
        }
    }


private:
    Epos4 epos;
    //StrikerController* pInstance;


    bool m_bInitialized = false;
    Command m_mode = Command::Restart;
    static const int kNumPointsForHit = NUM_POINTS_IN_TRAJ_FOR_HIT * PDO_RATE;
    static const int kNumPointsForUp = NUM_POINTS_IN_TRAJ_FOR_UP * PDO_RATE;
    static const int kTotalPoints = kNumPointsForHit + kNumPointsForUp;   // 65ms total with 1ms cycle time -> 65/1
    int m_iCurrentIdx;
    float m_afTraj[MAX_TRAJ_POINTS];
    int m_iEndIdx = kTotalPoints;
//    PresserCallbackType pPresserCallback = nullptr;
 //   Striker* controllerInstance = nullptr;



    // Tremolo
    int m_iTremoloStartIdx = 0;
    int m_iTremoloEndIdx = 0;

    Error_t generateTraj(int midiVelocity, uint8_t channelPressure = 0) {
        float q0, qf;

        switch (m_mode) {
        case Command::Restart:
        case Command::StopTremolo:
            q0 = epos.getCurrentPosition_deg();;
            qf = HOME_POSITION;
            Util::interpWithBlend(q0, qf, kTotalPoints, 0.25, m_afTraj);
            m_iEndIdx = kTotalPoints - 1;
            return kNoError;

        case Command::Quit:
            LOG_ERROR("Cannot generate trajectory for mode: {}", (int) m_mode);
            return kTrajectoryError;

        case Command::Choreo:
            q0 = epos.getCurrentPosition_deg();
            qf = choreoPositionMap(channelPressure);
            m_iEndIdx = choreoTimeMap(midiVelocity) - 1;
            // char msg[64];
            // sprintf(msg, "q0: %i, qf: %i, endIdx: %i", (int) (q0 * 100), (int) (qf * 100), m_iEndIdx);
            // Serial.println(msg);
            Util::interpWithBlend(q0, qf, m_iEndIdx + 1, 0.49, m_afTraj);

            return kNoError;

        default:
            break;
        }

        float fInitialPosition_deg, fStrikePosition_deg, fBlend;
        int iNumPtsForHit, iNumPtsForUp;

        velocityMap(midiVelocity, fInitialPosition_deg, fStrikePosition_deg, fBlend);
        timeMap(midiVelocity, iNumPtsForHit, iNumPtsForUp);




        // go to initial position
//        q0 = epos.getCurrentPosition_deg();
//        qf = fInitialPosition_deg;
//        Util::interpWithBlend(q0, q0, 50, 0.25, m_afTraj);


//      //Move to next fret
        q0 = epos.getCurrentPosition_deg();
//        Serial.print("The rotation is ");
//        Serial.println(epos.angle2Pos(midiVelocity, false));
        //best movement traj
//        Util::interpWithBlend(q0, midiVelocity, 70, fBlend, m_afTraj);
        Util::interpWithBlend(q0, midiVelocity, 20, .05, m_afTraj);

//        // upward movement
//        q0 = fStrikePosition_deg;
//        qf = (m_mode == Command::Tremolo) ? fInitialPosition_deg : HOME_POSITION;
//        float blend = (m_mode == Command::Tremolo) ? fBlend : 0.25;
//        Util::interpWithBlend(q0, qf, iNumPtsForUp, blend, &m_afTraj[iNumPtsForHit]);
        m_iEndIdx = kTotalPoints - 1;

        return kNoError;
    }

    float choreoPositionMap(uint8_t pressure) {
        pressure = min(MAX_STRIKER_ANGLE_DEG, pressure);
        return (float) pressure;
    }

    int choreoTimeMap(uint8_t midiVelocity) {
        // The higher the velocity, the faster it should reach target
        float m = log2(max(2, midiVelocity)) * 5.f;
        int b = -100;

        return min(MAX_TRAJ_POINTS, (int) round((MAX_TRAJ_POINTS / m)) + b);
    }

    void timeMap(int midiVelocity, int& iNumPointsForHit, int& iNumPointsForUp) {
        iNumPointsForHit = kNumPointsForHit;
        iNumPointsForUp = kNumPointsForUp;

        if (m_mode == Command::Tremolo) {
            midiVelocity = getCorrectedVelocity(midiVelocity);

            if (midiVelocity == 0)
                return;

            float m = midiVelocity * 0.08;
            int b = 10;
            iNumPointsForHit = (int) round(kNumPointsForHit / m) + b;
            m_iTremoloStartIdx = kNumPointsForUp;
            m_iTremoloEndIdx = min(kTotalPoints, m_iTremoloStartIdx + (2 * iNumPointsForHit));   // Hit and up are symmetric for tremolo
        }
    }

    void velocityMap(int midiVelocity, float& fInitialPosition, float& fStrikePosition, float& fBlend) {
        /*
        fInitialPosition = midiVelocity * 0.3 + 10;
        fStrikePosition = -midiVelocity * 0.5;
        fBlend = 8.f / max(16, midiVelocity);
        */

        midiVelocity = getCorrectedVelocity(midiVelocity);

        // Mapping from velocity to position and blend
        fInitialPosition = midiVelocity * 0.3 + 10;
        fStrikePosition = -midiVelocity * 0.5;
        // best
        // fBlend = 8.f / 70;
        fBlend = 8.f / 180;

        if (m_mode == Command::Tremolo) {
            fInitialPosition = midiVelocity * 0.1 + 10;
            fStrikePosition = -midiVelocity * 0.3;
        }
    }

    uint8_t getCorrectedVelocity(int midiVelocity) {
        // Correction for strike command arriving faster than expected
        float timeCorrection = min(1.f, m_iCurrentIdx / (1.f * kTotalPoints));
        return min(127, midiVelocity * sq(timeCorrection));
    }



};

#endif // STRIKER_H
