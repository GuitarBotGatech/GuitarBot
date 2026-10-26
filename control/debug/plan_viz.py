"""Debug visualization and verbose dumps for GuitarBotParser.

Kept out of ``control.plan`` so algorithmic trajectory code stays free of
plotly / console-dump coupling. Enable via ``GuitarBotParser(graph=True)``
or ``tune.graph = True``.
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from tuning import tune as tu


def show_motor_trajectory(combined_array, cc_events=None, time_step: float | None = None):
    """Interactive Plotly chart of LH/RH motor positions (optional CC subplot)."""
    if combined_array is None or getattr(combined_array, "size", 0) == 0:
        return

    dt = float(tu.TIME_STEP if time_step is None else time_step)
    max_rows = int(combined_array.shape[0])
    timestamps = np.arange(0, max_rows * dt, dt)

    cc_points_by_controller: dict[int, list[tuple[float, int]]] = {}
    if cc_events:
        for event in cc_events:
            if getattr(event, "address", None) != "/cc" or len(event.args) < 2:
                continue
            try:
                controller = int(event.args[0])
                value = int(round(float(event.args[1])))
                value = max(0, min(127, value))
            except (ValueError, TypeError):
                continue
            cc_points_by_controller.setdefault(controller, []).append(
                (event.timestamp, value)
            )

    has_cc_subplot = bool(cc_points_by_controller)
    if has_cc_subplot:
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            row_heights=[0.8, 0.2],
            vertical_spacing=0.06,
            subplot_titles=("Motor Positions", "MIDI CC (0–127)"),
        )
    else:
        fig = go.Figure()

    for motor in range(min(12, combined_array.shape[1])):
        motor_type = "Slider" if motor < 6 else "Presser"
        string_id = motor if motor < 6 else motor - 6
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=combined_array[:, motor],
                mode="lines",
                name=f"LH {motor_type} {string_id + 1}",
            ),
            **({"row": 1, "col": 1} if has_cc_subplot else {}),
        )

    for motor in range(12, min(18, combined_array.shape[1])):
        picker_id = motor - 12
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=combined_array[:, motor],
                mode="lines",
                name=f"RH Picker {picker_id}",
                line=dict(width=2),
            ),
            **({"row": 1, "col": 1} if has_cc_subplot else {}),
        )

    if has_cc_subplot:
        for controller in sorted(cc_points_by_controller):
            points = sorted(cc_points_by_controller[controller], key=lambda p: p[0])
            fig.add_trace(
                go.Scatter(
                    x=[point[0] for point in points],
                    y=[point[1] for point in points],
                    mode="lines+markers",
                    name=f"CC{controller}",
                    marker=dict(size=5),
                    line=dict(width=1.5),
                ),
                row=2,
                col=1,
            )
        fig.update_layout(
            title="Motor Positions Over Time + MIDI CC",
            legend_title="Signals",
        )
        fig.update_yaxes(title_text="Motor Position", row=1, col=1)
        fig.update_yaxes(title_text="CC Value", range=[0, 127], row=2, col=1)
        fig.update_xaxes(title_text="Time (s)", row=2, col=1)
    else:
        fig.update_layout(
            title="Motor Positions Over Time",
            xaxis_title="Time (s)",
            yaxis_title="Motor Position",
            legend_title="Motors",
        )
    fig.show()


def print_events(motor_positions) -> None:
    print("PRINTING EVENTS: ")
    for event in motor_positions:
        print(event)


def log_slide_toggles(slide_toggles) -> None:
    print("Slide Toggles: ", slide_toggles)


def log_matrix_shape(shape) -> None:
    print("Full Matrix Shape: ", shape)


def log_lh_events_header() -> None:
    print("LH UPDATED EVENTS LIST (NO SYNC LH EVENTS): ")


def log_lh_pick_events(lh_pick_events) -> None:
    print("LH PICK EVENTS: ", lh_pick_events)
