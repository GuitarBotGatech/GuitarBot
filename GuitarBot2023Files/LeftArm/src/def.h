//
// Created by Raghavasimhan Sankaranarayanan on 03/30/22.
//

#ifndef SHIMON_DEF_H
#define SHIMON_DEF_H
// 1 for now, change to 6 later.
#define NUM_STRIKERS 1
#define NUM_PRESSERS 1


const int kStrikerDirection[9] = { 0, 0, 1, 0, 0, 1, 1, 1, 0 }; // 0 is normal, 1 is flipped, idx 0 is dummy

#define HOME_POSITION 25 // Deg

#define MAX_TRAJ_POINTS 5000
#define NUM_POINTS_IN_TRAJ_FOR_HIT 50  // Make sure Hit > up
#define NUM_POINTS_IN_TRAJ_FOR_UP 15

#define CLEAR_FAULT_TIMER_INTERVAL 100   // ms
//Step 1 Define Positions by degrees, like home position



#define MAX_STRIKER_ANGLE_DEG 180
#endif // SHIMON_DEF_H
