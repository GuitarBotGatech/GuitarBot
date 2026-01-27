#!/usr/bin/env python3
"""
Quick Start: /Config Messages
==============================

This is the fastest way to get started with runtime configuration.
"""

from pythonosc import udp_client

# Connect to the receiver
client = udp_client.SimpleUDPClient("127.0.0.1", 12000)

# ============================================================
# COMMON CONFIGURATIONS
# ============================================================

# 1. DISABLE GRAPHS (for faster execution)
client.send_message("/Config", ["graph", False])

# 2. ENABLE AUTO-RELEASE (presser returns to -650 after pluck)
client.send_message("/Config", ["unpress_after", True])

# 3. SPEED UP MOTION (reduce interpolation points)
client.send_message("/Config", ["presser_points", 5])   # 25ms instead of 50ms
client.send_message("/Config", ["slider_points", 20])   # 100ms instead of 200ms
client.send_message("/Config", ["picker_points", 6])    # 30ms instead of 55ms

# 4. SMOOTHER TRAJECTORIES (increase blend)
client.send_message("/Config", ["blend_percent", 0.4])  # More gradual accel/decel

# 5. REDUCE COORDINATION DELAY
client.send_message("/Config", ["lh_prep_time", 0.3])   # 300ms instead of 450ms

# ============================================================
# TESTING PRESETS
# ============================================================

# FAST TESTING MODE: No graphs, fast motion, auto-release
client.send_message("/Config", ["graph", False])
client.send_message("/Config", ["unpress_after", True])
client.send_message("/Config", ["presser_points", 5])
client.send_message("/Config", ["slider_points", 20])
client.send_message("/Config", ["picker_points", 6])
print("✓ Fast testing mode enabled")

# PERFORMANCE MODE: No graphs, default timing
client.send_message("/Config", ["graph", False])
client.send_message("/Config", ["unpress_after", False])
client.send_message("/Config", ["presser_points", 10])
client.send_message("/Config", ["slider_points", 40])
client.send_message("/Config", ["picker_points", 11])
print("✓ Performance mode enabled")

# DEBUG MODE: Graphs on, slower motion
client.send_message("/Config", ["graph", True])
client.send_message("/Config", ["presser_points", 20])
client.send_message("/Config", ["slider_points", 80])
client.send_message("/Config", ["picker_points", 22])
print("✓ Debug mode enabled")

# ============================================================
# RESET TO DEFAULTS
# ============================================================
client.send_message("/Config", ["graph", True])
client.send_message("/Config", ["unpress_after", False])
client.send_message("/Config", ["force_adjustment_only", False])
client.send_message("/Config", ["blend_percent", 0.2])
client.send_message("/Config", ["presser_points", 10])
client.send_message("/Config", ["slider_points", 40])
client.send_message("/Config", ["picker_points", 11])
client.send_message("/Config", ["lh_prep_time", 0.45])
print("✓ Reset to defaults")

# ============================================================
# OR USE THE HELPER (RECOMMENDED)
# ============================================================

from config_helper import ConfigHelper

config = ConfigHelper()

# Single command presets
config.testing_mode()      # Fast, no graphs, auto-release
config.performance_mode()  # Default timing, no graphs  
config.debug_mode()        # Slow with graphs
config.default_motion()    # Reset to defaults

# Individual settings
config.disable_graph()
config.set_unpress_after(True)
config.faster_motion()
config.set_blend_percent(0.3)

print("\n✓ Configuration complete!")
