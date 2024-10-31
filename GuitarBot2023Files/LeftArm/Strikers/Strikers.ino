//
// Created by Raghavasimhan Sankaranarayanan on 03/30/22.
// Modified for GuitarBot by Marcus Parker on 12/7/23
// Modified for general send_msg + executeCommand by Shayahn Mirfendereski 10/30/24
//Working Ethernet version
#include "src/strikerController.h"
#include "src/logger.h"
#include <Ethernet.h>
#include <EthernetUdp.h>

StrikerController* pController = nullptr;
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED}; //mac adress
IPAddress ip(10, 2, 1, 177); //ip address

unsigned int localPort = 8888; //udp port to listen for packets on

char packetBuffer[1024];
uint8_t playcommand[6];
uint8_t fret[6];
uint8_t pickings[6];
int8_t strumAngle;
char event;

EthernetUDP udp;

bool complete = false;    // Setting this flag will start processing of received message

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
    Serial.begin(115200);


    // put your setup code here, to run once:
    delay(2000); //Added delay for output reading
    LOG_LOG("Initializing GuitarBot...");
    // delay(5000); //Added delay for output reading
    pController = StrikerController::createInstance();
    LOG_LOG("Initializing Pressers and Striker...");
    int err = pController->init(MotorSpec::EC45_Slider); //Sliders
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
    //pController->executePluckTest(0);
}

void loop() {
  //int8_t commands[18];
//test all 6 sliders
    //ethernetEvent(commands);
    ethernetEvent();
    if (complete) {

        // Error_t err = parseCommand(commands, playcommand, fret, pickings);
        complete = false;
        // //Unpress

        // if (err == kNoError) {
        //   pController->executeSlide(fret[0], fret[1], fret[2], fret[3], fret[4], fret[5], playcommand[0], playcommand[1], playcommand[2], playcommand[3], playcommand[4], playcommand[5]);
        //   LOG_LOG("playcommand 1: %i, playcommand 2: %i, playcommand 3: %i, playcommand 4: %i, playcommand 5: %i, playcommand 6: %i", playcommand[0], playcommand[1], playcommand[2], playcommand[3], playcommand[4], playcommand[5]);
        //   LOG_LOG("fret 1: %i, fret 2: %i, fret 3: %i, fret 4: %i, fret 5: %i, fret 6: %i", fret[0], fret[1], fret[2], fret[3], fret[4], fret[5]);
        //   LOG_LOG("pick 1: %i, pick 2: %i, pick 3: %i, pick 4: %i, pick 5: %i, pick 6: %i", pickings[0], pickings[1], pickings[2], pickings[3], pickings[4], pickings[5]);
        // }
        // else if (err == kCorruptedDataError) {
        //   Serial.println("Corrupted data");
        // }
        LOG_LOG("press 1: %i, press 2: %i, press 3: %i, press 4: %i, press 5: %i, press 6: %i", playcommand[0], playcommand[1], playcommand[2], playcommand[3], playcommand[4], playcommand[5]);
        LOG_LOG("slide 1: %i, slide 2: %i, slide 3: %i, slide 4: %i, slide 5: %i, slide 6: %i", fret[0], fret[1], fret[2], fret[3], fret[4], fret[5]);
        LOG_LOG("pick 1: %i, pick 2: %i, pick 3: %i, pick 4: %i, pick 5: %i, pick 6: %i", pickings[0], pickings[1], pickings[2], pickings[3], pickings[4], pickings[5]);
        LOG_LOG("strummer: %i", strumAngle);
        pController->executeSlide(fret[0], fret[1], fret[2], fret[3], fret[4], fret[5], playcommand[0], playcommand[1], playcommand[2], playcommand[3], playcommand[4], playcommand[5]);
        //delay(10);
    }
}

void ethernetEvent(int8_t commands[]) {
    int packetSize = udp.parsePacket();
    if (packetSize) {
      udp.read(packetBuffer, 1024);
      //Convert each byte in packet_buffer to a uint8_t
      for(int i = 0; i<18; i++)
      {
        int8_t value = static_cast<uint8_t>(packetBuffer[i]);
        commands[i] = value;
        //Serial.print(commands[i]);
      }
      //Serial.println('\n');
      complete = true;
    }        
}

void ethernetEvent() {
    int packetSize = udp.parsePacket();
    if (packetSize) {
      udp.read(packetBuffer, 1024);
      //Convert each byte in packet_buffer to a uint8_t
      event = packetBuffer[0];
      if (event == 'L') {
        LOG_LOG("LH event");
        playcommand[0] = static_cast<uint8_t>(packetBuffer[1]);
        playcommand[1] = static_cast<uint8_t>(packetBuffer[2]);
        playcommand[2] = static_cast<uint8_t>(packetBuffer[3]);
        playcommand[3] = static_cast<uint8_t>(packetBuffer[4]);
        playcommand[4] = static_cast<uint8_t>(packetBuffer[5]);
        playcommand[5] = static_cast<uint8_t>(packetBuffer[6]);
        fret[0] = static_cast<uint8_t>(packetBuffer[7]);
        fret[1] = static_cast<uint8_t>(packetBuffer[8]);
        fret[2] = static_cast<uint8_t>(packetBuffer[9]);
        fret[3] = static_cast<uint8_t>(packetBuffer[10]);
        fret[4] = static_cast<uint8_t>(packetBuffer[11]);
        fret[5] = static_cast<uint8_t>(packetBuffer[12]);
      }
      else if (event == 'S') {
        LOG_LOG("Strum event");
        strumAngle = packetBuffer[1];
      }
      else if (event == 'P') {
        LOG_LOG("Pick event");
        for (int i = 1; i <= 6; i++) {
          pickings[i - 1] = static_cast<uint8_t>(packetBuffer[i]);
        }
      }
      complete = true;
    }        
}

// Format example to strike using motor 1 with velocity 80: s<SCH>P ... explanation s -> normal strike, <SCH> -> ascii of 0b00000001, P -> ascii of 80
// Pressure is another parameter to map when using choreo
// To stop tremolo, send mode t with velocity 0
Error_t parseCommand(int8_t buffer[], uint8_t playcommand[], uint8_t fret[], uint8_t pickings[]) {
    //if (sizeof(buffer) / sizeof(buffer[0]) != 18) return kCorruptedDataError;

    playcommand[0] = buffer[0];
    playcommand[1] = buffer[1];
    playcommand[2] = buffer[2];
    playcommand[3] = buffer[3];
    playcommand[4] = buffer[4];
    playcommand[5] = buffer[5];
    fret[0] = buffer[6];
    fret[1] = buffer[7];
    fret[2] = buffer[8];
    fret[3] = buffer[9];
    fret[4] = buffer[10];
    fret[5] = buffer[11];
    pickings[0] = buffer[12];
    pickings[1] = buffer[13];
    pickings[2] = buffer[14];
    pickings[3] = buffer[15];
    pickings[4] = buffer[16];
    pickings[5] = buffer[17];


    return kNoError;
}
