"""
EncoderUDPReceiver.py

Listens for encoder feedback UDP packets from the microcontroller and logs them.
Expected packet format matches EncoderFeedbackCollector.h (packed):
- uint8  motor_id
- int32  encoder_position (little-endian)
- uint16 status_word (little-endian)
- uint8  checksum (one's complement sum of prior fields)

By default, listens on 0.0.0.0:8889 and prints to console and optional CSV.

Usage:
  python -m EncoderFeedback.EncoderUDPReceiver --host 0.0.0.0 --port 8889 --csv encoder_log.csv
  python -m EncoderFeedback.EncoderUDPReceiver --duration 10 --csv run.csv --plot
"""
from __future__ import annotations
import argparse
import socket
import struct
import time
import csv
from typing import Optional, Dict, List
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import threading
from collections import defaultdict, deque

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8889

PACKET_STRUCT = struct.Struct("<B i H B")  # motor_id, encoder_position, status_word, checksum
PACKET_SIZE = PACKET_STRUCT.size  # 8 bytes


def calc_checksum(motor_id: int, encoder_pos: int, status_word: int) -> int:
    s = 0
    s = (s + (motor_id & 0xFF)) & 0xFF
    s = (s + (encoder_pos & 0xFF)) & 0xFF
    s = (s + ((encoder_pos >> 8) & 0xFF)) & 0xFF
    s = (s + ((encoder_pos >> 16) & 0xFF)) & 0xFF
    s = (s + ((encoder_pos >> 24) & 0xFF)) & 0xFF
    s = (s + (status_word & 0xFF)) & 0xFF
    s = (s + ((status_word >> 8) & 0xFF)) & 0xFF
    return (~s) & 0xFF


