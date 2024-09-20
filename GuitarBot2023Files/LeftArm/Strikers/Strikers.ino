//
// Created by Raghavasimhan Sankaranarayanan on 03/30/22.
// Modified for GuitarBot by Marcus Parker on 12/7/23
//base version
#include "src/strikerController.h"
#include "src/logger.h"
#include <Ethernet.h>
#include <EthernetUdp.h>

StrikerController* pController = nullptr;
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED}; //mac adress
IPAddress ip(10, 2, 1, 177); //ip address

unsigned int localPort = 8888; //udp port to listen for packets on

char packetBuffer[1024];

EthernetUDP udp;

String inputString = "";        // To hold incoming serial message
bool stringComplete = false;    // Setting this flag will start processing of received message

void setup() {
    Ethernet.init(10); // set CS pin for ethernet shield
    Ethernet.begin(mac, ip); //initialize ethernet with mac and ip addresses
    //Checks for presence of Ethernet shield. Halts if no ethernet hardware present. 
    if (Ethernet.hardwareStatus() == EthernetNoHardware) {
      LOG_LOG("Ethernet shield was not found. Sorry, can't run without hardware.");
      while (true) {
        delay(1);
      }
    } else {LOG_LOG("Ethernet shield found!");};
    //Checks for presence of etherner link.Halts if no link present. 
    if (Ethernet.linkStatus() == LinkOFF) {
      LOG_LOG("Ethernet cable is not connected.");
    } else {LOG_LOG("Ethernet cable connected!");};
    udp.begin(localPort); //begins udp on port specified above.
    Serial.begin(9600);


    // put your setup code here, to run once:
    delay(8000); //Added delay for output reading
    LOG_LOG("Initializing GuitarBot...");
    inputString.reserve(10);
    // delay(5000); //Added delay for output reading
    pController = StrikerController::createInstance();
    LOG_LOG("Initializing Pressers and Striker...");
    int err = pController->init(MotorSpec::EC45); //Sliders
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
    pController->start();
    delay(2000);
    
    LOG_LOG("Listening for commands...");   // "in format (ascii characters) <mode><id code><midi velocity>"
}

void loop() {
//test all 6 sliders
    //Serial.println("loop test");
    int packetSize = udp.parsePacket(); 
    //Serial.println(packetSize);
    if (packetSize) {
        Serial.println("WE GOT A PACKET!");
        Serial.println(packetSize);
        // LOG_LOG("%s", inputString);
        uint8_t idCode;
        uint8_t midiVelocity;
        uint8_t chPressure;
        char cMode;

        uint8_t playcommand[6];
        uint8_t fret[6];

        LOG_LOG("----------------------------------------------");
        udp.read(packetBuffer, 1024);
        LOG_LOG(packetBuffer);
        LOG_LOG("----------------------------------------------");
        // String message;
        // memcpy(&message, packetBuffer, 1024);
        // Serial.println(message);

        // Error_t err = parseCommand(inputString, playcommand, fret);
        // inputString = "";
        // stringComplete = false;
        // //Unpress

        // pController->executeSlide(fret[0], fret[1], fret[2], fret[3], fret[4], fret[5], playcommand[0], playcommand[1], playcommand[2], playcommand[3], playcommand[4], playcommand[5]);

        // if (err == kNoError) {
        //   LOG_LOG("playcommand 1: %i, playcommand 2: %i, playcommand 3: %i, playcommand 4: %i, playcommand 5: %i, playcommand 6: %i", playcommand[0], playcommand[1], playcommand[2], playcommand[3], playcommand[4], playcommand[5]);
        //   LOG_LOG("fret 1: %i, fret 2: %i, fret 3: %i, fret 4: %i, fret 5: %i, fret 6: %i", fret[0], fret[1], fret[2], fret[3], fret[4], fret[5]);
        // }
        delay(10);
    }
}

// void ethernetEvent() {
//     // while (Serial.available()) {
//     //     char inChar = (char) Serial.read();
//     //     inputString += inChar;
//     //     if (inChar == '\n') {
//     //         stringComplete = true;
//     //     }
//     // }
//     int packetSize = udp.parsePacket(); 
//     if (packetSize) {                     //if data available, prints following;

//       LOG_LOG("----------------------------------------------");
//       udp.read(packetBuffer, UDP_TX_PACKET_MAX_SIZE);
//       LOG_LOG(packetBuffer);
//       LOG_LOG("----------------------------------------------");
//     }
// }

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
