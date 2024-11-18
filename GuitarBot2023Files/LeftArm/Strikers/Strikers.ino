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
int8_t tremLength;
int8_t tremSpeed;
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

    delay(2000); //Added delay for output reading
    LOG_LOG("Initializing GuitarBot...");
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
    pController->start();
    delay(2000);
    
    LOG_LOG("Listening for commands...");   // "in format (ascii characters) <mode><id code><midi velocity>"
}

void loop() {
    ethernetEvent();
    if (complete) {

        complete = false;

        LOG_LOG("slide 1: %i, slide 2: %i, slide 3: %i, slide 4: %i, slide 5: %i, slide 6: %i", fret[0], fret[1], fret[2], fret[3], fret[4], fret[5]);
        LOG_LOG("press 1: %i, press 2: %i, press 3: %i, press 4: %i, press 5: %i, press 6: %i", playcommand[0], playcommand[1], playcommand[2], playcommand[3], playcommand[4], playcommand[5]);
        LOG_LOG("pick 1: %i, pick 2: %i, pick 3: %i, pick 4: %i, pick 5: %i, pick 6: %i", pickings[0], pickings[1], pickings[2], pickings[3], pickings[4], pickings[5]);
        LOG_LOG("tremolo length: %i, tremolo speed: %i", tremLength, tremSpeed);
        LOG_LOG("strummer: %i", strumAngle);
        if (event == 'L') {
          pController->executeSlide(fret[0], fret[1], fret[2], fret[3], fret[4], fret[5], playcommand[0], playcommand[1], playcommand[2], playcommand[3], playcommand[4], playcommand[5]);
        }
        else if (event == 'P') {
          pController ->executePluckTest(pickings[3], tremLength, tremSpeed);
        }
        delay(10);
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
        fret[0] = static_cast<uint8_t>(packetBuffer[1]);
        fret[1] = static_cast<uint8_t>(packetBuffer[2]);
        fret[2] = static_cast<uint8_t>(packetBuffer[3]);
        fret[3] = static_cast<uint8_t>(packetBuffer[4]);
        fret[4] = static_cast<uint8_t>(packetBuffer[5]);
        fret[5] = static_cast<uint8_t>(packetBuffer[6]);
        playcommand[0] = static_cast<uint8_t>(packetBuffer[7]);
        playcommand[1] = static_cast<uint8_t>(packetBuffer[8]);
        playcommand[2] = static_cast<uint8_t>(packetBuffer[9]);
        playcommand[3] = static_cast<uint8_t>(packetBuffer[10]);
        playcommand[4] = static_cast<uint8_t>(packetBuffer[11]);
        playcommand[5] = static_cast<uint8_t>(packetBuffer[12]);
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
        tremLength = packetBuffer[7];
        tremSpeed = packetBuffer[8];
      }
      complete = true;
    }        
}