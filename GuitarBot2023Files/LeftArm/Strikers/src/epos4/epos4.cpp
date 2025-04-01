//
// Created by Raghavasimhan Sankaranarayanan on 11/26/21.
// 

#include "epos4.h"

int Epos4::init(int iNodeID, MotorSpec spec, bool inverted, unsigned long timeout_ms) {
    m_uiNodeID = iNodeID;
    m_motorSpec = spec;
    m_ulTimeout_ms = timeout_ms;

    if (inverted) m_iDirMultiplier = -1;
    m_currentNMTState = PreOperational;

    int err;
    err = setControlWord(0x87);
    if (err < 0) {
        LOG_ERROR("control word send");
        return err;
    }

    err = shutdown();

    switch (spec) {
    case EC20:
        m_iEncoderResolution = EC20_ENC_RES;
        err = configEC20();
        break;
    case EC45_StrummerSlider:
        m_iEncoderResolution = EC45_ENC_RES_SLIDER;
        err = configEC45Strummer_Slider();
        break;

    case EC45_Slider:
        m_iEncoderResolution = EC45_ENC_RES_SLIDER;
        err = configEC45();
        break;
    case EC45_StrummerPicker:
            m_iEncoderResolution = EC45_ENC_RES_SLIDER;
            err = configEC45Strummer_Picker();
            break;
    case EC45_Plucker_1024:
        m_iEncoderResolution = EC45_ENC_RES_PLUCKER;
        err = configEC45Pickers();
        break;
    case EC45_Plucker_2048:
        m_iEncoderResolution = EC45_ENC_RES_SLIDER;
        err = configEC45Pickers();
        break;
    case EC60:
        m_iEncoderResolution = EC60_ENC_RES;
        err = configEC60();
        break;
    }

    if (err < 0) {
        LOG_ERROR("Motor Config Error");
        return err;
    }

    err = setFollowErrorWindow(MAX_FOLLOW_ERROR);
    if (err < 0) {
        LOG_ERROR("set Follow Error Window Error");
        return err;
    }

    err = PDO_config();
    if (err < 0) {
        LOG_ERROR("PDO Config Error");
        return err;
    }

    err = setNMTState(m_currentNMTState);
    if (err != 0) {
        LOG_ERROR("setNMTState");
        return err;
    }

    _WORD stat = 0x0;
    err = readStatusWord(&stat);
    if (err < 0) {
        LOG_ERROR("status word err");
        return err;
    }
    LOG_LOG("Status (%i): %h", (int) m_uiNodeID, (int) stat);

    // auto fw = firmwareVersion();
    // LOG_LOG("node %i fw version: %h", m_uiNodeID, fw);
    return 0;
}

void Epos4::reset() {
    setNMTState(NMTState::PreOperational);
    setEnable(false);
}
int Epos4::configEC20() {
    int err;
    // LOG_LOG("Configuring EC20");
    err = setNominalCurrent(1310);
    if (err != 0) {
        LOG_ERROR("setNominalCurrent");
        return err;
    }
    
    err = setOutputCurrentLimit(1200);
    if (err != 0) {
        LOG_ERROR("setOutputCurrentLimit");
        return err;
    }

    err = setMotorTorqueConstant(5880); // uNm/A
    if (err != 0) {
        LOG_ERROR("setMotorTorqueConstant");
        return err;
    }

    err = setThermalTimeConstantWinding(17); // x 0.1 s
    if (err != 0) {
        LOG_ERROR("setThermalTimeConstantWinding");
        return err;
    }

    err = setNumPolePairs(4);
    if (err != 0) {
        LOG_ERROR("setNumPolePairs");
        return err;
    }

    // Encoder
    err = setEncoderNumPulses(m_iEncoderResolution);
    if (err != 0) {
        LOG_ERROR("setEncoderNumPulses");
        return err;
    }
    // refer FW Spec 6.2.56.2 for type
    err = setEncoderType(0x0);
    if (err != 0) {
        LOG_ERROR("setEncoderType");
        return err;
    }

    err = setCurrentControlParameters_EC20();
    if (err != 0) {
        LOG_ERROR("setCurrentControlParameters");
        return err;
    }

    err = setPositionControlParameters_EC20();
    if (err != 0) {
        LOG_ERROR("setPositionControlParameters");
        return err;
    }

    return 0;
}
int Epos4::configEC45() {
    int err;
    // LOG_LOG("Configuring EC45");

    err = setNominalCurrent(3210);
    if (err != 0) {
        LOG_ERROR("setNominalCurrent");
        return err;
    }

    err = setOutputCurrentLimit(5000);
    if (err != 0) {
        LOG_ERROR("setOutputCurrentLimit");
        return err;
    }

    err = setMotorTorqueConstant(36900); // uNm/A
    if (err != 0) {
        LOG_ERROR("setMotorTorqueConstant");
        return err;
    }

    err = setThermalTimeConstantWinding(296); // x 0.1 s
    if (err != 0) {
        LOG_ERROR("setThermalTimeConstantWinding");
        return err;
    }

    err = setNumPolePairs(8);
    if (err != 0) {
        LOG_ERROR("setNumPolePairs");
        return err;
    }

    // Encoder
    err = setEncoderNumPulses(m_iEncoderResolution);
    if (err != 0) {
        LOG_ERROR("setEncoderNumPulses");
        return err;
    }
    // refer FW Spec 6.2.56.2 for type
    err = setEncoderType(0x0);
    if (err != 0) {
        LOG_ERROR("setEncoderType");
        return err;
    }

    err = setCurrentControlParameters();
    if (err != 0) {
        LOG_ERROR("setCurrentControlParameters");
        return err;
    }

    err = setPositionControlParameters();
    if (err != 0) {
        LOG_ERROR("setPositionControlParameters");
        return err;
    }

    return 0;
}

