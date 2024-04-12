//
// Created by Raghavasimhan Sankaranarayanan on 03/30/22.
//

#ifndef STRIKERCONTROLLER_H
#define STRIKERCONTROLLER_H

#include "def.h"
#include "striker.h"
#include <HardwareTimer.h>

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

    Error_t init(MotorSpec spec, bool bInitCAN = true) {
        LOG_LOG("Initializing Controller");
        int err = 0;
        if (bInitCAN) {
            if (!CanBus.begin(CAN_BAUD_1000K, CAN_STD_FORMAT)) {
                LOG_ERROR("CAN open failed");
                return kFileOpenError;
            }
            CanBus.attachRxInterrupt(canRxHandle);
        }

        RPDOTimer.setPeriod(PDO_RATE * 1000);
        RPDOTimer.attachInterrupt(RPDOTimerIRQHandler);
        LOG_LOG("Controller Initialized");

        return initStrikers(spec);
    }

    Error_t initStrikers(MotorSpec spec) {
        m_motorSpec = spec;
        Error_t err = kNoError;
        for (int i = 1; i < NUM_STRIKERS + 1; ++i) {
            LOG_LOG("slider %i", i);
            err = m_striker[i].init(i, spec);
            delay(500);
            if (err != kNoError) {
                LOG_ERROR("Cannot initialize slider with id %i. Error: %i", i, err);
            }
        }
        MotorSpec spec2 = EC20;
        err = kNoError;
        for (int i = NUM_STRIKERS + 1; i < NUM_PRESSERS + NUM_STRIKERS + 1; ++i) {
            LOG_LOG("presser %i", i);
            err = m_striker[i].init(i, spec2);
            delay(500);
            if (err != kNoError) {
                LOG_ERROR("Cannot initialize presser with id %i. Error: %i", i, err);
            }
            else {
                LOG_LOG("Successfully initialized presser with id %i", i);
            }
        }
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
            for (int i = 1; i < NUM_STRIKERS + 1; ++i) {
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


    void executeCommand(uint8_t idCode, char mode, int midiVelocity, uint8_t channelPressure) {
        float fretLength = 263 - (SCALE_LENGTH - (SCALE_LENGTH / pow(2, ((midiVelocity) / 12.f))));
        float pos2pulse = (fretLength * 360) / 2048;
//        Serial.print("Position is: ");
//        Serial.print(" ");
//        Serial.print(fretLength);
//        Serial.print(" ");
//        Serial.print("pulse is: ");
//        Serial.print(" ");
//        Serial.println(pos2pulse);
        Serial.println(idCode);

        int mult = 1;
        bool offset = false;
        if(idCode == 2 || idCode == 3 || idCode == 6){
            mult = -1;
            offset = true;
        }
        int os = 0;
        switch (midiVelocity){
        case 1:
            midiVelocity = 49;
            if (offset){
                os = 0;
            }
            midiVelocity = mult * 49 + os;
            break;
        case 2:
            midiVelocity = 43;
            if (offset){
                os = 1;
                }
            midiVelocity = mult * 43 + os;
            break;
        case 3:
            midiVelocity = 36;
            if (offset){
                os = 0;
                }
            midiVelocity = mult * 36 + os;
            break;
        case 4:
            midiVelocity = 30;
            if (offset){
                os = 1;
                }
            midiVelocity = mult * 30 + os;
            break;
        case 5:
            midiVelocity = 24;
            if (offset){
                os = 1;
                }
            midiVelocity = mult * 24 + os;
            break;
        case 6:
            midiVelocity = 18;
            if (offset){
                os = 1;
                }
            midiVelocity = mult * 18 + os;
            break;
        case 7:
            midiVelocity = 12;
            if (offset){
                os = 1;
                }
            midiVelocity = mult * 12 + os;
            break;
        case 8:
            midiVelocity = 8;
            if (offset){
                    os = 1;
                }
            midiVelocity = mult * 8 + os;
            break;
        case 9:
            midiVelocity = 1;
            if (offset){
                    os = 0;
                }
            midiVelocity = mult * 2 + os;
            break;
        default:
            midiVelocity = 0;
            LOG_LOG("ERROR; not a fret");
            break;
        }
        uint8_t uiStrike = prepare(idCode, mode, midiVelocity, channelPressure);
        strike(uiStrike);
    }

    void start() {
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
        for (int i = 1; i < NUM_STRIKERS + 1; ++i) {
            err = m_striker[i].enablePDO(bEnable);
            LOG_LOG("Enabling PDO for slider %i", i);
            delay(1000);
            if (err != kNoError) {
                LOG_ERROR("EnablePDO failed. Error Code %i", err);
                return err;
            }
        }
        for (int i = NUM_STRIKERS + 1; i < NUM_STRIKERS + NUM_PRESSERS + 1; ++i) {
            err = m_striker[i].enablePDOEC20(bEnable);
            LOG_LOG("Enabling PDO for presser %i", i);
            delay(1000);
            if (err != kNoError) {
                LOG_ERROR("EnablePDO failed. Error Code %i", err);
                return err;
            }
        }

        return kNoError;
    }

    Error_t enableStrikers(bool bEnable = true) {
        int err;
        for (int i = 1; i < NUM_STRIKERS + NUM_PRESSERS + 1; ++i) {
            LOG_LOG("Enabling controller %i", i);
            err = m_striker[i].enable(bEnable);
            delay(500);
            if (err != 0) {
                LOG_ERROR("Enable failed. Error Code %h", err);
                return kSetValueError;
            }
        }

        return kNoError;
    }

    int strike(uint8_t idCode) {
        for (int i = 1; i < NUM_STRIKERS + 1; ++i) {
            if (idCode == i) {
                // LOG_LOG("(idcode: %h) Striking: %i", idCode, i);
                m_striker[i].strike();
            }
        }
    }

private:
    Striker m_striker[NUM_STRIKERS + NUM_PRESSERS + 1]; // 0 is dummy
    static StrikerController* pInstance;
    volatile bool m_bPlaying = false;
    MotorSpec m_motorSpec = MotorSpec::EC45;

    HardwareTimer RPDOTimer;//, faultClearTimer;

    StrikerController(): RPDOTimer(TIMER_CH1) {}
    // , faultClearTimer(TIMER_CH3) {}

    ~StrikerController() {
        reset();
        destroyInstance();
    }

    static void canRxHandle(can_message_t* arg) {
        auto id = arg->id - COB_ID_SDO_SC;
        if (id > 0 && id < NUM_STRIKERS + NUM_PRESSERS + 1) {
            //LOG_LOG("controller %i, if statement 1", id);
            pInstance->m_striker[id].setRxMsg(*arg);
        }

        id = arg->id - COB_ID_TPDO3;
        if (id > 0 && id < NUM_STRIKERS + NUM_PRESSERS + 1) {
            //LOG_LOG("controller %i, if statement 2", id);
            pInstance->m_striker[id].PDO_processMsg(*arg);
        }

        id = arg->id - COB_ID_EMCY;
        if (id > 0 && id < NUM_STRIKERS + NUM_PRESSERS + 1) {
            //LOG_LOG("controller %i, if statement 3", id);
            pInstance->m_striker[id].handleEMCYMsg(*arg);
        }
    }

    static void RPDOTimerIRQHandler() {
        for (int i = 1; i < NUM_STRIKERS + 1; ++i) {
            pInstance->m_striker[i].update();
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
