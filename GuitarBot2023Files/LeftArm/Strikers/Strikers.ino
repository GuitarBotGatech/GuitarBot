//
// Created by Raghavasimhan Sankaranarayanan on 03/30/22.
// Modified for GuitarBot by Marcus Parker on 12/7/23
//base version
#include "src/strikerController.h"
#include "src/logger.h"

StrikerController* pController = nullptr;

String inputString = "";        // To hold incoming serial message
bool stringComplete = false;    // Setting this flag will start processing of received message
void setup() {
    // put your setup code here, to run once:
    delay(8000); //Added delay for output reading
    LOG_LOG("Initializing GuitarBot...");
    inputString.reserve(10);
    // delay(5000); //Added delay for output reading
    pController = StrikerController::createInstance();
    LOG_LOG("Initializing Pressers and Strikers...");
    int err = pController->init(MotorSpec::EC45); //All motors
    delay(15000);
    if (err != 0) {
        LOG_ERROR("Controller Init failed");
        return;
    }
//  int err = PController->init(MotorSpec::EC20); //Pressers
    if (err != 0) {
        LOG_ERROR("Controller Init failed");
        return;
    }
    delay(2000);
    LOG_LOG("Successfully Initialized! Controller Starting....");
    delay(2000);
    //pController->start(); //Just testing homing for now
    delay(2000);
    
    LOG_LOG("Listening for commands...");   // "in format (ascii characters) <mode><id code><midi velocity>"
}

void loop() {
//test all 6 sliders


    if (stringComplete) {
        // LOG_LOG("%s", inputString);
        uint8_t idCode;
        uint8_t midiVelocity;
        uint8_t chPressure;
        char cMode;

        uint8_t playcommand[6];
        uint8_t fret[6];
        Error_t err = parseCommand(inputString, playcommand, fret);
        inputString = "";
        stringComplete = false;
        //Unpress

//        for(int i = 7; i < 13; i++){
//          pController->executePress(i, -1);
//        }
//        //Slide
//        for(int i = 0; i < 6; i++) {
//          pController->executeCommand(i+1, 's', fret[i], 50);
//          if(i == 3){
//              delay(75);
//          }
//        }
//        delay(75);
//        //Press/Mute/Open
//        for(int i = 7; i < 13; i++){
//          switch(playcommand[i]) {
//            case 1:
//            pController->executePress(i, -1);
//            LOG_LOG("open on %i", i);
//            break;
//            case 2:
//            pController->executePress(i, 400);
//            LOG_LOG("press on %i", i);
//            break;
//            case 3:
//            pController->executePress(i, 50);
//            LOG_LOG("mute on %i", i);
//            break;
//            default:
//            pController->executePress(i, 0);
//            LOG_LOG("passthrough press");
//          }
//        }

        pController->executeSlide(fret[0], fret[1], fret[2], fret[3], fret[4], fret[5], playcommand[0], playcommand[1], playcommand[2], playcommand[3], playcommand[4], playcommand[5]);
        // For now, add in an executePluck() here, will probably later combine with executeSlide()
        //pController->executePluck()

        if (err == kNoError) {
          LOG_LOG("playcommand 1: %i, playcommand 2: %i, playcommand 3: %i, playcommand 4: %i, playcommand 5: %i, playcommand 6: %i", playcommand[0], playcommand[1], playcommand[2], playcommand[3], playcommand[4], playcommand[5]);
          LOG_LOG("fret 1: %i, fret 2: %i, fret 3: %i, fret 4: %i, fret 5: %i, fret 6: %i", fret[0], fret[1], fret[2], fret[3], fret[4], fret[5]);
        }
    }
}

void serialEvent() {
    while (Serial.available()) {
        char inChar = (char) Serial.read();
        inputString += inChar;
        if (inChar == '\n') {
            stringComplete = true;
        }
    }
}

// Format example to strike using motor 1 with velocity 80: s<SCH>P ... explanation s -> normal strike, <SCH> -> ascii of 0b00000001, P -> ascii of 80
// Pressure is another parameter to map when using choreo
// To stop tremolo, send mode t with velocity 0
Error_t parseCommand(const String& cmd, uint8_t playcommand[], uint8_t fret[]) {
    if (cmd.length() < 13) return kCorruptedDataError;

    playcommand[0] = cmd[0];
    playcommand[1] = cmd[1];
    playcommand[2] = cmd[2];
    playcommand[3] = cmd[3];
    playcommand[4] = cmd[4];
    playcommand[5] = cmd[5];
    fret[0] = cmd[6];
    fret[1] = cmd[7];
    fret[2] = cmd[8];
    fret[3] = cmd[9];
    fret[4] = cmd[10];
    fret[5] = cmd[11];

    return kNoError;
}