int Epos4::configEC60() {
    int err;
    // LOG_LOG("Configuring EC60");

    err = setNominalCurrent(5470);
    if (err != 0) {
        LOG_ERROR("setNominalCurrent");
        return err;
    }

    err = setOutputCurrentLimit(30000);
    if (err != 0) {
        LOG_ERROR("setOutputCurrentLimit");
        return err;
    }

    err = setMotorTorqueConstant(0); // 52500 uNm/A
    if (err != 0) {
        LOG_ERROR("setMotorTorqueConstant");
        return err;
    }

    err = setThermalTimeConstantWinding(414); // x 0.1 s
    if (err != 0) {
        LOG_ERROR("setThermalTimeConstantWinding");
        return err;
    }

    err = setNumPolePairs(7);
    if (err != 0) {
        LOG_ERROR("setNumPolePairs");
        return err;
    }

    // Encoder
    err = setEncoderNumPulses(m_iEncoderResolution);
    if (err != 0) {
        LOG_ERROR("setEncoderNumPulses");
        return err;
    }
    // refer FW Spec 6.2.56.2 for type
    err = setEncoderType(0x0);
    if (err != 0) {
        LOG_ERROR("setEncoderType");
        return err;
    }

    err = setCurrentControlParameters_EC60();
    if (err != 0) {
        LOG_ERROR("setCurrentControlParameters");
        return err;
    }

    err = setPositionControlParameters_EC60();
    if (err != 0) {
        LOG_ERROR("setPositionControlParameters");
        return err;
    }

    return 0;
}

int Epos4::configEC45Strummer_Slider() {
    int err;
    // LOG_LOG("Configuring EC45");

    err = setNominalCurrent(3210);
    if (err != 0) {
        LOG_ERROR("setNominalCurrent");
        return err;
    }

    err = setOutputCurrentLimit(5000);
    if (err != 0) {
        LOG_ERROR("setOutputCurrentLimit");
        return err;
    }

    err = setMotorTorqueConstant(36900); // uNm/A
    if (err != 0) {
        LOG_ERROR("setMotorTorqueConstant");
        return err;
    }

    err = setThermalTimeConstantWinding(296); // x 0.1 s
    if (err != 0) {
        LOG_ERROR("setThermalTimeConstantWinding");
        return err;
    }

    err = setNumPolePairs(8);
    if (err != 0) {
        LOG_ERROR("setNumPolePairs");
        return err;
    }

    // Encoder
    err = setEncoderNumPulses(m_iEncoderResolution);
    if (err != 0) {
        LOG_ERROR("setEncoderNumPulses");
        return err;
    }
    // refer FW Spec 6.2.56.2 for type
    err = setEncoderType(0x0);
    if (err != 0) {
        LOG_ERROR("setEncoderType");
        return err;
    }

    err = setCurrentControlParameters_StrummerSlider();
    if (err != 0) {
        LOG_ERROR("setCurrentControlParameters");
        return err;
    }

    err = setPositionControlParameters_StrummerSlider();
    if (err != 0) {
        LOG_ERROR("setPositionControlParameters");
        return err;
    }

    return 0;
}

int Epos4::configEC45Strummer_Picker() {
    int err;
    // LOG_LOG("Configuring EC45");

    err = setNominalCurrent(3210);
    if (err != 0) {
        LOG_ERROR("setNominalCurrent");
        return err;
    }

    err = setOutputCurrentLimit(5000);
    if (err != 0) {
        LOG_ERROR("setOutputCurrentLimit");
        return err;
    }

    err = setMotorTorqueConstant(36900); // uNm/A
    if (err != 0) {
        LOG_ERROR("setMotorTorqueConstant");
        return err;
    }

    err = setThermalTimeConstantWinding(296); // x 0.1 s
    if (err != 0) {
        LOG_ERROR("setThermalTimeConstantWinding");
        return err;
    }

    err = setNumPolePairs(8);
    if (err != 0) {
        LOG_ERROR("setNumPolePairs");
        return err;
    }

    // Encoder
    err = setEncoderNumPulses(m_iEncoderResolution);
    if (err != 0) {
        LOG_ERROR("setEncoderNumPulses");
        return err;
    }
    // refer FW Spec 6.2.56.2 for type
    err = setEncoderType(0x0);
    if (err != 0) {
        LOG_ERROR("setEncoderType");
        return err;
    }

    err = setCurrentControlParameters_StrummerPicker();
    if (err != 0) {
        LOG_ERROR("setCurrentControlParameters");
        return err;
    }

    err = setPositionControlParameters_StrummerPicker();
    if (err != 0) {
        LOG_ERROR("setPositionControlParameters");
        return err;
    }

    return 0;
}

int Epos4::configEC45Pickers() {
    int err;
    // LOG_LOG("Configuring EC45");

    err = setNominalCurrent(3210);
    if (err != 0) {
        LOG_ERROR("setNominalCurrent");
        return err;
    }

    err = setOutputCurrentLimit(5000);
    if (err != 0) {
        LOG_ERROR("setOutputCurrentLimit");
        return err;
    }

    err = setMotorTorqueConstant(36900); // uNm/A
    if (err != 0) {
        LOG_ERROR("setMotorTorqueConstant");
        return err;
    }

    err = setThermalTimeConstantWinding(296); // x 0.1 s
    if (err != 0) {
        LOG_ERROR("setThermalTimeConstantWinding");
        return err;
    }

    err = setNumPolePairs(8);
    if (err != 0) {
        LOG_ERROR("setNumPolePairs");
        return err;
    }

    // Encoder
    err = setEncoderNumPulses(m_iEncoderResolution);
    if (err != 0) {
        LOG_ERROR("setEncoderNumPulses");
        return err;
    }
    // refer FW Spec 6.2.56.2 for type
    err = setEncoderType(0x0);
    if (err != 0) {
        LOG_ERROR("setEncoderType");
        return err;
    }

    err = setCurrentControlParameters_Pickers();
    if (err != 0) {
        LOG_ERROR("setCurrentControlParameters");
        return err;
    }

    err = setPositionControlParameters_Pickers();
    if (err != 0) {
        LOG_ERROR("setPositionControlParameters");
        return err;
    }

    return 0;
}

