//
// Created by Raghavasimhan Sankaranarayanan on 11/26/21.
// 
// Maxon EPOS4 library for STM32F7 based Robotis OpenCR1.0 controller board.
// Based on libEPOS_STM32 Liyu Wang, SJTU repo for epos2
//
// Refer: EPOS4 Firmware Specification (2021-04)

#pragma once 

#include <Arduino.h>
#include "epos4_def.h"
#include <CAN.h>
#include "../logger.h"
#include "../ErrorDef.h"

#define MAX_FOLLOW_ERROR 40000
#define CALLBACK_ENC_THRESHOLD 5
#define PDO_RATE 5 // ms

/*
    *  Reference: canTxRxNessage Example from OpenCR1.0 Arduino Library
    *
    *  typedef struct
    *  {
    *    uint32_t id      : Identifier of received message
    *    uint32_t length  : Length of received message data
    *    uint8_t  data[8] : Data of received message
    *    uint8_t  format  : Type of ID
    *  } can_message_t;
    *
    * BAUDRATE :
    *   CAN_BAUD_125K
    *   CAN_BAUD_250K
    *   CAN_BAUD_500K
    *   CAN_BAUD_1000K
    *
    * FORMAT :
    *   CAN_STD_FORMAT
    *   CAN_EXT_FORMAT
*/

class Epos4 {
public:
    ~Epos4() = default;

    // Timeout of 0 means no timeout
    int init(int iNodeID = 1, MotorSpec spec = EC45_Slider, bool inverted = false, unsigned long timeout_ms = 0);
    void reset();

    int configEC20();
    int configEC45();
    int configEC60();

    // Checks
    _WORD firmwareVersion();

    int readObj(_WORD index, _BYTE subIndex, _DWORD* answer);
    int writeObj(_WORD index, _BYTE subIndex, _DWORD param);

    // Read
    int readStatusWord(_WORD* status);
    int readITP(uint8_t* time, int8_t* unit);
    // Refer: FW Spec 6.2.103
    int getActualPosition(int32_t* piPos);

    // Getter for the stored encoder value from PDO_msg
    int32_t getEncoderPosition() {
        return m_iEncoderPosition;
    }

    HomingStatus getHomingStatus();

    // Refer: FW Spec 6.2.101
    int getOpMode(OpMode* opMode = nullptr, char* sOpMode = nullptr);
    char* getOpModeString(OpMode mode) const;

    // Write
    int setOpMode(OpMode opMode, uint8_t uiInterpolationTime = PDO_RATE, int8_t iInterpolationIndex = -3, HomingMethod homingMethod = CurrentThresholdNegative);

    int setControlWord(_WORD cw);
    int shutdown();
    int setEnable(bool bEnable = true);
    int setProfile(_DWORD vel = 1000, _DWORD acc = 10000);
    int setHomingMethod(HomingMethod method);
    int setHomingCurrentThreshold(_WORD currentThreshold);
    int moveToPosition(int32_t pos, bool bWait = false);
    int rotate(float fAngle, bool bRadian = true, bool bWait = true);
    int moveWithVelocity(int32_t velocity);
    int setFollowErrorWindow(_DWORD errWindow);
    int quickStop();
    int startHoming();
    int setTargetTorque(int16_t torque);
    int SetHomePosition(int32_t iPos);
    int SetHomeOffset(int32_t iPos);
    int SetHomeSpeedSwitch(int32_t iVel);


    int clearFault();

    int setCurrentControlParameters();
    int setCurrentControlParameters_EC20();
    int setCurrentControlParameters_EC60();
    int setPositionControlParameters();
    int setPositionControlParameters_EC20();
    int setPositionControlParameters_EC60();
    // Motor Data
    int setNominalCurrent(_DWORD current);
    int setOutputCurrentLimit(_DWORD currentLimit);
    int setNumPolePairs(_BYTE polePairs);
    int setThermalTimeConstantWinding(_WORD ttconstWinding);
    int setMotorTorqueConstant(_DWORD torqueConst);

    // Encoder
    int setEncoderNumPulses(_DWORD pulses);
    int setEncoderType(_WORD type);

    // Refer App notes -> 5.5
    int setNMTState(NMTState nmtState);

    // All PDO functions. Will work only with NMTState -> Operational

    // Configure mapping for each PDO
    int PDO_config();
    int PDO_configRPDO3();
    int PDO_configRPDO4();
    // Set Control word through PDO. Uses RPDO 1 - object 1
    int PDO_setControlWord(_WORD cw);
    int PDO_quickStop();
    // Process incoming TPDO Messages from EPOS4 device
    int PDO_processMsg(can_message_t& msg);
    // Set target position through PDO. Uses RPDO 3 - object 2
    int PDO_setPosition(int32_t position);
    int PDO_rotate(float fAngle, bool bRadian = true);
    // Set target velocity through PDO. Uses RPDO 4 - object 2
    int PDO_setVelocity(int32_t iVelocity);

    int setRxMsg(can_message_t& msg);
    void handleEMCYMsg(can_message_t& msg);

    // Getters
    uint8_t getNodeId() const {
        return m_uiNodeID;
    }

    int getEncoderResolution() const {
        return m_iEncoderResolution;
    }

    bool isEncoderInverted() const {
        return m_iDirMultiplier == -1;
    }

    MotorSpec getMotorSpec() const {
        return m_motorSpec;
    }

    int getCurrentPosition_ticks() const {
        return m_iEncoderPosition;
    }

    float getCurrentPosition_deg() const {
        return m_iEncoderPosition * 360.f / (m_iEncoderResolution);
    }

    int32_t angle2Pos(float fAngle, bool bRadian);

