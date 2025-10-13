/*
 * EncoderFeedbackCollector.h
 * 
 * Arduino/OpenCR integration for collecting encoder feedback from EPOS4 motors
 * and transmitting to Python TrajectoryFeedbackAnalyzer via UDP.
 * 
 * Uses Ethernet UDP similar to networkHandler.h for consistency with existing system.
 * 
 */

#ifndef ENCODER_FEEDBACK_COLLECTOR_H
#define ENCODER_FEEDBACK_COLLECTOR_H

#include "epos4/epos4.h"
#include "striker.h"
#include "ErrorDef.h"
#include "logger.h"
#include "def.h"
#include <Ethernet.h>
#include <EthernetUdp.h>

// Feedback transmission settings
constexpr uint16_t FEEDBACK_PORT = 8889;
constexpr uint32_t FEEDBACK_INTERVAL_US = 5000; // 5ms = 200Hz
constexpr size_t MAX_FEEDBACK_BUFFER = 64;

// Encoder feedback packet structure
struct EncoderFeedbackPacket {
    uint8_t motor_id;           // Motor ID (1 byte)
    int32_t encoder_position;   // Current encoder position (4 bytes)
    uint16_t status_word;       // EPOS4 status word (2 bytes) 
    uint8_t checksum;           // Simple checksum (1 byte)
    
    // Calculate checksum
    uint8_t calculateChecksum() const {
        uint8_t sum = motor_id;
        sum += (encoder_position & 0xFF);
        sum += ((encoder_position >> 8) & 0xFF);
        sum += ((encoder_position >> 16) & 0xFF);
        sum += ((encoder_position >> 24) & 0xFF);
        sum += (status_word & 0xFF);
        sum += ((status_word >> 8) & 0xFF);
        return ~sum; // One's complement
    }
    
    bool isValidChecksum() const {
        return checksum == calculateChecksum();
    }
} __attribute__((packed));

class EncoderFeedbackCollector {
private:
    // Network configuration (similar to networkHandler.h)
    EthernetUDP udp_socket_;
    IPAddress python_host_;
    uint16_t python_port_;
    bool ethernet_initialized_;
    
    // MAC address for feedback collector (different from networkHandler.h)
    byte mac_[6] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xEE};
    
    // Timing control
    uint32_t last_transmission_us_;
    uint32_t transmission_interval_us_;
    
    // Data collection
    EncoderFeedbackPacket feedback_buffer_[MAX_FEEDBACK_BUFFER];
    size_t buffer_head_;
    size_t buffer_tail_;
    size_t buffer_count_;
    
    // Statistics
    uint32_t packets_sent_;
    uint32_t packets_lost_;
    uint32_t transmission_errors_;
    
    // Reference to striker controller for accessing motors
    StrikerController* striker_controller_;
    
