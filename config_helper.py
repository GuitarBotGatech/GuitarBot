#!/usr/bin/env python3
"""
config_helper.py - Helper functions for sending /Config messages

This module provides easy-to-use functions for updating GuitarBot
runtime configuration without restarting the receiver.

Example usage:
    from config_helper import ConfigHelper
    
    config = ConfigHelper()
    config.disable_graph()  # Turn off plotting for faster execution
    config.set_unpress_after(True)  # Release after each note
    config.faster_motion()  # Speed up all movements
"""

from pythonosc import udp_client
import time


class ConfigHelper:
    """Helper class for sending /Config OSC messages."""
    
    def __init__(self, ip="127.0.0.1", port=12000):
        """
        Initialize config helper.
        
        Args:
            ip: OSC server IP address
            port: OSC server port
        """
        self.client = udp_client.SimpleUDPClient(ip, port)
        self.ip = ip
        self.port = port
        print(f"ConfigHelper connected to {ip}:{port}")
    
    def send(self, flag_name, value):
        """Send a config message."""
        self.client.send_message("/Config", [flag_name, value])
        print(f"Config: {flag_name} = {value}")
        time.sleep(0.05)  # Small delay for message processing
    
    # === Graphing ===
    
    def enable_graph(self):
        """Enable trajectory plotting (tu.graph = True)."""
        self.send("graph", True)
    
    def disable_graph(self):
        """Disable trajectory plotting (tu.graph = False)."""
        self.send("graph", False)
    
    # === Behavioral Flags ===
    
    def set_unpress_after(self, enabled):
        """
        Control presser release after pluck.
        
        Args:
            enabled: If True, presser returns to -650 after pluck
        """
        self.send("unpress_after", enabled)
    
    def set_force_adjustment_only(self, enabled):
        """
        Control force adjustment behavior.
        
        Args:
            enabled: If True, skip unpress phase when adjusting force
        """
        self.send("force_adjustment_only", enabled)
    
    # === Timing Parameters ===
    
    def set_blend_percent(self, value):
        """
        Set trajectory blend percentage (smoothness).
        
        Args:
            value: Blend percentage (0.0 = linear, 1.0 = very smooth)
        """
        if not 0.0 <= value <= 1.0:
            print(f"Warning: blend_percent should be 0.0-1.0 (got {value})")
        self.send("blend_percent", value)
    
    def set_presser_points(self, points):
        """
        Set presser interpolation points.
        
        Args:
            points: Number of points (duration = points * 5ms)
        """
        self.send("presser_points", points)
    
    def set_slider_points(self, points):
        """
        Set slider motion points.
        
        Args:
            points: Number of points (duration = points * 5ms)
        """
        self.send("slider_points", points)
    
    def set_picker_points(self, points):
        """
        Set picker pluck motion points.
        
        Args:
            points: Number of points (duration = points * 5ms)
        """
        self.send("picker_points", points)
    
    def set_lh_prep_time(self, seconds):
        """
        Set left hand prep time before pick.
        
        Args:
            seconds: Prep time in seconds
        """
        self.send("lh_prep_time", seconds)
    
    # === Presets ===
    
    def faster_motion(self):
        """Speed up all movements by reducing interpolation points."""
        print("\n=== Setting Faster Motion Preset ===")
        self.set_presser_points(5)   # 25ms (was 50ms)
        self.set_slider_points(20)   # 100ms (was 200ms)
        self.set_picker_points(6)    # 30ms (was 55ms)
        print("Motion speed increased!\n")
    
    def slower_motion(self):
        """Slow down all movements for precision."""
        print("\n=== Setting Slower Motion Preset ===")
        self.set_presser_points(20)  # 100ms
        self.set_slider_points(80)   # 400ms
        self.set_picker_points(22)   # 110ms
        print("Motion speed decreased for precision!\n")
    
    def default_motion(self):
        """Reset to default motion parameters."""
        print("\n=== Resetting to Default Motion ===")
        self.set_presser_points(10)  # 50ms
        self.set_slider_points(40)   # 200ms
        self.set_picker_points(11)   # 55ms
        self.set_blend_percent(0.2)
        self.set_lh_prep_time(0.450)
        print("Default motion restored!\n")
    
    def testing_mode(self):
        """Configure for testing: fast, no graphs, auto-release."""
        print("\n=== Entering Testing Mode ===")
        self.disable_graph()
        self.set_unpress_after(True)
        self.faster_motion()
        print("Testing mode enabled!\n")
    
    def performance_mode(self):
        """Configure for performance: default timing, no graphs."""
        print("\n=== Entering Performance Mode ===")
        self.disable_graph()
        self.set_unpress_after(False)
        self.default_motion()
        print("Performance mode enabled!\n")
    
    def debug_mode(self):
        """Configure for debugging: slower, with graphs."""
        print("\n=== Entering Debug Mode ===")
        self.enable_graph()
        self.slower_motion()
        print("Debug mode enabled!\n")
    
    # === Info ===
    
    def print_available_flags(self):
        """Print all available configuration flags."""
        print("\n" + "="*60)
        print("Available Configuration Flags")
        print("="*60)
        print("\nBoolean Flags:")
        print("  graph                  - Enable/disable trajectory plotting")
        print("  unpress_after          - Release presser after pluck")
        print("  force_adjustment_only  - Skip unpress phase for force tests")
        print("\nNumeric Flags:")
        print("  blend_percent (0.0-1.0) - Trajectory smoothness")
        print("  presser_points (int)    - Presser motion duration")
        print("  slider_points (int)     - Slider motion duration")
        print("  picker_points (int)     - Picker pluck duration")
        print("  lh_prep_time (float)    - LH prep time (seconds)")
        print("\nPresets:")
        print("  .faster_motion()    - Speed up all movements")
        print("  .slower_motion()    - Slow down for precision")
        print("  .default_motion()   - Reset to defaults")
        print("  .testing_mode()     - Fast, no graphs, auto-release")
        print("  .performance_mode() - Default timing, no graphs")
        print("  .debug_mode()       - Slow motion with graphs")
        print("="*60 + "\n")


# Convenience functions for quick scripting

def quick_config(ip="127.0.0.1", port=12000):
    """Get a ConfigHelper instance quickly."""
    return ConfigHelper(ip, port)


def disable_graphs():
    """Quick function to disable graphing."""
    config = quick_config()
    config.disable_graph()


def enable_graphs():
    """Quick function to enable graphing."""
    config = quick_config()
    config.enable_graph()


def testing_mode():
    """Quick function to enter testing mode."""
    config = quick_config()
    config.testing_mode()


def performance_mode():
    """Quick function to enter performance mode."""
    config = quick_config()
    config.performance_mode()


# === Example Usage ===

if __name__ == "__main__":
    print("ConfigHelper Example Usage\n")
    
    # Create helper
    config = ConfigHelper()
    
    # Show available options
    config.print_available_flags()
    
    # Example: Switch to testing mode
    print("Example 1: Switch to testing mode")
    config.testing_mode()
    time.sleep(1)
    
    # Example: Custom configuration
    print("Example 2: Custom configuration")
    config.disable_graph()
    config.set_blend_percent(0.3)
    config.set_presser_points(15)
    time.sleep(1)
    
    # Example: Reset to defaults
    print("Example 3: Reset to defaults")
    config.default_motion()
    config.enable_graph()
    
    print("\nDone! You can now use ConfigHelper in your scripts:")
    print("  from config_helper import ConfigHelper")
    print("  config = ConfigHelper()")
    print("  config.testing_mode()")
