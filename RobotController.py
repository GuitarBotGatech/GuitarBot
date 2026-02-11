import numpy as np
import socket
import time
import struct


def main(song_trajs):
    """
    Sends the entire song trajectory in timed chunks without an ACK mechanism.
    It calculates the duration of a chunk and waits for that amount of time
    before sending the next, creating a predictive, open-loop timing system.
    """
    # --- Configuration ---
    UDP_IP = "10.2.1.177"  # Arduino's IP address
    UDP_PORT = 8888  # Arduino's listening port

    # --- Tunable Parameters ---
    # Set the number of points to bundle into a single network message.
    BATCH_SIZE_POINTS = 20

    # Each trajectory point represents a 5ms step.
    TIME_PER_POINT_S = 0.005

    # Trajectory must be N x 16 (15 motors + 1 control flag).
    # If N x 15 is passed (legacy), pad with 0 flag (normal mode).
    if song_trajs.ndim == 2 and song_trajs.shape[1] == 15:
        flag_col = np.zeros((song_trajs.shape[0], 1), dtype=song_trajs.dtype)
        song_trajs = np.hstack([song_trajs, flag_col])

    # --- Socket Setup ---
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # --- Calculation ---
    # The time interval to wait after sending a batch is the number of points
    # multiplied by the time each point represents.
    batch_interval_seconds = BATCH_SIZE_POINTS * TIME_PER_POINT_S


    num_total_points = len(song_trajs)
    print(f"Starting song with {num_total_points} points.")
    print(f"Sending in batches of {BATCH_SIZE_POINTS} points every {batch_interval_seconds:.2f} seconds.")

    # --- Timed Sending Loop ---
    total_start_time = time.time()
    for i in range(0, num_total_points, BATCH_SIZE_POINTS):
        start_time = time.time()

        # Slice the next batch from the full song trajectory
        chunk = song_trajs[i:i + BATCH_SIZE_POINTS]

        # Convert the numpy chunk to a flat byte array (using float32)
        byte_payload = chunk.astype(np.float32).tobytes()

        # Send the entire chunk as a single UDP packet
        sock.sendto(byte_payload, (UDP_IP, UDP_PORT))

        num_points_in_chunk = len(chunk)
        print(f"Sent batch {i // BATCH_SIZE_POINTS + 1}: {num_points_in_chunk} points ({len(byte_payload)} bytes).")
        elapsed_time = time.time() - start_time

        # The last chunk might be smaller, so we find specific duration
        actual_chunk_interval = num_points_in_chunk * TIME_PER_POINT_S
        sleep_time = max(0, actual_chunk_interval - elapsed_time)

        # Only sleep if there's another chunk to send
        #if (i + BATCH_SIZE_POINTS) < num_total_points:
        print(f"--> Sleeping for {sleep_time:.4f} seconds...\n")
        time.sleep(sleep_time)

    total_elapsed_time = time.time() - total_start_time
    print(f"Total elapsed time: {total_elapsed_time:.4f} seconds")
    print("All batches sent. Song Complete.")
    return 0