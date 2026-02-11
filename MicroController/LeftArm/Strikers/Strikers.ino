//
// Created by Raghavasimhan Sankaranarayanan on 03/30/22.
// Modified for GuitarBot by Marcus Parker on 12/7/23
// Modified for general send_msg + executeCommand by Shayahn Mirfendereski 10/30/24
// Modified for executeEvent()
// Modified by Derrick 11/14/2024 at 5:49pm
#include "src/strikerController.h"
#include "src/logger.h"
#include <SPI.h>
#include "Ethernet.h" 
#include <EthernetUdp.h>
#include <ArduinoQueue.h>

// --- Global Objects ---
StrikerController* pController = nullptr;
EthernetUDP udp;

// --- Network Configuration ---
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };
IPAddress ip(10, 2, 1, 177);
unsigned int localPort = 8888;
char packetBuffer[2048]; // Buffer for one chunk (20 * 15 * 4 = 1200 bytes)

// --- Two-Stage Queue System ---
const int FLOATS_PER_POINT = 16;  // 15 motors + 1 control flag

// Define a simple structure to hold one trajectory point
// values[0..14] = motor positions/torques
// values[15]    = control flags (0 = normal, 1 = force torque mode for pressers)
struct TrajectoryPoint {
  float values[FLOATS_PER_POINT];
};

// Stage 1: A large software buffer to hold incoming data from the network.
// Sized to hold 5 chunks (100 points) to absorb network jitter.
ArduinoQueue<TrajectoryPoint> g_softwareBufferQueue(100);

// --- Timing Control ---
unsigned long g_previousTime = 0;
const unsigned long g_interval = 1; // 5 milliseconds per point

void setup() {
    Serial.begin(115200);
    LOG_LOG("--- GuitarBot Controller ---");

    Ethernet.init(10);
    Ethernet.begin(mac, ip);
    delay(1000);
    udp.begin(localPort);
    //LOG_LOG("Listening for UDP packets on %s:%d", Ethernet.localIP().toString().c_str(), localPort);

    // Initialize Robot Controller
    pController = StrikerController::createInstance();
    pController->init(MotorSpec::EC45_Slider);
    pController->start();
    LOG_LOG("Controller Ready. Listening for Points.");
}

void loop() {
    // 1. Always check for new data chunks from the network.
    ethernetEvent();

    // 2. Run the feeder logic every 5ms.
    unsigned long currentTime = millis();
    if (currentTime - g_previousTime >= g_interval) {
        g_previousTime = currentTime;

        // If there are points in our software buffer
        if (!g_softwareBufferQueue.isEmpty()) {
            // pull one point out of the Stage 1 buffer.
            TrajectoryPoint pointToProcess = g_softwareBufferQueue.dequeue();
            
            // feed it to the controller's processing function.
            if (pController != nullptr) {
                pController->processTrajPoints(pointToProcess.values);
            }
        }
    }
}

void ethernetEvent() {
    int packetSize = udp.parsePacket();
    if (packetSize > 0) {
        udp.read(packetBuffer, packetSize);
        
        const int BYTES_PER_NEW_POINT = FLOATS_PER_POINT * sizeof(float);      // 16 floats = 64 bytes
        const int BYTES_PER_LEGACY_POINT = 15 * sizeof(float);                  // 15 floats = 60 bytes

        bool isNewFormat = (packetSize % BYTES_PER_NEW_POINT == 0);
        bool isLegacyFormat = (!isNewFormat && packetSize % BYTES_PER_LEGACY_POINT == 0);

        if (isNewFormat || isLegacyFormat) {
            int bytesPerPoint = isNewFormat ? BYTES_PER_NEW_POINT : BYTES_PER_LEGACY_POINT;
            int numPoints = packetSize / bytesPerPoint;

            if (isLegacyFormat) {
                LOG_LOG("Legacy 15-float packet detected. Padding flag to 0.");
            }
            LOG_LOG("Received chunk with %d points. Adding to software buffer.", numPoints);

            for (int i = 0; i < numPoints; i++) {
                TrajectoryPoint tempPoint;
                if (isLegacyFormat) {
                    // Copy 15 motor values, set control flag to 0 (normal mode)
                    memcpy(tempPoint.values, packetBuffer + (i * bytesPerPoint), bytesPerPoint);
                    tempPoint.values[15] = 0.0f;
                } else {
                    memcpy(tempPoint.values, packetBuffer + (i * bytesPerPoint), bytesPerPoint);
                }
                g_softwareBufferQueue.enqueue(tempPoint);
            }
        } else {
            LOG_ERROR("Received corrupted packet. Size %d is not divisible by point size %d or legacy size %d.", packetSize, BYTES_PER_NEW_POINT, BYTES_PER_LEGACY_POINT);
        }
    }
}