"""3D charts: a whole season on one surface, with the round on the slider highlighted.

  error_surface    mean log-WIS by round and horizon, for up to two models
  rate_surface     flu admissions per 100k by week and state (the teammate's heatmap from
                   notebooks/data_analysis.ipynb, raised into 3D), with a model's forecasts on top
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from benchmark_site.viz.charts.common import (SCORED_HORIZONS, as_dict, count_label, date_label,
                                        is_all_locations, observed_series, shared_forecasts)
from benchmark_site.viz.distributions import quantile_table
from benchmark_site.viz.replay import add_replay, frame_name, start_index
from benchmark_site.viz.states import STATE_ABBR
from benchmark_site.viz.theme import ChartContext, colorscale, empty_figure, new_figure

CAMERA = dict(eye=dict(x=0.95, y=-1.95, z=0.8), up=dict(x=0, y=0, z=1), center=dict(x=0, y=0, z=-0.12))
MARGIN = dict(l=8, r=8, t=112)
PER_100K = 100_000
RATE_TICKS = [0, 0.5, 1, 2, 5, 10, 20]   # admissions per 100k, labelled on the log(1 + rate) axis


def _date_axis(title: str, dates: list, tick_count: int = 8) -> dict:
    """A 3D axis over round positions 0..n-1, labelled with about tick_count dates."""
    step = max(1, len(dates) // tick_count)
    positions = list(range(0, len(dates), step))
    return dict(title=title, tickvals=positions, ticktext=[f"{pd.Timestamp(dates[i]):%b %d '%y}" for i in positions])


# ---------------------------------------------------------------- error by round and horizon

def error_surface(ctx: ChartContext, scores, location=None, start=None) -> go.Figure:
    """Mean log-WIS for each (round, horizon) as a surface per model, for up to two models, on the
    forecasts both made. Peaks show when, and how far ahead, a model struggled."""
    scores = shared_forecasts(as_dict(scores), location)
    names = [name for name, table in scores.items() if len(table)][:2]
    if not names:
        return empty_figure(ctx, "No shared forecasts to compare")

    p = ctx.palette
    dates = sorted(scores[names[0]]["reference_date"].unique())
    where = "all locations" if is_all_locations(location) else ctx.location_name(location)
    surface_colors = [p.sequential, p.sequential_second]
    color_names = ["blue", "orange"]
    subtitle = " vs ".join(f"{name} ({color_names[i]})" for i, name in enumerate(names))
    figure = new_figure(ctx, f"Error by round and horizon · {where}", subtitle + " · mean log-WIS, lower is better",
                        height=640)

    grids = {}
    round_labels = np.tile(np.array([date_label(d) for d in dates]), (len(SCORED_HORIZONS), 1))[..., None]
    for i, name in enumerate(names):
        grid = scores[name].pivot_table(index="horizon", columns="reference_date", values="wis", aggfunc="mean")
        grids[name] = grid.reindex(index=SCORED_HORIZONS, columns=dates).to_numpy(dtype=float)
        figure.add_trace(go.Surface(
            x=np.arange(len(dates)), y=SCORED_HORIZONS, z=grids[name], name=name, showscale=False,
            colorscale=colorscale(surface_colors[i]), opacity=0.9 if i == 0 else 0.6, customdata=round_labels,
            hovertemplate=f"<b>{name}</b><br>round %{{customdata[0]}} · h%{{y}}<br>mean log-WIS %{{z:.3f}}<extra></extra>"))

    frames = []
    for j, reference_date in enumerate(dates):
        lines = [go.Scatter3d(x=[j] * len(SCORED_HORIZONS), y=SCORED_HORIZONS, z=grids[name][:, j] + 0.005,
                              mode="lines+markers", name="Selected round", showlegend=k == 0, hoverinfo="skip",
                              line=dict(color=p.ink, width=6), marker=dict(size=4, color=p.ink))
                 for k, name in enumerate(names)]
        frames.append(go.Frame(name=frame_name(reference_date), data=lines,
                               traces=list(range(len(names), 2 * len(names)))))

    figure.update_layout(
        scene=dict(xaxis=_date_axis("Forecast round", dates),
                   yaxis=dict(title="Horizon", tickvals=SCORED_HORIZONS, ticktext=[f"h{h}" for h in SCORED_HORIZONS]),
                   zaxis=dict(title="Mean log-WIS"), camera=CAMERA, aspectmode="manual",
                   aspectratio=dict(x=1.6, y=0.9, z=0.7)),
        margin=MARGIN)
    add_replay(figure, ctx, frames, [date_label(d) for d in dates],
               len(dates) - 1 if start is None else start_index(dates, start), prefix="Round: ")
    return figure


# ---------------------------------------------------------------- flu rate by week and state

def rate_surface(ctx: ChartContext, truth: pd.DataFrame, output: pd.DataFrame, name: str = "model",
                 weeks_before: int = 6, weeks_after: int = 4, start=None) -> go.Figure:
    """The teammate's state-by-week heatmap as a surface, with a model's forecasts on top.

    Built the same way as in notebooks/data_analysis.ipynb: one row per state (the US total left out),
    rows sorted by the state's mean weekly rate (highest first), one column per week, and
    height = log(1 + admissions per 100k). Her heatmap used viridis; this uses the site's blue scale.

    At the round on the slider, the dark line marks that week across every state, and the dots are
    the model's median forecasts for horizons 0-3, converted to the same rate scale.
    truth needs a weekly_rate column (admissions per 100k), as saved by the backtest.
    """
    if "weekly_rate" not in truth.columns:
        return empty_figure(ctx, "This run's truth has no weekly_rate column")
    states = truth[truth["location"] != "US"]
    medians = quantile_table(output[output["location"] != "US"])
    if states.empty or medians.empty:
        return empty_figure(ctx, "No state data to show")

    rounds = sorted(medians["reference_date"].unique())
    first_week = pd.Timestamp(rounds[0]) - pd.Timedelta(weeks=weeks_before)
    last_week = pd.Timestamp(rounds[-1]) + pd.Timedelta(weeks=weeks_after)
    states = states[(states["date"] >= first_week) & (states["date"] <= last_week)]

    rates = states.pivot_table(index="location", columns="date", values="weekly_rate", aggfunc="first")
    rates = rates.loc[rates.mean(axis=1).sort_values(ascending=False).index]   # highest-rate states first
    weeks, locations = list(rates.columns), list(rates.index)
    z = np.log1p(rates.to_numpy(dtype=float))

    p = ctx.palette
    names = [ctx.location_name(code) for code in locations]
    hover_text = np.array([[f"{place} · week ending {date_label(week)}" for week in weeks] for place in names])
    figure = new_figure(
        ctx, "Flu hospital admissions per 100k, by week and state",
        f"States sorted by mean rate, highest first · height = log(1 + rate) · orange dots = {name}'s median "
        "forecasts at the round on the slider", height=700)
    figure.add_trace(go.Surface(
        x=np.arange(len(weeks)), y=np.arange(len(locations)), z=z, colorscale=colorscale(p.sequential), opacity=0.95,
        customdata=np.dstack([hover_text, rates.to_numpy(dtype=float)]), name="Observed rate",
        colorbar=dict(title=dict(text="per 100k", font=dict(color=p.ink_secondary, size=12)),
                      tickvals=np.log1p(RATE_TICKS), ticktext=[f"{t:g}" for t in RATE_TICKS],
                      thickness=12, len=0.6, outlinewidth=0, tickfont=dict(color=p.muted, size=11)),
        contours=dict(z=dict(show=False)),
        hovertemplate="%{customdata[0]}<br>observed %{customdata[1]:.2f} per 100k<extra></extra>"))

    week_position = {pd.Timestamp(week): i for i, week in enumerate(weeks)}
    state_position = {code: i for i, code in enumerate(locations)}
    population = _population_from_truth(states)
    accent = p.series[1]   # orange: stands out on the blue surface

    frames = []
    for reference_date in rounds:
        column = week_position.get(pd.Timestamp(reference_date))
        in_view = column is not None
        this_week = go.Scatter3d(
            x=[column] * len(locations) if in_view else [], y=np.arange(len(locations)) if in_view else [],
            z=z[:, column] + 0.02 if in_view else [], mode="lines", name="Reference week",
            line=dict(color=p.ink, width=5), hoverinfo="skip")
        forecasts = _forecast_points(medians[medians["reference_date"] == reference_date], population,
                                     week_position, state_position, ctx)
        dots = go.Scatter3d(
            x=forecasts["x"], y=forecasts["y"], z=forecasts["z"], mode="markers", name=f"{name} median forecast",
            ids=forecasts["location"] + "-h" + forecasts["horizon"].astype(str),   # each dot glides to its next round
            marker=dict(size=3.5, color=accent, line=dict(color=p.surface, width=0.5)),
            customdata=forecasts[["text", "rate", "count"]].to_numpy(),
            hovertemplate="%{customdata[0]}<br>forecast median %{customdata[1]:.2f} per 100k "
                          "(%{customdata[2]} admissions)<extra></extra>")
        frames.append(go.Frame(name=frame_name(reference_date), data=[this_week, dots], traces=[1, 2]))

    abbreviations = [STATE_ABBR.get(code, code) for code in locations]
    figure.update_layout(
        scene=dict(xaxis=_date_axis("Week ending", weeks),
                   yaxis=dict(title="State (highest mean rate first)", tickvals=list(range(len(locations))),
                              ticktext=abbreviations, tickfont=dict(size=8)),
                   zaxis=dict(title="log(1 + per 100k)", tickvals=np.log1p(RATE_TICKS),
                              ticktext=[f"{t:g}" for t in RATE_TICKS]),
                   camera=dict(eye=dict(x=1.5, y=-1.8, z=1.05), up=dict(x=0, y=0, z=1)),
                   aspectmode="manual", aspectratio=dict(x=1.35, y=1.5, z=0.55)),
        margin=MARGIN)
    national = observed_series(truth, "US")   # open on the national peak
    add_replay(figure, ctx, frames, [date_label(d) for d in rounds], start_index(rounds, start, national),
               prefix="Round: ")
    return figure


def _population_from_truth(truth: pd.DataFrame) -> pd.Series:
    """Each location's population, recovered from its counts and rates: count / rate x 100k."""
    usable = truth[truth["weekly_rate"] > 0]
    return (usable["value"] / usable["weekly_rate"] * PER_100K).groupby(usable["location"]).median()


def _forecast_points(medians: pd.DataFrame, population: pd.Series, week_position: dict, state_position: dict,
                     ctx: ChartContext) -> pd.DataFrame:
    """Median forecasts for horizons 0-3 as points on the rate surface:
    rate = median admissions / population x 100k, height = log(1 + rate)."""
    rows = medians[medians["horizon"].isin(SCORED_HORIZONS)].copy()
    rows["x"] = rows["target_end_date"].map(lambda d: week_position.get(pd.Timestamp(d)))
    rows["y"] = rows["location"].map(state_position)
    rows["rate"] = rows[0.5] / rows["location"].map(population) * PER_100K
    rows = rows.dropna(subset=["x", "y", "rate"])
    rows["z"] = np.log1p(rows["rate"]) + 0.02
    rows["count"] = rows[0.5].map(count_label)
    rows["text"] = [f"{ctx.location_name(code)} · h{h} · week ending {date_label(d)}"
                    for code, h, d in zip(rows["location"], rows["horizon"], rows["target_end_date"])]
    return rows
