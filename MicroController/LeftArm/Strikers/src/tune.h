#ifndef TUNE_H
#define TUNE_H

// Auto-generated from tune.py — DO NOT EDIT BY HAND
// Run gen_tune_h.py or tune.py to regenerate.

const float start_state_PICK[3] = {7.3f, 5.4f, 5.8f};
const int motor_id_PICK[3] = {13, 14, 15};
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

#endif // TUNE_H