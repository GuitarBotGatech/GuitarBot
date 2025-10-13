//
// Created by Raghavasimhan Sankaranarayanan on 03/30/22.
// Modified for GuitarBot by Marcus Parker on 12/7/23
// Modified for general send_msg + executeCommand by Shayahn Mirfendereski 10/30/24
// Modified for executeEvent()
// Modified by Derrick 11/14/2024 at 5:49pm
#include "src/strikerController.h"
#include "src/logger.h"
#include <Ethernet.h>
#include <EthernetUdp.h>
// Encoder feedback transmitter
#include "src/EncoderFeedbackCollector.h"

StrikerController* pController = nullptr;
// Define global feedback collector instance (declared extern in header)
EncoderFeedbackCollector* g_feedback_collector = nullptr;
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED}; //mac adress
IPAddress ip(10, 2, 1, 177); //ip address

unsigned int localPort = 8888; //udp port to listen for packets on

char packetBuffer[2048];
uint8_t playcommands[6];
uint8_t frets[6];
uint8_t pickings[6];
int8_t tremLength;
int8_t tremSpeed;
int8_t strumAngle;
uint8_t strumSpeed;
uint8_t deflect; 
char event;
float trajPoint[16] = {1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1};


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
    delay(1000);
    LOG_LOG("Successfully Initialized! Controller Starting....");
    pController->start();

    LOG_LOG("Listening for commands...");

    // Initialize encoder feedback collector to stream encoder data to Python host
    // Adjust the IP below to the machine running EncoderUDPReceiver.py
    IPAddress python_ip(10, 2, 1, 1);
    g_feedback_collector = new EncoderFeedbackCollector(pController);
    if (g_feedback_collector) {
        Error_t fbErr = g_feedback_collector->initialize(python_ip, FEEDBACK_PORT);
        if (fbErr != kNoError) {
            LOG_ERROR("Failed to initialize encoder feedback collector");
            delete g_feedback_collector;
            g_feedback_collector = nullptr;
        } else {
            LOG_LOG("Encoder feedback collector ready on %d.%d.%d.%d:%d", python_ip[0], python_ip[1], python_ip[2], python_ip[3], FEEDBACK_PORT);
        }
    }
    else
      LOG_LOG("Feedback instantiation failed");
  }

void loop() {
    ethernetEvent();
    
    static uint32_t last_debug_print = 0;
    uint32_t now = millis();
    
    // Print debug info every 5 seconds to show the system is alive
    if (now - last_debug_print > 5000) {
        Serial.println("DEBUG: Main loop running...");
        if (g_feedback_collector) {
            Serial.println("DEBUG: g_feedback_collector is active");
        } else {
            Serial.println("DEBUG: g_feedback_collector is NULL!");
        }
        last_debug_print = now;
    }
    
    // TIMING-SAFE: Use non-blocking feedback transmission in main loop
    // This only transmits buffered data when timing interval has elapsed
    if (g_feedback_collector) {
        g_feedback_collector->transmitBufferedData();
    } else {
        // Only print this occasionally to avoid spam
        static uint32_t last_null_warning = 0;
        if (now - last_null_warning > 10000) {
            Serial.println("DEBUG: Cannot call transmitBufferedData() - g_feedback_collector is NULL");
            last_null_warning = now;
        }
    }
    
    if (complete) {

        complete = false;

        Serial.println("DEBUG: Processing trajectory command!");
        Serial.printf("DEBUG: Trajectory data: ");
        for (int i = 0; i < 15; i++) {
            Serial.printf("%.2f ", trajPoint[i]);
        }
        Serial.println();

        // Optional: mark start of a new trajectory feedback window
        if (g_feedback_collector) {
            Serial.println("DEBUG: Starting trajectory feedback collection");
            g_feedback_collector->startTrajectoryFeedback();
        }

        pController->processTrajPoints(trajPoint);

        // Force encoder feedback collection after trajectory execution
        if (g_feedback_collector) {
            Serial.println("DEBUG: Forcing encoder feedback collection after trajectory");
            g_feedback_collector->collectFeedback();
        }

        // Optional: stop feedback window after processing a single trajectory point buffer
        if (g_feedback_collector) {
            Serial.println("DEBUG: Stopping trajectory feedback collection");
            g_feedback_collector->stopTrajectoryFeedback();
        }
        //pController -> executeSlideTest(100,100,100,100,100,100,100,100);
        //pController -> testFunction();
        // pController->executeSlide(frets, playcommands);
        //pController->executeSlideDEMO(fret[0], fret[1], fret[2], fret[3], fret[4], fret[5], playcommand[0], playcommand[1], playcommand[2], playcommand[3], playcommand[4], playcommand[5]);
        

        //delay(10);
    }
}

// void ethernetEvent() {
//     int packetSize = udp.parsePacket();
//     if (packetSize) {
//       udp.read(packetBuffer, 1024);
//       //Convert each byte in packet_buffer to a uint8_t
//       event = packetBuffer[0];
//       if (event == 'L') {
//         LOG_LOG("LH event");
//         frets[0] = static_cast<uint8_t>(packetBuffer[1]);
//         frets[1] = static_cast<uint8_t>(packetBuffer[2]);
//         frets[2] = static_cast<uint8_t>(packetBuffer[3]);
//         frets[3] = static_cast<uint8_t>(packetBuffer[4]);
//         frets[4] = static_cast<uint8_t>(packetBuffer[5]);
//         frets[5] = static_cast<uint8_t>(packetBuffer[6]);
//         playcommands[0] = static_cast<uint8_t>(packetBuffer[7]);
//         playcommands[1] = static_cast<uint8_t>(packetBuffer[8]);
//         playcommands[2] = static_cast<uint8_t>(packetBuffer[9]);
//         playcommands[3] = static_cast<uint8_t>(packetBuffer[10]);
//         playcommands[4] = static_cast<uint8_t>(packetBuffer[11]);
//         playcommands[5] = static_cast<uint8_t>(packetBuffer[12]);

//       }
//       else if (event == 'S') {
//         LOG_LOG("Strum event");
//         strumAngle = packetBuffer[1];
//         strumSpeed =  packetBuffer[2];
//         deflect = packetBuffer[3];
        
//       }
//       else if (event == 'P') {
//         LOG_LOG("Pick event");
//         for (int i = 1; i <= 6; i++) {
//           pickings[i - 1] = static_cast<uint8_t>(packetBuffer[i]);
//         }
//         tremLength = packetBuffer[7];
//         tremSpeed = packetBuffer[8];
//       }
      
//       complete = true;
//     }        
// }

void ethernetEvent() {
    int packetSize = udp.parsePacket();
    if (packetSize) {
      //Serial.println(packetSize);
      udp.read(packetBuffer, packetSize);
        for (int i = 0; i < packetSize / sizeof(float); i++) {
            float* point = (float*)(packetBuffer + i * sizeof(float));
            trajPoint[i] = *point;
            // Serial.print(*point);
            // Serial.print(" ");
        }
        // Serial.println();
        complete = true;
    }
}        