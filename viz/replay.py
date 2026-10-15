"""The slider and Play/Pause controls that step a chart through forecast rounds.

How replay works: a chart is a list of Plotly frames, one per forecast round. Each frame only
replaces trace data. Frames never change the layout, because Plotly snaps the slider back to its
starting position whenever a frame touches layout. So anything that changes per round (labels,
cursor lines) is drawn as a trace, and titles stay fixed; the slider shows the round.

On the site and in saved charts, replay.js takes over the controls and glides every chart from one
round to the next. Without it the controls still work and rounds switch instantly.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from benchmark_site.viz.theme import ChartContext

BOTTOM_MARGIN = 180      # pixels under the plot for the buttons and the slider
BUTTONS_BELOW_PLOT = 68  # pixels from the plot's bottom edge to the buttons
SLIDER_BELOW_BUTTONS = 40

# Page script that glides charts between rounds (see the comment in the file).
# The site adds it to every page; save_html() adds it to every saved chart.
REPLAY_SCRIPT = Path(__file__).with_name("replay.js").read_text()


def add_replay(figure: go.Figure, ctx: ChartContext, frames: list[go.Frame], labels: list[str],
               start: int, prefix: str = "Forecast round: ", play_speed_ms: int = 450) -> None:
    """Attach frames, a Play/Pause row and a full-width slider; show frame `start` first."""
    p = ctx.palette
    figure.frames = frames
    if frames:
        figure.add_traces(frames[start].data)

    plot_height = max((figure.layout.height or 560) - 112 - BOTTOM_MARGIN - 24, 160)
    buttons_y = -BUTTONS_BELOW_PLOT / plot_height
    slider_y = buttons_y - SLIDER_BELOW_BUTTONS / plot_height
    jump = dict(mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=0))
    play = dict(mode="immediate", fromcurrent=True, frame=dict(duration=play_speed_ms, redraw=True),
                transition=dict(duration=0))

    figure.update_layout(
        margin=dict(b=BOTTOM_MARGIN),
        updatemenus=[dict(
            type="buttons", direction="left", showactive=False,
            x=0, xanchor="left", y=buttons_y, yanchor="top", pad=dict(t=0, r=8),
            bgcolor=p.surface, bordercolor=p.axis, borderwidth=1, font=dict(color=p.ink, size=12),
            buttons=[
                dict(label="▶  Play", method="animate", args=[None, play]),
                dict(label="❚❚  Pause", method="animate", args=[[None], jump]),
            ],
        )],
        sliders=[dict(
            active=start, x=0, len=1, xanchor="left", y=slider_y, yanchor="top", pad=dict(t=0, b=0),
            bgcolor=p.grid, activebgcolor=p.series[0], bordercolor=p.axis, borderwidth=0,
            tickcolor=p.axis, ticklen=3, minorticklen=0,
            font=dict(color="rgba(0,0,0,0)", size=1),  # tick labels hidden: too many rounds to label
            currentvalue=dict(prefix=prefix, xanchor="left", offset=8, font=dict(color=p.ink, size=13)),
            transition=dict(duration=300, easing="cubic-in-out"),   # the slider handle glides
            steps=[dict(method="animate", label=label, args=[[frame.name], jump])
                   for label, frame in zip(labels, frames)],
        )],
    )


def frame_name(reference_date) -> str:
    return str(pd.Timestamp(reference_date).date())


def round_label(reference_date) -> str:
    date = pd.Timestamp(reference_date)
    return f"{date:%b} {date.day}, {date.year}"


def start_index(dates, start=None, observed: pd.Series | None = None) -> int:
    """Which round to open on: `start` if given, else the week the location's admissions peaked,
    else the last round."""
    dates = [pd.Timestamp(d) for d in dates]
    if start is not None:
        start = pd.Timestamp(start)
        return min(range(len(dates)), key=lambda i: abs(dates[i] - start))
    if observed is not None:
        level = observed.reindex(dates)
        if level.notna().any():
            return int(np.nanargmax(level.to_numpy(dtype=float)))
    return len(dates) - 1
