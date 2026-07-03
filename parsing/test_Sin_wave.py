import numpy as np
import matplotlib.pyplot as plt


def interp_with_sine_blend(start_pos, end_pos, num_points):
    t = np.linspace(0, np.pi, num_points)
    blend = (1 - np.cos(t)) / 2
    points = (1 - blend) * start_pos + blend * end_pos

    return points

def interp_with_blend(q0, qf, N, tb_cent):
    curve = np.zeros(N)
    if curve is None:
        return
    nb = int(tb_cent * N)
    a_2 = 0.5 * (qf - q0) / (nb * (N - nb))

    for i in range(nb):
        tmp = a_2 * (i ** 2)
        curve[i] = q0 + tmp
        curve[N - i - 1] = qf - tmp

    tmp = a_2 * (nb ** 2)
    qa = q0 + tmp
    qb = qf - tmp

    curve[nb:N - nb] = np.linspace(qa, qb, N - (2 * nb))
    curve = curve.astype(int)

    return curve
# Example parameters
start_pos = 0
qf_encoder_picker = 10
fill_points = 20
tb_cent = .2
speed = 1
fill_points = min(30, int(30 - (speed - 1) * (25 / 9)))

# Generate points
points1 = interp_with_sine_blend(start_pos, qf_encoder_picker, 10)  # (move)
points2 = interp_with_sine_blend(qf_encoder_picker, qf_encoder_picker, fill_points)  # (fill)
points3 = interp_with_sine_blend(qf_encoder_picker, start_pos, 10)  # (move)
points4 = interp_with_sine_blend(start_pos, start_pos, fill_points)  # (fill)

# points1 = interp_with_blend(start_pos, qf_encoder_picker, 5, tb_cent) # (move)
# points2 = interp_with_blend(qf_encoder_picker, qf_encoder_picker, fill_points, tb_cent) # (fill)
# points3 = interp_with_blend(qf_encoder_picker, start_pos, 5, tb_cent) # (move)
# points4 = interp_with_blend(start_pos, start_pos, fill_points, tb_cent) # (fill)


# Combine all points
all_points = np.concatenate([points1, points2, points3, points4])

# Plotting
plt.figure(figsize=(12, 6))
plt.plot(all_points, '-o')
plt.title('Interpolated Points with Sine Blending')
plt.xlabel('Point Index')
plt.ylabel('Position')
plt.grid(True)

# Add vertical lines to separate different sections
plt.axvline(x=5, color='r', linestyle='--', label='Move/Fill Transition')
plt.axvline(x=25, color='r', linestyle='--')
plt.axvline(x=30, color='r', linestyle='--')

plt.legend()
plt.show()
