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
#define NUM_PLUCKERS 2
#define NUM_STRUMMER_SLIDERS 1
#define NUM_STRUMMER_PICKERS 1
#define NUM_MOTORS NUM_PRESSERS+NUM_STRIKERS+NUM_PLUCKERS+NUM_STRUMMER_SLIDERS+NUM_STRUMMER_PICKERS
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

#define CLEAR_FAULT_TIMER_INTERVAL 100   // ms



#define MAX_STRIKER_ANGLE_DEG 180
#endif // SHIMON_DEF_H