int Epos4::readObj(_WORD index, _BYTE subIndex, _DWORD* answer) {
    // block SDO
    m_bSDOBusy = true;

    // EPOS4 Communication Guide (2021-03) -> 3.4
    // EPOS4 Application Notes (2021-03) -> 5.4
    m_txMsg.id = COB_ID_SDO + m_uiNodeID;
    m_txMsg.format = CAN_STD_FORMAT;
    m_txMsg.length = 8;
    m_txMsg.data[0] = 0x40;
    m_txMsg.data[1] = index & 0xFF;
    m_txMsg.data[2] = (index & 0xFF00) >> 8;
    m_txMsg.data[3] = subIndex;
    m_txMsg.data[4] = 0x00;
    m_txMsg.data[5] = 0x00;
    m_txMsg.data[6] = 0x00;
    m_txMsg.data[7] = 0x00;

    if (CanBus.writeMessage(&m_txMsg) != m_txMsg.length) {
        LOG_ERROR("CanBus WriteMessage failed");
        m_bSDOBusy = false;
        return -1;
    }

    auto waitTime = millis();
    while (m_bSDOBusy) {
        // LOG_LOG("sdo busy");
        delay(1);
        if (m_ulTimeout_ms > 0 && ((millis() - waitTime) > m_ulTimeout_ms)) {
            return -2;
        }
    }

    /* check for error code */
    if (m_rxMsg.data[0] == 0x80) {
        m_uiError = (m_rxMsg.data[7] << 24) + (m_rxMsg.data[6] << 16) + (m_rxMsg.data[5] << 8) + m_rxMsg.data[4];
        return -1;
    }

    *answer = (((int32_t) (m_rxMsg.data[7])) << 24) + (((int32_t) (m_rxMsg.data[6])) << 16) + (((int32_t) (m_rxMsg.data[5])) << 8) + (int32_t) (m_rxMsg.data[4]);

    return 0;
}

int Epos4::writeObj(_WORD index, _BYTE subIndex, _DWORD param) {
    // EPOS4 Communication Guide (2021-03) -> 3.4
    // EPOS4 Application Notes (2021-03) -> 5.4
    m_bSDOBusy = true;
    m_txMsg.id = COB_ID_SDO + m_uiNodeID;
    m_txMsg.format = CAN_STD_FORMAT;
    m_txMsg.length = 8;
    m_txMsg.data[0] = 0x22;
    m_txMsg.data[1] = index & 0xFF;
    m_txMsg.data[2] = (index & 0xFF00) >> 8;
    m_txMsg.data[3] = subIndex;
    m_txMsg.data[4] = param & 0xFF;
    m_txMsg.data[5] = (param & 0xFF00) >> 8;
    m_txMsg.data[6] = (param & 0xFF0000) >> 16;
    m_txMsg.data[7] = (param & 0xFF000000) >> 24;
    //LOG_LOG("reached 1");

    int n = CanBus.writeMessage(&m_txMsg);
    if (n != 8) {
        LOG_ERROR("CanBus WriteMessage failed. Wrote %i bytes instead of %i bytes", 8);
        return -1;
    }

    //LOG_LOG("reached 2");

    auto waitTime = millis();
    while (m_bSDOBusy) {
        // LOG_LOG("sdo busy");
        delay(1);
        if (m_ulTimeout_ms > 0 && ((millis() - waitTime) > m_ulTimeout_ms)) {
            return -2;
        }
    }

    /* check for error code */
    if (m_rxMsg.data[0] == 0x80) {
        m_uiError = (m_rxMsg.data[7] << 24) + (m_rxMsg.data[6] << 16) + (m_rxMsg.data[5] << 8) + (m_rxMsg.data[4]);
        LOG_ERROR("Device Error: %h", m_uiError);
        return -1;
    }

    return 0;
}

_WORD Epos4::firmwareVersion() {
    _DWORD answer;

    int n = 0;
    if ((n = readObj(0x1018, 0x03, &answer)) != 0) {
        LOG_ERROR("readObj in readSWversion. Error code: %h", m_uiError);
        return n;
    }

    n = answer >> 0x10;
    return n;
}

int Epos4::readStatusWord(_WORD* status) {
    _DWORD ret;

    if (readObj(0x6041, 0x00, &ret) != 0) {
        LOG_ERROR("Read status word. ");
        return -1;
    }

    *status = ret & 0xFFFF;
    return 0;
}

int Epos4::readITP(uint8_t* time, int8_t* unit) {
    _DWORD val;
    int n = readObj(INTERP_TIME_ADDR, 0x01, &val);
    if (n != 0) {
        LOG_ERROR("Read Obj failed. Error code: ", m_uiError);
        return -1;
    }

    *time = val;

    n = readObj(INTERP_TIME_ADDR, 0x02, &val);
    if (n != 0) {
        LOG_ERROR("Read Obj failed. Error code: ", m_uiError);
        return -1;
    }

    *unit = val;
}

int Epos4::setITP(uint8_t value, int8_t index) {
    _BYTE idx = index & 0xFF;
    int n = writeObj(INTERP_TIME_ADDR, 0x01, value);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(INTERP_TIME_ADDR, 0x02, idx);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    value = 0;
    index = 0;
    readITP(&value, &index);

    return 0;
}

int32_t Epos4::angle2Pos(float fAngle, bool bRadian) {
    if (!bRadian)
        fAngle = fAngle * (M_PI / 180.f);

    return round((fAngle / (2.f * M_PI)) * (m_iEncoderResolution));
}