class EncoderPlotter:
    """Real-time plotter for encoder feedback data using Plotly."""
    
    def __init__(self, max_points: int = 1000, update_interval: float = 0.5):
        self.max_points = max_points
        self.update_interval = update_interval
        
        # Data storage: motor_id -> deque of (timestamp, encoder_pos, status_word, checksum_ok)
        self.motor_data: Dict[int, deque] = defaultdict(lambda: deque(maxlen=max_points))
        self.timestamps: deque = deque(maxlen=max_points)
        
        # Motor grouping for organized plots
        self.motor_groups = {
            'Sliders (1-6)': list(range(1, 7)),
            'Pressers (7-12)': list(range(7, 13)),
            'Pickers (13-15)': list(range(13, 16))
        }
        
        self.fig = None
        self.last_update = 0
        
    def add_data_point(self, timestamp: float, motor_id: int, encoder_pos: int, 
                      status_word: int, checksum_ok: bool):
        """Add new data point for a motor."""
        self.motor_data[motor_id].append((timestamp, encoder_pos, status_word, checksum_ok))
        
        # Update plot periodically
        if time.time() - self.last_update > self.update_interval:
            self.update_plot()
            self.last_update = time.time()
    
    def create_initial_plot(self):
        """Create the initial Plotly figure with subplots for motor groups."""
        self.fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=['Slider Motors (1-6)', 'Presser Motors (7-12)', 'Picker Motors (13-15)'],
            shared_xaxes=True,
            vertical_spacing=0.08
        )
        
        # Add empty traces for each motor
        for row, (group_name, motor_ids) in enumerate(zip(self.motor_groups.keys(), self.motor_groups.values()), 1):
            for motor_id in motor_ids:
                self.fig.add_trace(
                    go.Scatter(
                        x=[], y=[],
                        mode='lines+markers',
                        name=f'Motor {motor_id}',
                        line=dict(width=2),
                        marker=dict(size=3),
                        showlegend=(row == 1)  # Only show legend for first subplot
                    ),
                    row=row, col=1
                )
        
        self.fig.update_layout(
            title='Real-time Encoder Feedback',
            height=800,
            showlegend=True,
            hovermode='x unified',
            template='plotly_white'
        )
        
        self.fig.update_xaxes(title_text='Time (seconds)', row=3, col=1)
        self.fig.update_yaxes(title_text='Encoder Position (ticks)')
        
        # Show initial empty plot
        self.fig.show()
    
    def update_plot(self):
        """Update the plot with new data."""
        if self.fig is None:
            self.create_initial_plot()
            return
        
        # For real-time updates, we'll recreate the plot periodically
        # This is simpler than trying to update individual traces
        try:
            if self.fig is not None:
                # Clear and rebuild with latest data
                self.fig.data = []
                
                # Rebuild traces
                for row, (group_name, motor_ids) in enumerate(zip(self.motor_groups.keys(), self.motor_groups.values()), 1):
                    for motor_id in motor_ids:
                        if motor_id in self.motor_data and len(self.motor_data[motor_id]) > 0:
                            # Extract data for this motor
                            data_points = list(self.motor_data[motor_id])
                            if data_points:
                                timestamps = [dp[0] - data_points[0][0] for dp in data_points]  # Relative time
                                positions = [dp[1] for dp in data_points]
                                
                                # Separate good and bad checksum points
                                good_times = [t for t, dp in zip(timestamps, data_points) if dp[3]]
                                good_positions = [p for p, dp in zip(positions, data_points) if dp[3]]
                                
                                if good_times:
                                    self.fig.add_trace(
                                        go.Scatter(
                                            x=good_times, y=good_positions,
                                            mode='lines+markers',
                                            name=f'Motor {motor_id}',
                                            line=dict(width=2),
                                            marker=dict(size=3),
                                            showlegend=(row == 1)
                                        ),
                                        row=row, col=1
                                    )
        except Exception as e:
            # Don't let plotting errors crash the receiver
            print(f"Plot update error: {e}")
    
    def finalize_plot(self, title_suffix: str = ""):
        """Create final static plot after data collection is complete."""
        if not any(self.motor_data.values()):
            print("No data to plot")
            return
        
        # Create comprehensive final plot
        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=[
                'Slider Motors (1-6) - String Positioning',
                'Presser Motors (7-12) - Fret Pressing', 
                'Picker Motors (13-15) - String Plucking'
            ],
            shared_xaxes=True,
            vertical_spacing=0.08
        )
        
        # Add traces for each motor group
        for row, (group_name, motor_ids) in enumerate(zip(self.motor_groups.keys(), self.motor_groups.values()), 1):
            for motor_id in motor_ids:
                if motor_id in self.motor_data and len(self.motor_data[motor_id]) > 0:
                    data_points = list(self.motor_data[motor_id])
                    start_time = data_points[0][0]
                    timestamps = [dp[0] - start_time for dp in data_points]
                    positions = [dp[1] for dp in data_points]
                    
                    # Separate good and bad checksum points
                    good_times = [t for t, dp in zip(timestamps, data_points) if dp[3]]
                    good_positions = [p for p, dp in zip(positions, data_points) if dp[3]]
                    bad_times = [t for t, dp in zip(timestamps, data_points) if not dp[3]]
                    bad_positions = [p for p, dp in zip(positions, data_points) if not dp[3]]
                    
                    # Add good data points
                    if good_times:
                        fig.add_trace(
                            go.Scatter(
                                x=good_times, y=good_positions,
                                mode='lines+markers',
                                name=f'Motor {motor_id}',
                                line=dict(width=2),
                                marker=dict(size=3),
                                showlegend=(row == 1)
                            ),
                            row=row, col=1
                        )
                    
                    # Add bad data points (red markers)
                    if bad_times:
                        fig.add_trace(
                            go.Scatter(
                                x=bad_times, y=bad_positions,
                                mode='markers',
                                name=f'Motor {motor_id} (Bad Checksum)',
                                marker=dict(color='red', size=6, symbol='x'),
                                showlegend=False
                            ),
                            row=row, col=1
                        )
        
        # Calculate statistics for title
        total_points = sum(len(data) for data in self.motor_data.values())
        bad_checksums = sum(1 for data in self.motor_data.values() 
                           for point in data if not point[3])
        duration = max(max(data, key=lambda x: x[0])[0] for data in self.motor_data.values()) - \
                  min(min(data, key=lambda x: x[0])[0] for data in self.motor_data.values()) if self.motor_data else 0
        
        fig.update_layout(
            title=f'Encoder Feedback Analysis{title_suffix}<br>'
                  f'<sub>Duration: {duration:.2f}s | Points: {total_points} | Bad Checksums: {bad_checksums}</sub>',
            height=800,
            showlegend=True,
            hovermode='x unified',
            template='plotly_white'
        )
        
        fig.update_xaxes(title_text='Time (seconds)', row=3, col=1)
        fig.update_yaxes(title_text='Encoder Position (ticks)')
        
        # Add grid
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        
        fig.show()
        print(f"Final plot generated: {total_points} data points, {duration:.2f}s duration")


