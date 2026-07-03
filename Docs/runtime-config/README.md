# Runtime Configuration with /Config Messages

The `/Config` OSC message allows you to dynamically update runtime flags and tuning parameters in `OSC_Message_Receiver.py` without restarting the server. This is useful for:

- **Testing different motion speeds** during development
- **Enabling/disabling graphs** to speed up execution
- **Adjusting behavioral flags** like `unpress_after`
- **Fine-tuning trajectory timing** in real-time

## Message Format

```
/Config <flag_name> <value>
```

Where:
- `flag_name` is a string (e.g., `"graph"`, `"blend_percent"`)
- `value` is the new value (boolean, int, or float depending on flag)

## Available Flags

### Boolean Flags

| Flag | Type | Description | Default |
|------|------|-------------|---------|
| `graph` | bool | Enable/disable trajectory plotting (`tu.graph`) | `True` |
| `unpress_after` | bool | Release presser to -650 after pluck completes | `False` |
| `force_adjustment_only` | bool | Skip unpress phase when adjusting force (for testing) | `False` |

### Numeric Flags

| Flag | Type | Range | Description | Default |
|------|------|-------|-------------|---------|
| `blend_percent` | float | 0.0-1.0 | Trajectory blend percentage (smoothness) | `0.2` |
| `presser_points` | int | >0 | Presser interpolation points (× 5ms) | `10` (50ms) |
| `slider_points` | int | >0 | Slider motion points (× 5ms) | `40` (200ms) |
| `picker_points` | int | >0 | Picker pluck motion points (× 5ms) | `11` (55ms) |
| `lh_prep_time` | float | ≥0.0 | Left hand prep time before pick (seconds) | `0.45` |

## Examples

### Python (using pythonosc)

```python
from pythonosc import udp_client

client = udp_client.SimpleUDPClient("127.0.0.1", 12000)

# Disable graphing for faster execution
client.send_message("/Config", ["graph", False])

# Enable auto-release after pluck
client.send_message("/Config", ["unpress_after", True])

# Make motion smoother
client.send_message("/Config", ["blend_percent", 0.4])

# Speed up presser motion
client.send_message("/Config", ["presser_points", 5])
```

### Using the ConfigHelper

We provide a convenient `ConfigHelper` class for easier configuration:

```python
from config_helper import ConfigHelper

config = ConfigHelper()

# Individual settings
config.disable_graph()
config.set_unpress_after(True)
config.set_blend_percent(0.3)

# Or use presets
config.testing_mode()      # Fast motion, no graphs, auto-release
config.performance_mode()  # Default timing, no graphs
config.debug_mode()        # Slow motion with graphs
```

### Command-line (using oscsend)

```bash
# Disable graphing
oscsend localhost 12000 /Config s graph i 0

# Set blend percentage to 0.3
oscsend localhost 12000 /Config s blend_percent f 0.3

# Set presser points to 15
oscsend localhost 12000 /Config s presser_points i 15
```

## Use Cases

### 1. Testing Different Motion Speeds

```python
from config_helper import ConfigHelper
from pythonosc import udp_client

config = ConfigHelper()
client = udp_client.SimpleUDPClient("127.0.0.1", 12000)

# Test with fast motion
config.faster_motion()
client.send_message("/Fret", [45, 0.7])
time.sleep(1)

# Test with slow motion
config.slower_motion()
client.send_message("/Fret", [45, 0.7])
time.sleep(2)
```

### 2. Force Testing Without Motion

```python
config = ConfigHelper()
client = udp_client.SimpleUDPClient("127.0.0.1", 12000)

# Fret the note once
client.send_message("/Fret", [50, 0.5])
time.sleep(2)

# Enable force-adjustment-only mode
config.set_force_adjustment_only(True)

# Now test different forces quickly (no unpress/slide)
for force in [0.6, 0.7, 0.8, 0.9]:
    client.send_message("/Fret", [50, force])
    time.sleep(0.3)  # Just the force change
```

### 3. Disable Graphs for Performance

```python
from config_helper import disable_graphs

# Quick function to turn off graphs
disable_graphs()

# Now run your test with faster execution
# (no matplotlib rendering overhead)
```

## Scripts Included

- **`test_config_messages.py`** - Tests all config flags with examples
- **`config_helper.py`** - Helper class with convenient methods and presets
- **`example_config_workflow.py`** - Real-world workflow examples

## Running the Tests

1. Start the receiver in one terminal:
   ```bash
   python OSC_Message_Receiver.py
   ```

2. Run a test script in another terminal:
   ```bash
   python test_config_messages.py
   ```

3. Or use the helper in your own scripts:
   ```python
   from config_helper import ConfigHelper
   
   config = ConfigHelper()
   config.testing_mode()
   # Your test code here...
   ```

## Implementation Details

The `/Config` processor runs in a dedicated thread and updates:
- Global variables in `tune.py` (e.g., `tu.graph`, `tu.TRAJECTORY_BLEND_PERCENT`)
- Module-level flags in `OSC_Message_Receiver.py` (e.g., `unpress_after_flag`)

Changes take effect **immediately** for new trajectories but don't affect trajectories already in progress.

## Error Handling

Invalid configurations are rejected with error messages:

```python
# Out of range value
client.send_message("/Config", ["blend_percent", 2.0])
# Output: ✗ Error: blend_percent must be 0.0-1.0 (got 2.0)

# Unknown flag
client.send_message("/Config", ["invalid_flag", True])
# Output: ✗ Unknown flag: invalid_flag

# Invalid type
client.send_message("/Config", ["presser_points", "not_a_number"])
# Output: ✗ Error: Invalid int value: not_a_number
```

## Notes

- **Thread-safe**: Config changes are processed in a dedicated thread
- **Immediate effect**: New trajectories use updated parameters immediately
- **No restart required**: All changes happen at runtime
- **Validation**: Invalid values are rejected with clear error messages
- **Presets**: Use `ConfigHelper` presets for common configurations

## See Also

- `tune.py` - Source of default parameter values
- `OSC_Message_Receiver.py` - Config processor implementation
- `BothHandsParser.py` - Uses `unpress_after` flag
- `LeftHandParser.py` - Uses `force_adjustment_only` flag