int Epos4::getActualPosition(int32_t* piPos) {
    _DWORD ret;

    if (readObj(0x6064, 0x00, &ret) != 0) {
        LOG_ERROR("Get positon failed. Error: %h", m_uiError);
        return -1;
    }

    LOG_TRACE("Position: %i", (int) ret);
    *piPos = ret;

    return 0;
}

HomingStatus Epos4::getHomingStatus() {
    if (m_iCurrentMode != Homing) {
        return Error;
    }

    _WORD stat;
    int err = readStatusWord(&stat);
    if (err != 0) {
        LOG_ERROR("readStatusWord");
        return Error;
    }
    // LOG_LOG("homing status: %h", stat);

    if (stat & (1 << 13)) {
        LOG_ERROR("Homing error");
        return Error;
    }

    if ((stat & (1 << 12)) && (stat & (1 << 15))) {
        return Completed;
    }


    return stat & (1 << 10) ? Interrupted : InProgress;
}

int Epos4::getOpMode(OpMode* opMode, char* sOpMode) {
    _DWORD ret;

    if (readObj(MODE_OF_OPERATION_DISP_ADDR, 0x00, &ret) != 0) {
        LOG_ERROR("Get op mode failed. Error: %h", m_uiError);
        return -1;
    }

    m_iCurrentMode = static_cast<OpMode>(ret & 0xFF);
    if (opMode) *opMode = m_iCurrentMode;

    if (sOpMode) {
        const char* m = getOpModeString(m_iCurrentMode);
        strcpy(sOpMode, m);
    }
    return 0;
}

char* Epos4::getOpModeString(OpMode mode) const {
    switch (mode) {
    case OpMode::ProfilePosition:
        return "Profile Position Mode";
        break;
    case OpMode::ProfileVelocity:
        return "Profile Velocity Mode";
        break;
    case OpMode::Homing:
        return "Homing Mode";
        break;
    case OpMode::CyclicSyncPosition:
        return "Cyclic Synchronous Position Mode";
        break;
    case OpMode::CyclicSyncVelocity:
        return "Cyclic Synchronous Velocity Mode";
        break;
    case OpMode::CyclicSyncTorque:
        return "Cyclic Synchronous Torque Mode";
        break;
    default:
        break;
    }
    return "";
}

int Epos4::setOpMode(OpMode opMode, uint8_t uiInterpolationTime, int8_t iInterpolationIndex, HomingMethod homingMethod) {
    int n;
    n = writeObj(MODE_OF_OPERATION_ADDR, 0x0, (uint8_t) opMode);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    m_iCurrentMode = opMode;

    switch (opMode) {
    case ProfilePosition:
        n = setProfile();
        if (n != 0) {
            LOG_ERROR("setProfile");
            return -1;
        }
        break;

    case ProfileVelocity:
        n = setProfile();
        if (n != 0) {
            LOG_ERROR("setProfile");
            return -1;
        }
        break;

    case Homing:
        n = setHomingMethod(homingMethod);
        if (n != 0) {
            LOG_ERROR("setHomingMethod");
            return -1;
        }
        n = SetHomeOffset(52000); //52000

        if(m_uiNodeID >= 15){
            n = SetHomeOffset(0);
        }
        if(m_uiNodeID > 6 && m_uiNodeID < 13){
            n = SetHomeOffset(-25); //-25
        }
        if(m_uiNodeID == 13){   // Strummer slider
            n = SetHomeOffset(29500);
        }
        if(m_uiNodeID == 14){   // Strummer picker
            n = SetHomeOffset(100);
        }

        if(n != 0 ) {
            LOG_ERROR("setHomeOffset");
            return -1;
        }
        n = SetHomeSpeedSwitch(200);
        if(n != 0 ) {
            LOG_ERROR("setHomeSpeedSwitch");
            return -1;
        }

//        n = SetHomePosition(1000);
//        if(n != 0 ) {
//            LOG_ERROR("setHomePosition");
//            return -1;
//        }
        n = setHomingCurrentThreshold(2000);
        //n = setHomingCurrentThreshold(400);
        if(m_uiNodeID > 6 && m_uiNodeID < 13){
            n = setHomingCurrentThreshold(500);
        }
//        if(m_uiNodeID == 7){
//            n = setHomingCurrentThreshold(1500);; //-25
//        }
        if(m_uiNodeID == 14){ //Strummer-Picker
//            n = setHomingCurrentThreshold(400);
            n = setHomingCurrentThreshold(300);
        }
        if(m_uiNodeID >= 15){//Picker
            n = setHomingCurrentThreshold(500);
        }
        if (n != 0) {
            LOG_ERROR("setHomingCurrentThreshold");
            return -1;
        }

        break;

    case CyclicSyncPosition:
        n = setITP(uiInterpolationTime, iInterpolationIndex);
        if (n != 0) return -1;

        n = setProfile();
        if (n != 0) {
            LOG_ERROR("setProfile");
            return -1;
        }
        break;

    case CyclicSyncVelocity:
        break;

    case CyclicSyncTorque:
        int err = writeObj(0x6084, 0x0, 10000);
        if (err != 0) {
            LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
            return -1;
        }

        // Profile Quick stop deceleration
        err = writeObj(0x6085, 0x0, 10000);
        if (err != 0) {
            LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
            return -1;
        }
    }

    // Refer App notes -> 7.6
    // control word Shutdown (quickstop and enable voltage)
    int err = shutdown();

    _DWORD mooDisplay;
    n = readObj(0x6061, 0x0, &mooDisplay);
    if (n != 0) {
        LOG_ERROR("read Modes of operation display");
        return -1;
    }

    // LOG_LOG("Mode display (%i): %h", m_uiNodeID, mooDisplay);

    if (mooDisplay != opMode) {
        LOG_WARN("Mode not set properly");
    }
    return err;
}

int Epos4::setNominalCurrent(_DWORD current) {
    if (current < 0 || current > 6000) {    // For EPOS4 50/5
        LOG_ERROR("Current Not in range");
        return -1;
    }

    int n;
    n = writeObj(MOTOR_DATA_ADDR, NOMINAL_CURRENT, current);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    return 0;
}

