// Github Version
// Created by Raghavasimhan Sankaranarayanan on 03/30/22.
// Modified for GuitarBot by Marcus Parker on 12/7/23
// Modified to merge pluck and pick by Marcus Parker 10/17/24
// Modified to increase homing speed by Marcus Parker 10/22/24
// Modification in progress for queue manipulation 10/23/24

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

bool complete = false;    // Setting this flag will start processing of received message

void setup() {
    Ethernet.init(10); // set CS pin for ethernet shield
    Ethernet.begin(mac, ip); //initialize ethernet with mac and ip addresses
    //Checks for presence of Ethernet shield. Halts if no ethernet hardware present. 
    if (Ethernet.hardwareStatus() == EthernetNoHardware) {
      LOG_LOG("Ethernet shield was not found. Sorry, can't run without hardware.");
      while (true) {
        delay(10000);
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
    // delay(2000);
    // LOG_LOG("Successfully Initialized! Controller Starting....");
    delay(1000);
    pController->start();
    delay(1000);
    // delay(2000);
    // pController->executeSlide(1,1,1,5,1,1,1,1,1,1,1,1);
    // delay(2000);
    // pController->executeSlide(1,1,1,4,1,1,1,1,1,2,1,1);
    // delay(2000);
    // pController->executeSlide(1,1,1,3,1,1,1,1,1,1,1,1);
    // delay(2000);
    // pController->executeSlide(1,1,1,2,1,1,1,1,1,1,1,1);
    // delay(2000);
    // pController->executePluckTest(0);
    // delay(2000);
    // pController->executePluckTest(1);
    // delay(2000);
    // pController->executePluckTest(0);
    // delay(2000);
    // pController->executePluckTest(1);
    // delay(2000);
    // pController->executePluckTest(0);
    // delay(2000);
    //pController->executePluckTest(1);

    LOG_LOG("Listening for commands...");   // "in format (ascii characters) <mode><id code><midi velocity>"

}

void loop() {
  ethernetEvent();

    if (complete) {
      LOG_LOG("ETHERNET RECEIVED");
      //test all 6 sliders

      //30ms is in fact good and possible, just need a more stable setup -- AMIT
      //40 ms is the max if continuous to test, change the two delays above. 
      //100 ms is the max stable
        uint8_t idCode;
        uint8_t midiVelocity;
        uint8_t chPressure;
        char cMode;
        uint8_t playcommand[6];
        uint8_t fret[6];

        Error_t err = parseCommand(packetBuffer, playcommand, fret);
        complete = false;
        // //Unpress

        pController->executeSlide(fret[0], fret[1], fret[2], fret[3], fret[4], fret[5], playcommand[0], playcommand[1], playcommand[2], playcommand[3], playcommand[4], playcommand[5]);

        if (err == kNoError) {
          LOG_LOG("playcommand 1: %i, playcommand 2: %i, playcommand 3: %i, playcommand 4: %i, playcommand 5: %i, playcommand 6: %i", playcommand[0], playcommand[1], playcommand[2], playcommand[3], playcommand[4], playcommand[5]);
          LOG_LOG("fret 1: %i, fret 2: %i, fret 3: %i, fret 4: %i, fret 5: %i, fret 6: %i", fret[0], fret[1], fret[2], fret[3], fret[4], fret[5]);
        }
        //Why is this here.
        delay(10);
    }
}

void ethernetEvent() {
    int packetSize = udp.parsePacket();
    if (packetSize) {
      udp.read(packetBuffer, 1024);
      //Convert each byte in packet_buffer to a uint8_t
      for(int i = 0; i<12; i++)
      {
        int8_t value = static_cast<uint8_t>(packetBuffer[i]);
        Serial.print(value);
      }
      Serial.println('\n');
      complete = true;
    }        
}

// Format example to strike using motor 1 with velocity 80: s<SCH>P ... explanation s -> normal strike, <SCH> -> ascii of 0b00000001, P -> ascii of 80
// Pressure is another parameter to map when using choreo
// To stop tremolo, send mode t with velocity 0
Error_t parseCommand(char buffer[], uint8_t playcommand[], uint8_t fret[]) {
    if (strlen(buffer) != 12) return kCorruptedDataError;

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

    return kNoError;
}