    int getDeviceError() const {
        return m_uiError;
    }

    bool isDeviceReady() const {
        // if (m_uiError != 0) LOG_WARN("Node %i: Error (%h): %s", m_uiNodeID, m_uiError, getDeviceError(m_uiError));
        return m_uiError == 0x0;
    }

private:
    uint8_t m_uiNodeID = 0; // 0 is an invalid nodeId
    int m_iDirMultiplier = 1;
    _DWORD m_uiError = 0x0;    ///< EPOS global error status

    unsigned long m_ulTimeout_ms;

    NMTState m_currentNMTState;
    OpMode m_iCurrentMode;
    _WORD m_uiCurrentCtrlWord;
    _WORD m_uiCurrentStatusWord;

    MotorSpec m_motorSpec = EC45_Slider;
    int32_t m_iEncoderPosition;
    int m_iEncoderResolution = EC45_ENC_RES_PLUCKER;

    can_message_t m_txMsg;
    can_message_t m_rxMsg;

    volatile bool m_bSDOBusy = true;
    bool m_bCANRxReady = false;
    bool m_bCANTxReady = false;
    bool m_bIsPDO = false;

    volatile bool m_bFault = false;

    // write
    // Interpolation time period
    int setITP(uint8_t value = 1, int8_t index = -3);

    static String getDeviceError(int errorCode) {
        switch (errorCode) {
        case 0x0000:
            return "No Error";
        case 0x1000:
            return "Generic Error";
        case 0x1080:
        case 0x1081:
        case 0x1082:
        case 0x1083:
            return "Generic Init Error";
        case 0x1090:
            return "Firmware Compatibility Error";
        case 0x2310:
            return "Overcurrent Error";
        case 0x2320:
            return "Power stage protection Error";
        case 0x3210:
            return "Overvoltage Error";
        case 0x3220:
            return "Undervoltage Error";
        case 0x4210:
            return "Thermal overload Error";
        case 0x4380:
            return "Thermal motor overload Error";
        case 0x5113:
            return "Logic supply voltage too low Error";
        case 0x5280:
            return "Hardware defect Error";
        case 0x5281:
            return "Hardware incompatibility Error";
        case 0x5480:
        case 0x5481:
        case 0x5482:
        case 0x5483:
            return "Hardware Error";
        case 0x6080:
            return "Sign of life Error";
        case 0x6081:
            return "Extension 1 watchdog Error";
        case 0x6180:
        case 0x6181:
        case 0x6182:
        case 0x6183:
        case 0x6184:
        case 0x6185:
        case 0x6186:
        case 0x6187:
        case 0x6188:
        case 0x6189:
            return "Internal software Error";
        case 0x6320:
            return "Software parameter Error";
        case 0x6380:
            return "Persistent parameter corrupt Error";
        case 0x7320:
            return "Position sensor Error";
        case 0x7380:
            return "Position sensor breach Error";
        case 0x7381:
            return "Position sensor resolution Error";
        case 0x7382:
            return "Position sensor index Error";
        case 0x7388:
            return "Hall sensor Error";
        case 0x7389:
            return "Hall sensor not found Error";
        case 0x738A:
            return "Hall angle detection Error";
        case 0x738C:
            return "SSI sensor Error";
        case 0x7390:
            return "Missing main sensor Error";
        case 0x7391:
            return "Missing commutation sensor Error";
        case 0x7392:
            return "Main sensor direction Error";
        case 0x8110:
            return "CAN overrun Error (object lost)";
        case 0x8111:
            return "CAN overrun Error";
        case 0x8120:
            return "CAN passive mode Error";
        case 0x8130:
            return "CAN heartbeat Error";
        case 0x8150:
            return "CAN PDO COB-ID collision";
        case 0x8180:
            return "EtherCAT communication Error";
        case 0x8181:
            return "EtherCAT initialization Error";
        case 0x8182:
            return "EtherCAT Rx queue overflow";
        case 0x8183:
            return "EtherCAT communication Error (internal)";
        case 0x81FD:
            return "CAN bus turned off";
        case 0x81FE:
            return "CAN Rx queue overflow";
        case 0x81FF:
            return "CAN Tx queue overflow";
        case 0x8210:
            return "CAN PDO length Error";
        case 0x8250:
            return "RPDO timeout";
        case 0x8280:
            return "EtherCAT PDO communication Error";
        case 0x8281:
            return "EtherCAT SDO communication Error";
        case 0x8611:
            return "Following Error";
        case 0x8A80:
            return "Negative limit switch Error";
        case 0x8A81:
            return "Positive limit switch Error";
        case 0x8A82:
            return "Software position limit Error";
        case 0x8A88:
            return "STO Error";
        case 0xFF01:
            return "System overloaded Error";
        case 0xFF02:
            return "Watchdof Error";
        case 0xFF0B:
            return "System peak overloaded Error";
        case 0xFF10:
            return "Controller gain Error";
        case 0xFF12:
            return "Auto tuning current limit Error";
        case 0xFF13:
            return "Auto tuning identification current Error";
        case 0xFF14:
            return "Auto tuning data sampling Error";
        case 0xFF15:
            return "Auto tuning sample mismatch Error";
        case 0xFF16:
            return "Auto tuning parameter Error";
        case 0xFF17:
            return "Auto tuning amplitude mismatch Error";
        case 0xFF18:
            return "Auto tuning period length Error";
        case 0xFF19:
            return "Auto tuning timeout Error";
        case 0xFF20:
            return "Auto tuning standstill Error";
        case 0xFF21:
            return "Auto tuning torque invalid Error";
        default:
            return "Unknown Error";
        }
    }
};