public:
    EncoderFeedbackCollector(StrikerController* controller) 
        : striker_controller_(controller),
          python_host_(10, 2, 1, 100), // Default Python host IP
          python_port_(FEEDBACK_PORT),
          ethernet_initialized_(false),
          last_transmission_us_(0),
          transmission_interval_us_(FEEDBACK_INTERVAL_US),
          buffer_head_(0),
          buffer_tail_(0), 
          buffer_count_(0),
          packets_sent_(0),
          packets_lost_(0),
          transmission_errors_(0) {
    }
    
    /**
     * Initialize Ethernet connection and UDP socket (similar to networkHandler.h)
     */
    Error_t initialize(IPAddress python_host, uint16_t python_port = FEEDBACK_PORT) {
        python_host_ = python_host;
        python_port_ = python_port;
        
        // Note: Ethernet should already be initialized by networkHandler.h
        // We just need to start our UDP socket on a different port
        
        // Check if Ethernet is already initialized
        if (Ethernet.hardwareStatus() == EthernetNoHardware) {
            LOG_ERROR("Ethernet hardware not found for feedback collector");
            return kFileOpenError;
        }
        
        if (Ethernet.linkStatus() == LinkOFF) {
            LOG_ERROR("Ethernet cable not connected for feedback collector");
            return kFileOpenError;
        }
        
        // Start UDP on feedback port
        if (!udp_socket_.begin(FEEDBACK_PORT)) {
            LOG_ERROR("Failed to initialize UDP socket for feedback");
            return kNetworkError;
        }
        
        ethernet_initialized_ = true;
        
        LOG_LOG("Encoder feedback collector initialized");
        LOG_LOG("Local IP: %s", Ethernet.localIP());
        LOG_LOG("Sending feedback to: %d.%d.%d.%d:%d", python_host[0], python_host[1], python_host[2], python_host[3], python_port_);
        LOG_LOG("Transmission interval: %d us", transmission_interval_us_);
        
        return kNoError;
    }
    
    /**
     * Close UDP connection
     */
    void close() {
        if (ethernet_initialized_) {
            udp_socket_.stop();
            ethernet_initialized_ = false;
        }
    }
    
    /**
     * Set transmission interval in microseconds
     */
    void setTransmissionInterval(uint32_t interval_us) {
        transmission_interval_us_ = interval_us;
    }
    
    /**
     * Transmit any buffered encoder data (non-blocking)
     * Safe to call from main loop, NOT from IRQ handlers
     */
    void transmitBufferedData() {
        if (!ethernet_initialized_) {
            return;
        }
        
        // Only transmit if we have data and it's time
        uint32_t current_time_us = micros();
        if (buffer_count_ > 0 && (current_time_us - last_transmission_us_) >= transmission_interval_us_) {
            transmitBuffer();
            last_transmission_us_ = current_time_us;
        }
    }
    
    /**
     * SLOW: Collect encoder feedback from all active motors
     * This should be called from the main control loop, NOT from IRQ handlers
     */
    void collectFeedback() {
        if (!ethernet_initialized_ || !striker_controller_) {
            return;
        }
        
        uint32_t current_time_us = micros();
        
        // Check if it's time to collect/transmit
        if (current_time_us - last_transmission_us_ < transmission_interval_us_) {
            return;
        }
        
        // Collect feedback from all motors
        for (int motor_id = 1; motor_id <= NUM_MOTORS; motor_id++) {
            Striker& striker = striker_controller_->getStriker(motor_id);
            
            // Get current encoder position from Striker (using public methods only)
            int32_t encoder_pos = striker.getPosition_ticks();
            uint16_t status_word = striker.getStatusWord();
            
            // Create feedback packet
            EncoderFeedbackPacket packet;
            packet.motor_id = motor_id;
            packet.encoder_position = encoder_pos;
            packet.status_word = status_word;
            packet.checksum = packet.calculateChecksum();
            
            // Add to buffer
            addToBuffer(packet);
        }
        
        // Transmit buffered data
        transmitBuffer();
        
        last_transmission_us_ = current_time_us;
    }
    
    /**
     * Collect feedback for specific motor ID
     */
    void collectMotorFeedback(uint8_t motor_id) {
        if (!ethernet_initialized_ || !striker_controller_ || !striker_controller_->isValidMotorId(motor_id)) {
            return;
        }
        
        Striker& striker = striker_controller_->getStriker(motor_id);
        
        // Get encoder feedback (using public methods only)
        int32_t encoder_pos = striker.getPosition_ticks();
        uint16_t status_word = striker.getStatusWord();
        
        // Create and transmit packet immediately
        EncoderFeedbackPacket packet;
        packet.motor_id = motor_id;
        packet.encoder_position = encoder_pos;
        packet.status_word = status_word;
        packet.checksum = packet.calculateChecksum();
        
        transmitPacket(packet);
    }
    
    /**
     * Enable continuous feedback collection for trajectory execution
     */
    void startTrajectoryFeedback() {
        Serial.println("Starting trajectory feedback collection");
        last_transmission_us_ = micros();
        
        // Reset statistics
        packets_sent_ = 0;
        packets_lost_ = 0;
        transmission_errors_ = 0;
        
        // Clear buffer
        buffer_head_ = 0;
        buffer_tail_ = 0;
        buffer_count_ = 0;
    }
    
    /**
     * Stop continuous feedback collection
     */
    void stopTrajectoryFeedback() {
        // Transmit any remaining buffered data
        transmitBuffer();
        
        Serial.printf("Trajectory feedback stopped. Stats:\n");
        Serial.printf("  Packets sent: %d\n", packets_sent_);
        Serial.printf("  Packets lost: %d\n", packets_lost_);
        Serial.printf("  Transmission errors: %d\n", transmission_errors_);
        
        if (packets_sent_ > 0) {
            float loss_rate = (float)packets_lost_ / packets_sent_ * 100.0f;
            Serial.printf("  Loss rate: %.2f%%\n", loss_rate);
        }
    }
    
    /**
     * Get transmission statistics
     */
    void getStatistics(uint32_t& packets_sent, uint32_t& packets_lost, 
                      uint32_t& transmission_errors) const {
        packets_sent = packets_sent_;
        packets_lost = packets_lost_;
        transmission_errors = transmission_errors_;
    }
    
    /**
     * FAST: Non-blocking feedback capture for time-critical contexts
     * Safe to call from RPDOTimerIRQHandler - only captures data, no transmission
     */
    void captureMotorData(uint8_t motor_id) {
        if (!ethernet_initialized_ || !striker_controller_ || !striker_controller_->isValidMotorId(motor_id)) {
            return;
        }
        
        // Quick data capture - no network I/O
        Striker& striker = striker_controller_->getStriker(motor_id);
        int32_t encoder_pos = striker.getPosition_ticks();
        uint16_t status_word = striker.getStatusWord();
        
        EncoderFeedbackPacket packet;
        packet.motor_id = motor_id;
        packet.encoder_position = encoder_pos;
        packet.status_word = status_word;
        packet.checksum = packet.calculateChecksum();
        
        // Add to buffer only - no transmission
        addToBuffer(packet);
    }
    
    /**
     * SLOW: Integration point with existing PDO message processing
     * Call this from strikerController PDO callback (when not in IRQ context)
     */
    void onPDOMessageReceived(uint8_t motor_id, const can_message_t& msg) {
        // This allows us to collect encoder feedback immediately when
        // PDO messages are received, ensuring minimal latency
        
        if (!ethernet_initialized_ || !striker_controller_->isValidMotorId(motor_id)) {
            return;
        }
        
        // Extract encoder position directly from PDO message
        // (This mirrors the logic in Epos4::PDO_processMsg)
        int32_t encoder_position = (((msg.data[5] & 0xFF) << 24) + 
                                   ((msg.data[4] & 0xFF) << 16) + 
                                   ((msg.data[3] & 0xFF) << 8) + 
                                   msg.data[2]);
        
        uint16_t status_word = ((msg.data[1] & 0xFF) << 8) + msg.data[0];
        
        // Apply direction multiplier if needed
        Striker& striker = striker_controller_->getStriker(motor_id);
        if (striker.isInverted()) {
            encoder_position *= -1;
        }
        
        // Create and transmit packet
        EncoderFeedbackPacket packet;
        packet.motor_id = motor_id;
        packet.encoder_position = encoder_position;
        packet.status_word = status_word;
        packet.checksum = packet.calculateChecksum();
        
        transmitPacket(packet);
    }
    
