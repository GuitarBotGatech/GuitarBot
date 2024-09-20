/*
*Author: Raghavasimhan Sankaranarayanan, Shayahn Mirfendereski
*Date: 09/10/2024
*/

#pragma once

#include <Ethernet.h>
#include <EthernetUdp.h>
#include "def.h"
#include "ErrorDef.h"
#include "logger.h"

class NetworkHandler {
public:
    NetworkHandler() = default;

    Error_t init(void(*packetAvailableCallback)(char* pPacket, size_t packetSize)) {
        m_packetAvailableCallback = packetAvailableCallback;
        Ethernet.init(CS_PIN);

        IPAddress ip;
        ip.fromString(IP_ADDR);

        // start the Ethernet
        Ethernet.begin(mac, ip);

        // Check for Ethernet hardware present
        if (Ethernet.hardwareStatus() == EthernetNoHardware) {
            LOG_ERROR("Ethernet shield was not found.  Sorry, can't run without hardware. :(");
            return kFileOpenError;  // similar to linux hardware us treated as a file
        }

        if (Ethernet.linkStatus() == LinkOFF) {
            LOG_ERROR("Ethernet cable is not connected.");
            return kFileOpenError;
        }

        // start UDP
        m_socket.begin(PORT);
        LOG_LOG("Server Listening...");
        return kNoError;
    }

    void close() {
        m_socket.stop();
    }

    void poll() {
        int packetSize = m_socket.parsePacket();
        if (packetSize) {
            // read the packet into packetBuffer and callback
            if (m_socket.read(m_packetBuffer, packetSize)) {
                m_packetAvailableCallback(m_packetBuffer, packetSize);
            }
        }
    }

private:
    // Enter a MAC address and IP address for your controller below.
    // The IP address will be dependent on your local network:
    byte mac[6] = {
      0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED
    };

    // An EthernetUDP instance to let us send and receive packets over UDP
    EthernetUDP m_socket;

    IPAddress masterIp;

    // buffers for receiving and sending data
    char m_packetBuffer[MAX_BUFFER_SIZE];   // buffer to hold incoming packet,

    void (*m_packetAvailableCallback)(char* pPacket, size_t packetSize);
};