def run_receiver(host: str, port: int, csv_path: Optional[str], duration: Optional[float], 
                enable_plot: bool = False, max_plot_points: int = 1000):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        # Allow address reuse to prevent "Address already in use" errors
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.settimeout(0.5)
        print(f"Listening for encoder feedback on {host}:{port} (packet size {PACKET_SIZE} bytes)")
    except OSError as e:
        print(f"Failed to bind socket to {host}:{port}: {e}")
        print("Try a different port or check if another process is using this port")
        sock.close()
        return

    # Initialize plotter if requested
    plotter = None
    if enable_plot:
        try:
            plotter = EncoderPlotter(max_points=max_plot_points)
            print("Real-time plotting enabled")
        except Exception as e:
            print(f"Failed to initialize plotter: {e}")
            enable_plot = False

    csv_file = None
    csv_writer = None
    if csv_path:
        try:
            csv_file = open(csv_path, "w", newline="")
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["timestamp", "motor_id", "encoder_position", "status_word", "checksum_ok"])
        except IOError as e:
            print(f"Failed to open CSV file {csv_path}: {e}")
            sock.close()
            return

    start = time.time()
    count = 0
    try:
        print("Receiving encoder feedback... Press Ctrl+C to stop")
        if duration is not None:
            print(f"Will run for {duration} seconds")
        
        while True:
            if duration is not None and (time.time() - start) >= duration:
                print("Duration elapsed; stopping receiver")
                break
            try:
                data, addr = sock.recvfrom(64)
            except socket.timeout:
                continue
            except OSError as e:
                print(f"Socket error during receive: {e}")
                break

            if len(data) < PACKET_SIZE:
                continue

            # Some MCUs may batch multiple packets; parse chunk-wise
            offset = 0
            while offset + PACKET_SIZE <= len(data):
                motor_id, enc, status, checksum = PACKET_STRUCT.unpack_from(data, offset)
                offset += PACKET_SIZE
                expected = calc_checksum(motor_id, enc, status)
                ok = (checksum == expected)
                ts = time.time()
                count += 1
                
                # Console output
                print(f"[{ts:.3f}] motor={motor_id:02d} enc={enc:8d} status=0x{status:04X} chk={'OK' if ok else 'BAD'}")
                
                # CSV logging
                if csv_writer:
                    csv_writer.writerow([f"{ts:.6f}", motor_id, enc, status, int(ok)])
                
                # Real-time plotting
                if plotter:
                    plotter.add_data_point(ts, motor_id, enc, status, ok)
                    
    except KeyboardInterrupt:
        print("\nReceiver interrupted by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        try:
            sock.close()
        except:
            pass
        if csv_file:
            try:
                csv_file.close()
            except:
                pass
        
        print(f"Receiver stopped after {count} packets")
        
        # Generate final plot if plotting was enabled
        if plotter and count > 0:
            print("Generating final plot...")
            try:
                plotter.finalize_plot(f" - {count} packets")
            except Exception as e:
                print(f"Failed to generate final plot: {e}")


def main():
    ap = argparse.ArgumentParser(description="UDP receiver for encoder feedback")
    ap.add_argument("--host", default=DEFAULT_HOST, help="Host to bind to")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind to")
    ap.add_argument("--csv", dest="csv_path", help="CSV file to save data")
    ap.add_argument("--duration", type=float, help="Recording duration in seconds")
    ap.add_argument("--plot", action="store_true", help="Enable real-time plotting")
    ap.add_argument("--max-plot-points", type=int, default=1000, 
                    help="Maximum points to show in real-time plot")
    args = ap.parse_args()

    run_receiver(args.host, args.port, args.csv_path, args.duration, 
                args.plot, args.max_plot_points)


if __name__ == "__main__":
    main()