int Epos4::setOutputCurrentLimit(_DWORD currentLimit) {
    if (currentLimit < 0 || currentLimit > 30000) {
        LOG_ERROR("Current Not in range");
        return -1;
    }

    int n;
    n = writeObj(MOTOR_DATA_ADDR, OUTPUT_CURRENT_LIMIT, currentLimit);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    return 0;
}

int Epos4::setNumPolePairs(_BYTE polePairs) {
    if (polePairs < 1 || polePairs > 255) {    // For EPOS4 50/5
        LOG_ERROR("Current Not in range");
        return -1;
    }

    int n;
    n = writeObj(MOTOR_DATA_ADDR, POLE_PAIRS, polePairs);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    return 0;
}

int Epos4::setThermalTimeConstantWinding(_WORD ttconstWinding) {
    if (ttconstWinding < 1 || ttconstWinding > 10000) {
        LOG_ERROR("torque Constant Not in range. Refer FW spec 6.2.53.4");
        return -1;
    }
    int n;
    n = writeObj(MOTOR_DATA_ADDR, THERMAL_TIME_CONST_WINDING, ttconstWinding);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    return 0;

}

int Epos4::setMotorTorqueConstant(_DWORD torqueConst) {
    if (torqueConst < 0 || torqueConst > 10000000) {
        LOG_ERROR("torque Constant Not in range. Refer FW spec 6.2.53.5");
        return -1;
    }

    int n;
    n = writeObj(MOTOR_DATA_ADDR, TORQUE_CONST, torqueConst);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    return 0;
}

int Epos4::setEncoderNumPulses(_DWORD pulses) {
    if (pulses < 16 || pulses > 2500000) {
        LOG_ERROR("Pulses Not in range. Refer FW spec 6.2.56.1");
        return -1;
    }

    return writeObj(0x3010, 0x01, pulses);
}

int Epos4::setEncoderType(_WORD type) {
    return writeObj(0x3010, 0x02, type);
}

int Epos4::setControlWord(_WORD cw) {
    int n = writeObj(CTRL_WORD_ADDR, 0x00, cw);
    // LOG_LOG("%i", n);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    m_uiCurrentCtrlWord = cw;
    delay(5);
    //delay(100);
    return 0;
}

int Epos4::shutdown() {
    return setControlWord(0x0006);
}

int Epos4::setEnable(bool bEnable) {
    // control word switch on and enable
    // Refer FW spec -> 6.2.94
    // bit 0 -> Switched On
    // bit 1 -> Enable Voltage
    // bit 2 -> Quick Stop
    // bit 3 -> Enable Operation
    _WORD cw = 0x000F;
    // bit 4 -> new setpoint (PPM) | Homing start (HMM)
    // bit 5 -> Change immediately (PPM)
    // bit 6 -> Abs (0) / rel (1) (PPM)
    // bit 7 -> Fault Reset
    // bit 8 -> Halt (Profiled modes)
    // bit 15 -> Endless Move (PPM)

    // if (m_iCurrentMode == ProfilePosition) cw = 0xBB;

    if (!bEnable) cw = 0x0004;

    return setControlWord(cw);
}