private:
    /**
     * Add packet to transmission buffer
     */
    void addToBuffer(const EncoderFeedbackPacket& packet) {
        if (buffer_count_ >= MAX_FEEDBACK_BUFFER) {
            packets_lost_++;
            return; // Buffer full, drop packet
        }
        
        feedback_buffer_[buffer_head_] = packet;
        buffer_head_ = (buffer_head_ + 1) % MAX_FEEDBACK_BUFFER;
        buffer_count_++;
    }
    
    /**
     * Transmit all buffered packets
     */
    void transmitBuffer() {
        while (buffer_count_ > 0) {
            EncoderFeedbackPacket& packet = feedback_buffer_[buffer_tail_];
            
            if (transmitPacket(packet)) {
                buffer_tail_ = (buffer_tail_ + 1) % MAX_FEEDBACK_BUFFER;
                buffer_count_--;
            } else {
                break; // Stop on transmission error
            }
        }
    }
    
    /**
     * Transmit single packet via UDP (similar to networkHandler.h pattern)
     */
    bool transmitPacket(const EncoderFeedbackPacket& packet) {
        if (!ethernet_initialized_) {
            transmission_errors_++;
            return false;
        }
        
        // Begin UDP packet to Python host
        int result = udp_socket_.beginPacket(python_host_, python_port_);
        if (result == 0) {
            transmission_errors_++;
            return false;
        }
        
        // Write packet data
        size_t bytes_written = udp_socket_.write((const uint8_t*)&packet, sizeof(packet));
        
        // End and send packet
        result = udp_socket_.endPacket();
        
        if (result == 1 && bytes_written == sizeof(packet)) {
            packets_sent_++;
            return true;
        } else {
            transmission_errors_++;
            return false;
        }
    }
};

/**
 * Integration macros for existing code
 */

// Add this to strikerController.h initialization
#define INIT_ENCODER_FEEDBACK_COLLECTOR() \
    g_feedback_collector = new EncoderFeedbackCollector(this); \
    IPAddress python_ip(10, 2, 1, 100); \
    if (g_feedback_collector->initialize(python_ip) != kNoError) { \
        LOG_ERROR("Failed to initialize encoder feedback collector"); \
        delete g_feedback_collector; \
        g_feedback_collector = nullptr; \
    }

/**
 * TIMING-SAFE INTEGRATION MACROS
 */

// FAST: Safe for IRQ handlers - only captures data, no network I/O
#define CAPTURE_MOTOR_FEEDBACK(motor_id) \
    if (g_feedback_collector) { \
        g_feedback_collector->captureMotorData(motor_id); \
    }

// FAST: Safe for IRQ - transmit buffered data (non-blocking check)
#define TRANSMIT_FEEDBACK_BUFFER() \
    if (g_feedback_collector) { \
        g_feedback_collector->transmitBufferedData(); \
    }

// SLOW: Full collection - only call from main loop, NOT IRQ handlers
#define COLLECT_ENCODER_FEEDBACK_SAFE() \
    if (g_feedback_collector) { \
        g_feedback_collector->collectFeedback(); \
    }

// SLOW: PDO message processing - only call from non-IRQ PDO callbacks
#define ON_PDO_MESSAGE_RECEIVED(nodeID, msg) \
    if (g_feedback_collector) { \
        g_feedback_collector->onPDOMessageReceived(nodeID, *arg); \
    }


extern EncoderFeedbackCollector* g_feedback_collector;

#endif // ENCODER_FEEDBACK_COLLECTOR_H