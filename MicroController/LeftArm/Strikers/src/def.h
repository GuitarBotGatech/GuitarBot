//
// Created by Raghavasimhan Sankaranarayanan on 03/30/22.
//

#ifndef SHIMON_DEF_H
#define SHIMON_DEF_H

#define IP_ADDR "10.2.1.177"
#define MASTER_ADDR "10.2.1.1"
#define PORT 8888
#define CS_PIN 10
#define MAX_BUFFER_SIZE 1024
//change num pressers, TRACE_ME
#define NUM_STRIKERS 6
#define NUM_PRESSERS 6
#define NUM_PLUCKERS 6
#define NUM_STRUMMER_SLIDERS 0
#define NUM_STRUMMER_PICKERS 0
#define NUM_MOTORS NUM_STRIKERS+NUM_PRESSERS+NUM_STRUMMER_SLIDERS+NUM_STRUMMER_PICKERS+NUM_PLUCKERS
#define NUT_POS 0
#define NUM_BYTES_PER_VALUE sizeof(uint16_t)

#define ENCODER_DIR 1


const int kStrikerDirection[13] = { 0, 0, 1, 0, 0, 1, 1, 1, 0,0,0,0,0 }; // 0 is normal, 1 is flipped, idx 0 is dummy
const int FRET_LENGTHS[10] = {0, 43, 76, 107, 134, 163, 187, 210, 234, 256};

#define HOME_POSITION 25 // Deg
#define P2P_MULT 100.f
#define MAX_TRAJ_POINTS 20
#define SCALE_LENGTH 645 //mm
#define NUM_POINTS_IN_TRAJ_FOR_HIT 4  // Make sure Hit > up
#define NUM_POINTS_IN_TRAJ_FOR_UP 0
#define DISCONTINUITY_THRESHOLD 10000
#define BUFFER_TIME 1

// --- Presser mode state machine ---
// Encoder position (ticks) at or below which a presser is considered fully
// released and can safely switch from torque mode to position-hold at 0.
#define PRESSER_RELEASED_POS_THRESHOLD 15
// Number of consecutive PDO cycles the op-mode switch frame is re-sent after a
// mode change. The switch is fire-and-forget CAN; redundant sends make a single
// lost/failed frame a non-event.
#define PRESSER_MODE_RESEND_CYCLES 3
// How often the main loop verifies actual drive op modes via SDO read-back.
#define PRESSER_MODE_VERIFY_INTERVAL_MS 500

#define CLEAR_FAULT_TIMER_INTERVAL 100   // ms



#define MAX_STRIKER_ANGLE_DEG 180
#endif // SHIMON_DEF_H