int Epos4::setProfile(_DWORD vel, _DWORD acc) {
    int err;
    // Profile Velocity
    err = writeObj(0x6081, 0x0, vel);
    if (err != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    // Profile Acc
    err = writeObj(0x6083, 0x0, acc);
    if (err != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    // Profile Deceleration
    err = writeObj(0x6084, 0x0, acc);
    if (err != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    // Profile Quick stop deceleration
    err = writeObj(0x6085, 0x0, 10000);
    if (err != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    // Shutdown
    err = setControlWord(0x0006);
    if (err != 0) {
        LOG_ERROR("Shutdown Failed");
        return -1;
    }

    // Switch on & Enable
    err = setControlWord(0x000F);
    if (err != 0) {
        LOG_ERROR("Switch on & Enable Failed");
        return -1;
    }
}

int Epos4::setHomingMethod(HomingMethod method) {
    return writeObj(0x6098, 0x00, (uint8_t) method);
}

int Epos4::setHomingCurrentThreshold(_WORD currentThreshold) {
    return writeObj(0x30B2, 0x0, currentThreshold);
}
int Epos4::setTargetTorque(int16_t torque){
    int err = writeObj(0x6071, 0x0, torque);
    if (err != 0) {
        LOG_ERROR("Write Obj failed for setting torque. Error code: ", m_uiError);
        return -1;
    }
}


int Epos4::moveToPosition(int32_t pos, bool bWait) {
    pos *= m_iDirMultiplier;

    //LOG_LOG("position: %i", pos);
    int err;
    // Target position
    err = writeObj(0x607A, 0x0, pos);
    if (err != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    // Abs Pos, start immediately
    err = setControlWord(0x003F);
    if (err != 0) {
        LOG_ERROR("Abs Pos, start immediately");
        return -1;
    }

    _WORD stat = 0x0;
    err = readStatusWord(&stat);
    if (err != 0) {
        LOG_ERROR("readStatusWord");
        return -1;
    }
    LOG_LOG("stat (%i): %h", m_uiNodeID, stat);

    if (bWait) {
        // refer FW spec table 7-64 -> 
        while (!(stat & 0x400)) {
            err = readStatusWord(&stat);
            // LOG_LOG("wait stat: %h", stat);
            if (err != 0) {
                LOG_ERROR("readStatusWord");
                return -1;
            }

            if ((stat) & 0x8) {
                LOG_ERROR("Fault state");
                return -1;
            }
            err = setControlWord(0x000F);
            if (err != 0) {
                LOG_ERROR("Abs Pos, start immediately");
                return -1;
            }

        }
        LOG_LOG("PASSED A MOVE");

    }

    m_iEncoderPosition = pos;
    return 0;
}

int Epos4::rotate(float fAngle, bool bRadian, bool bWait) {
    int32_t pos = angle2Pos(fAngle, bRadian);
    return moveToPosition(pos, bWait);
}

int Epos4::moveWithVelocity(int32_t velocity) {
    int err;
    velocity *= m_iDirMultiplier;
    // Target velocity
    err = writeObj(0x60FF, 0x0, velocity);
    if (err != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    delay(10);
    // Start Move
    err = setControlWord(0x000F);
    if (err != 0) {
        LOG_ERROR("Start Move failed");
        return -1;
    }
    return 0;
}

int Epos4::setFollowErrorWindow(_DWORD errWindow) {
    int err;
    err = writeObj(0x6065, 0x00, errWindow);
    if (err != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    return 0;
}

int Epos4::quickStop() {
    return setControlWord(0x000B);
}

int Epos4::startHoming() {
    // This delay is needed for homing to work
    delay(50);  // Can be as low as 10ms
    return setControlWord(0x001F);
}

int Epos4::SetHomeOffset(int32_t iPos) {
    int n;
    iPos *= m_iDirMultiplier;

    n = writeObj(0x30B1, 0x00, iPos);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    m_iEncoderPosition = iPos;
    return 0;

}
int Epos4::SetHomeSpeedSwitch(int32_t iVel) {
    int n;

    n = writeObj(0x6099, 0x01, iVel);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    return 0;

}



int Epos4::SetHomePosition(int32_t iPos) {
    int n;
//    LOG_LOG("Setting Home Position");
    iPos *= m_iDirMultiplier;

    n = writeObj(0x30B0, 0x00, iPos);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    m_iEncoderPosition = iPos;
    return 0;
}

int Epos4::clearFault() {
    int err = setControlWord(0x80);
    if (err != 0) return err;

    m_uiError = 0;
    return 0;
}

int Epos4::setCurrentControlParameters() {
    int n;
    n = writeObj(CURRENT_CTRL_PARAM_ADDR, CC_P_GAIN, 781067);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(CURRENT_CTRL_PARAM_ADDR, CC_I_GAIN, 1386330);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    return 0;
}
int Epos4::setCurrentControlParameters_StrummerPicker() {
    int n;
    n = writeObj(CURRENT_CTRL_PARAM_ADDR, CC_P_GAIN, 970589);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(CURRENT_CTRL_PARAM_ADDR, CC_I_GAIN, 1952164);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    return 0;
}

int Epos4::setCurrentControlParameters_StrummerSlider() {
    int n;
    n = writeObj(CURRENT_CTRL_PARAM_ADDR, CC_P_GAIN, 952440);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(CURRENT_CTRL_PARAM_ADDR, CC_I_GAIN, 2186907);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    return 0;
}

int Epos4::setCurrentControlParameters_Pickers() {
    int n;
    n = writeObj(CURRENT_CTRL_PARAM_ADDR, CC_P_GAIN, 1042729);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(CURRENT_CTRL_PARAM_ADDR, CC_I_GAIN, 2976309);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    return 0;
}

int Epos4::setCurrentControlParameters_EC20() {
    int n;
    n = writeObj(CURRENT_CTRL_PARAM_ADDR, CC_P_GAIN, 3456649);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(CURRENT_CTRL_PARAM_ADDR, CC_I_GAIN, 10257);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    return 0;
}


int Epos4::setCurrentControlParameters_EC60() {
    int n;
    n = writeObj(CURRENT_CTRL_PARAM_ADDR, CC_P_GAIN, 569005);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(CURRENT_CTRL_PARAM_ADDR, CC_I_GAIN, 3403363);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    return 0;
}

int Epos4::setPositionControlParameters() {
    int n;
    n = writeObj(POS_CTRL_PARAM_ADDR, PC_P_GAIN, 830000);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    _DWORD ans;
    n = readObj(POS_CTRL_PARAM_ADDR, PC_P_GAIN, &ans);
    if (n != 0) {
        LOG_ERROR("Read Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_I_GAIN, 290000);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_D_GAIN, 70000);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_FF_V_GAIN, 0);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_FF_A_GAIN, 0);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    return 0;
}

int Epos4::setPositionControlParameters_StrummerSlider() {
    int n;
    n = writeObj(POS_CTRL_PARAM_ADDR, PC_P_GAIN, 9348336);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    _DWORD ans;
    n = readObj(POS_CTRL_PARAM_ADDR, PC_P_GAIN, &ans);
    if (n != 0) {
        LOG_ERROR("Read Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_I_GAIN, 2186907);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_D_GAIN, 98967);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_FF_V_GAIN, 22758);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_FF_A_GAIN, 528);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    return 0;
}

int Epos4::setPositionControlParameters_StrummerPicker() {
    int n;
    n = writeObj(POS_CTRL_PARAM_ADDR, PC_P_GAIN, 5172512);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    _DWORD ans;
    n = readObj(POS_CTRL_PARAM_ADDR, PC_P_GAIN, &ans);
    if (n != 0) {
        LOG_ERROR("Read Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_I_GAIN, 12699311);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_D_GAIN, 20000);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_FF_V_GAIN, 47393);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_FF_A_GAIN, 870);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    return 0;
}

int Epos4::setPositionControlParameters_Pickers() {
    int n;
    n = writeObj(POS_CTRL_PARAM_ADDR, PC_P_GAIN, 18462573);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    _DWORD ans;
    n = readObj(POS_CTRL_PARAM_ADDR, PC_P_GAIN, &ans);
    if (n != 0) {
        LOG_ERROR("Read Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_I_GAIN, 157853228);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_D_GAIN, 170004);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_FF_V_GAIN, 9945);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_FF_A_GAIN, 585);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }
    return 0;
}

int Epos4::setPositionControlParameters_EC20() {
    int n;
    n = writeObj(POS_CTRL_PARAM_ADDR, PC_P_GAIN, 200000); // 92493
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    _DWORD ans;
    n = readObj(POS_CTRL_PARAM_ADDR, PC_P_GAIN, &ans);
    if (n != 0) {
        LOG_ERROR("Read Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_I_GAIN, 905480); //905480
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_D_GAIN, 2643); //2643
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_FF_V_GAIN, 507);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_FF_A_GAIN, 36);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    return 0;
}


int Epos4::setPositionControlParameters_EC60() {
    int n;
    n = writeObj(POS_CTRL_PARAM_ADDR, PC_P_GAIN, 15758200); // 11758200
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    _DWORD ans;
    n = readObj(POS_CTRL_PARAM_ADDR, PC_P_GAIN, &ans);
    if (n != 0) {
        LOG_ERROR("Read Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_I_GAIN, 22040510);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_D_GAIN, 522732);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_FF_V_GAIN, 0);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    n = writeObj(POS_CTRL_PARAM_ADDR, PC_FF_A_GAIN, 7746);
    if (n != 0) {
        LOG_ERROR("Write Obj failed. Error code: ", m_uiError);
        return -1;
    }

    return 0;
}

int Epos4::setNMTState(NMTState nmtState) {
    m_txMsg.id = 0x0;
    m_txMsg.length = 2;
    m_txMsg.format = CAN_STD_FORMAT;
    m_txMsg.data[0] = (uint8_t) nmtState;
    m_txMsg.data[1] = m_uiNodeID;

    int n = CanBus.writeMessage(&m_txMsg);
    if (n != 2) {
        LOG_ERROR("CanBus write msg failed. wrote %i units instead of %i units", n, m_txMsg.length);
        return -1;
    }

    m_currentNMTState = nmtState;
    return 0;
}

int Epos4::PDO_config() {
    int err;

    /********** TPDO 3 stuffs **********/

    // Set COD ID for TPDO3
    err = writeObj(0x1802, 0x01, COB_ID_TPDO3 + m_uiNodeID);
    if (err < 0) {
        LOG_ERROR("Set COB ID Failed. Error code: %h", m_uiError);
    }

    // Set TPDO3 transmission type to Asynchronous
    err = writeObj(0x1802, 0x02, 255);
    if (err != 0) {
        LOG_ERROR("Set transmission type failed. Error code: %h", m_uiError);
    }

    // Set TPDO3 Inhibition time
    err = writeObj(0x1802, 0x03, 10);
    if (err != 0) {
        LOG_ERROR("Set transmission type failed. Error code: %h", m_uiError);
    }

    /********** RPDO stuffs **********/
    err = PDO_configRPDO3();
    if (err != 0) {
        LOG_ERROR("Failed to configure RPDO3. Error code: %h", m_uiError);
    }

    return kNoError;
    // return PDO_configRPDO4();
}

int Epos4::PDO_configRPDO3() {
    int err;

    // Set COB ID for RPDO3
    err = writeObj(0x1402, 0x01, COB_ID_RPDO3 + m_uiNodeID);
    if (err != 0) {
        LOG_ERROR("Set COB ID Failed for RPDO3. Error code: %h", m_uiError);
        return err;
    }

    // Set RPDO3 transmission type to Asynchronous
    err = writeObj(0x1402, 0x02, 255);
    if (err != 0) {
        LOG_ERROR("Set transmission type failed for RPDO3. Error code: %h", m_uiError);
        return err;
    }

    /*
    To be able to change the PDO mapping, the following procedure must be performed:
    a) Write the value “0” (zero) to subindex 0x00 (disable PDO).
    b) Modify the desired objects in subindex 0x01…0x0n.
    c) Write the desired number of mapped objects to subindex 0x00.
    */

    // // Write the value “0” (zero) to subindex 0x00 (disable PDO).
    // err = writeObj(0x1602, 0x00, 0);
    // if (err != 0) {
    //     LOG_ERROR("write zero to 0x00 failed for RPDO3. Error code: %h", m_uiError);
    //     return err;
    // }

    // // Modify the desired objects in subindex 0x01…0x0n.
    // err = writeObj(0x1602, 0x01, 0x60400010);   // Controlword
    // if (err != 0) {
    //     LOG_ERROR("write to 0x01 failed for RPDO3. Error code: %h", m_uiError);
    //     return err;
    // }

    // err = writeObj(0x1602, 0x02, 0x607A0020);   // Position
    // if (err < 0) {
    //     LOG_ERROR("write to 0x02 failed for RPDO3. Error code: %h", m_uiError);
    //     return err;
    // }

    // // Write the desired number of mapped objects to subindex 0x00.
    // err = writeObj(0x1602, 0x00, 2);
    // if (err != 0) {
    //     LOG_ERROR("write length failed for RPDO3. Error code: %h", m_uiError);
    //     return err;
    // }

    return 0;
}

int Epos4::PDO_configRPDO4() {
    int err;

    // Set COB ID for RPDO4
    err = writeObj(0x1403, 0x01, COB_ID_RPDO4 + m_uiNodeID);
    if (err != 0) {
        LOG_ERROR("Set COB ID Failed for RPDO4. Error code: %h", m_uiError);
        return err;
    }

    // Set RPDO3 transmission type to Asynchronous
    err = writeObj(0x1403, 0x02, 255);
    if (err != 0) {
        LOG_ERROR("Set transmission type failed for RPDO4. Error code: %h", m_uiError);
        return err;
    }

    /*
    To be able to change the PDO mapping, the following procedure must be performed:
    a) Write the value “0” (zero) to subindex 0x00 (disable PDO).
    b) Modify the desired objects in subindex 0x01…0x0n.
    c) Write the desired number of mapped objects to subindex 0x00.
    */

    // // Write the value “0” (zero) to subindex 0x00 (disable PDO).
    // err = writeObj(0x1603, 0x00, 0);
    // if (err != 0) {
    //     LOG_ERROR("write zero to 0x00 failed for RPDO4. Error code: %h", m_uiError);
    //     return err;
    // }

    // // Modify the desired objects in subindex 0x01…0x0n.
    // err = writeObj(0x1603, 0x01, 0x60810020);   // Velocity
    // if (err != 0) {
    //     LOG_ERROR("write to 0x01 failed for RPDO4. Error code: %h", m_uiError);
    //     return err;
    // }

    // err = writeObj(0x1603, 0x02, 0x60830020);   // Acceleration
    // if (err != 0) {
    //     LOG_ERROR("write to 0x02 failed for RPDO4. Error code: %h", m_uiError);
    //     return err;
    // }

    // // Write the desired number of mapped objects to subindex 0x00.
    // err = writeObj(0x1603, 0x00, 2);
    // if (err != 0) {
    //     LOG_ERROR("write length failed for RPDO4. Error code: %h", m_uiError);
    //     return err;
    // }

    return 0;
}

int Epos4::PDO_setControlWord(_WORD cw) {
    m_txMsg.id = COB_ID_RPDO1 + m_uiNodeID;
    m_txMsg.format = CAN_STD_FORMAT;
    m_txMsg.length = 2;
    m_txMsg.data[0] = cw & 0xFF;
    m_txMsg.data[1] = (cw >> 8) & 0xFF;
    int n = CanBus.writeMessage(&m_txMsg);

    if (n != 2) {
        LOG_ERROR("CanBus write msg failed.");
        return -1;
    }

    m_uiCurrentCtrlWord = cw;
    return 0;
}

int Epos4::PDO_quickStop() {
    return PDO_setControlWord(0x000B);
}

int Epos4::PDO_processMsg(can_message_t& msg) {
    m_uiCurrentStatusWord = ((msg.data[1] & 0xFF) << 8) + msg.data[0];
    static int32_t callbackEncPos = 0;
    m_iEncoderPosition = (((msg.data[5] & 0xFF) << 24) + ((msg.data[4] & 0xFF) << 16) + ((msg.data[3] & 0xFF) << 8) + msg.data[2]) * m_iDirMultiplier;
    m_uiError = ((msg.data[7] & 0xFF) << 8) + msg.data[6];
    // Callback only when the encoder value changes more than a threshold
    if (abs(m_iEncoderPosition - callbackEncPos) > CALLBACK_ENC_THRESHOLD) {
        callbackEncPos = m_iEncoderPosition;
        // LOG_LOG("Encoder position: %i", m_iEncoderPosition);
    }

    m_bFault = (m_uiCurrentStatusWord & (1 << 3));

    if (m_bFault || m_uiError != 0x0000) {
        LOG_WARN("status: %h - Fault detected in node %i. Error (%h): %s", m_uiCurrentStatusWord, m_uiNodeID, m_uiError, getDeviceError(m_uiError));
    }

    return 0;
}

int Epos4::PDO_setPosition(int32_t position) {
    // position *= m_iDirMultiplier;
    //LOG_LOG("%i", position);

    uint8_t LSB = 0x0F;
    if (m_bFault)
        LSB = 0x8F;

    m_txMsg.id = COB_ID_RPDO3 + m_uiNodeID;
    m_txMsg.format = CAN_STD_FORMAT;
    m_txMsg.length = 6;
    m_txMsg.data[0] = LSB;  // cw set to enable and switch on. Clear fault if present
    m_txMsg.data[1] = 0x0;
    m_txMsg.data[2] = (uint8_t) (position & 0xFF);
    m_txMsg.data[3] = (uint8_t) ((position >> 8) & 0xFF);
    m_txMsg.data[4] = (uint8_t) ((position >> 16) & 0xFF);
    m_txMsg.data[5] = (uint8_t) ((position >> 24) & 0xFF);
    int n = CanBus.writeMessage(&m_txMsg);

    if (n != m_txMsg.length) {
        LOG_ERROR("CanBus write msg failed.");
        return -1;
    }

    m_iEncoderPosition = position;
    return 0;
}

int Epos4::PDO_rotate(float fAngle, bool bRadian) {
    int32_t pos = angle2Pos(fAngle, bRadian);
    return PDO_setPosition(pos);
}

int Epos4::PDO_setVelocity(int32_t iVelocity) {
    iVelocity = iVelocity * m_iDirMultiplier;
    uint8_t LSB = 0x0F;
    if (m_bFault)
        LSB = 0x8F;

    m_txMsg.id = COB_ID_RPDO4 + m_uiNodeID;
    m_txMsg.format = CAN_STD_FORMAT;
    m_txMsg.length = 6;
    m_txMsg.data[0] = LSB;  // cw set to enable and switch on. Clear fault if present
    m_txMsg.data[1] = 0x0;
    m_txMsg.data[2] = (uint8_t) (iVelocity & 0xFF);
    m_txMsg.data[3] = (uint8_t) ((iVelocity >> 8) & 0xFF);
    m_txMsg.data[4] = (uint8_t) ((iVelocity >> 16) & 0xFF);
    m_txMsg.data[5] = (uint8_t) ((iVelocity >> 24) & 0xFF);
    int n = CanBus.writeMessage(&m_txMsg);

    if (n != m_txMsg.length) {
        LOG_ERROR("CanBus write msg failed.");
        return -1;
    }

    return 0;
}

int Epos4::setRxMsg(can_message_t& msg) {
    if (!m_bSDOBusy) {
        LOG_ERROR("No one requested CAN message. Not copying...");
        return -1;
    }
    memcpy(&m_rxMsg, &msg, sizeof(can_message_t));
    m_bSDOBusy = false;
    return 0;
}

void Epos4::handleEMCYMsg(can_message_t& msg) {
    m_uiError = (msg.data[1] << 8) + msg.data[0];
    if (m_uiError != 0)
        LOG_ERROR("Device Error for node %i: %h", m_uiNodeID, m_uiError);
}
