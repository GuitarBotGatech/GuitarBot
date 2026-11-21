#ifndef TUNE_H
#define TUNE_H

// Auto-generated from tuning/tune.py — DO NOT EDIT BY HAND
// Run: python -m tuning.gen_tune_h  (or python -m tuning.tune)

const float start_state_PICK[6] = {-6.0f, 4.2f, -3.6f, 4.3f, 4.0f, -5.1f};
const float start_state_PICK_DOWN[6] = {-2.75f, 0.6f, -0.7f, 0.95f, 1.1f, -2.0f};
const int motor_id_PICK[6] = {13, 14, 15, 16, 17, 18};
const int home_offset_SLIDE = 50000;
const int home_offset_PRESS = -25;
const int home_offset_PICK = 0;
const uint32_t current_control_SLIDE[2] = {1575853, 4837093};
const uint32_t current_control_PICK[2] = {1042729, 2976309};
const uint32_t current_control_PRESS[2] = {3456649, 10257};
const uint32_t pos_control_SLIDE[5] = {6933308, 139254287, 104848, 10219, 637};
const uint32_t pos_control_PICK[5] = {18462573, 157853228, 170004, 9945, 585};
const uint32_t pos_control_PRESS[5] = {200000, 905480, 2643, 507, 36};
const float mm_to_enc_conversion_factor = 9.4f;
const int presser_cal_frets[3] = {0, 4, 9};
const int presser_cal_torque = 500;
const int presser_cal_slider_ticks[3][6] = {{0, 0, 0, 0, 0, 0}, {-21502, 21502, 21502, -21502, -21502, 21502}, {-48082, 48082, 48082, -48082, -48082, 48082}};

#endif // TUNE_H
