"""Score and calibration charts. Every chart compares models only on the forecasts they all made."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from benchmark_site.viz.charts.common import SCORED_HORIZONS, as_dict, date_label, is_all_locations, shared_forecasts, \
    with_season_gaps
from benchmark_site.viz.replay import add_replay, frame_name, start_index
from benchmark_site.viz.theme import ChartContext, empty_figure, new_figure


def _scope(ctx: ChartContext, location, horizon=None) -> str:
    where = "all locations" if is_all_locations(location) else ctx.location_name(location)
    return where + (f", horizon {horizon}" if horizon is not None else ", horizons 0-3")


def _opening_round(dates, start) -> int:
    """Season-to-date charts open on the latest round unless a start date is given."""
    return start_index(dates, start) if start is not None else len(dates) - 1


# ---------------------------------------------------------------- score over the season

def score_timeline(ctx: ChartContext, scores, location=None, horizon=None, relative_to: str | None = None,
                   start=None) -> go.Figure:
    """Mean log-WIS per forecast round for each model.

    relative_to: divide each round's score by that model's score for the same round, so 1.0 means
    "as good as it" and below 1.0 means better.
    """
    scores = shared_forecasts(as_dict(scores), location, horizon)
    weekly = {name: table.groupby("reference_date")["wis"].mean().sort_index()
              for name, table in scores.items() if len(table)}
    if not weekly:
        return empty_figure(ctx, "No shared forecasts to compare")
    relative = relative_to in weekly
    if relative:
        reference = weekly[relative_to]
        weekly = {name: (series / reference).dropna() for name, series in weekly.items()}

    p = ctx.palette
    names = list(weekly)
    forecasts = len(next(iter(scores.values())))
    subtitle = f"{forecasts:,} forecasts made by every model shown"
    if relative:
        subtitle += f" · 1.0 = as good as {relative_to}"
    figure = new_figure(ctx, f"Score by forecast round · {_scope(ctx, location, horizon)}", subtitle)
    for name in names:
        series = with_season_gaps(weekly[name])
        is_reference = relative and name == relative_to
        figure.add_trace(go.Scatter(
            x=series.index, y=series.values, mode="lines", name=name, connectgaps=False,
            line=dict(color=ctx.color(name, names), width=1.5 if is_reference else 2),
            hovertemplate=f"<b>{name}</b>: %{{y:.3f}}<extra></extra>"))
    if relative:
        figure.add_hline(y=1, line=dict(color=p.axis, width=1))

    values = pd.concat(list(weekly.values()))
    padding = (values.max() - values.min()) * 0.08 or 0.05
    y_bottom, y_top = max(float(values.min() - padding), 0), float(values.max() + padding)

    dates = sorted(set().union(*(set(series.index) for series in weekly.values())))
    frames = []
    for reference_date in dates:
        cursor = go.Scatter(x=[reference_date, reference_date], y=[y_bottom, y_top], mode="lines",
                            line=dict(color=p.axis, width=1), showlegend=False, hoverinfo="skip")
        points = [_value_marker(ctx, name, names, reference_date, weekly[name].get(reference_date)) for name in names]
        frames.append(go.Frame(name=frame_name(reference_date), data=[cursor, *points],
                               traces=list(range(len(names), len(names) + 1 + len(points)))))

    y_title = f"log-WIS ÷ {relative_to}'s (lower is better)" if relative else "Mean log-WIS (lower is better)"
    figure.update_layout(yaxis=dict(title=y_title, range=[y_bottom, y_top]),
                         xaxis_title="Forecast round (reference date)", hovermode="x unified")
    add_replay(figure, ctx, frames, [date_label(d) for d in dates], _opening_round(dates, start), prefix="Round: ")
    return figure


def _value_marker(ctx: ChartContext, name: str, names: list, x, value) -> go.Scatter:
    has_value = value is not None and pd.notna(value)
    return go.Scatter(
        x=[x], y=[value if has_value else None], mode="markers+text", showlegend=False, hoverinfo="skip",
        text=[f" {value:.2f}" if has_value else ""], textposition="middle right",
        textfont=dict(color=ctx.palette.ink_secondary, size=11),
        marker=dict(size=10, color=ctx.color(name, names), line=dict(color=ctx.palette.surface, width=2)))


# ---------------------------------------------------------------- score by horizon

def horizon_summary(ctx: ChartContext, scores, relative_to: str | None = None, location=None,
                    start=None) -> go.Figure:
    """Mean log-WIS by horizon over every forecast up to the round on the slider."""
    scores = shared_forecasts(as_dict(scores), location)
    names = [name for name, table in scores.items() if len(table)]
    if not names:
        return empty_figure(ctx, "No shared forecasts to compare")
    relative = relative_to in names
    dates = sorted(scores[names[0]]["reference_date"].unique())

    def season_to_date(name, reference_date) -> pd.Series:
        table = scores[name][scores[name]["reference_date"] <= reference_date]
        return table.groupby("horizon")["wis"].mean().reindex(SCORED_HORIZONS)

    frames, tallest = [], 0.0
    for reference_date in dates:
        means = {name: season_to_date(name, reference_date) for name in names}
        if relative:
            means = {name: mean / means[relative_to] for name, mean in means.items()}
        tallest = max(tallest, max(float(np.nanmax(mean.to_numpy(dtype=float), initial=0)) for mean in means.values()))
        bars = [_horizon_bars(ctx, name, names, means[name]) for name in names]
        frames.append(go.Frame(name=frame_name(reference_date), data=bars))

    figure = new_figure(ctx, "Score by horizon, season to date", "Every shared forecast up to the round on the slider")
    figure.update_layout(
        barmode="group", bargap=0.28, bargroupgap=0.06,
        yaxis=dict(title=f"log-WIS ÷ {relative_to}'s" if relative else "Mean log-WIS", range=[0, tallest * 1.18]),
        xaxis_title="Horizon (weeks after the reference date)")
    if relative:
        figure.add_hline(y=1, line=dict(color=ctx.palette.axis, width=1))
    add_replay(figure, ctx, frames, [date_label(d) for d in dates], _opening_round(dates, start),
               prefix="Through round: ")
    return figure


def _horizon_bars(ctx: ChartContext, name: str, names: list, means: pd.Series) -> go.Bar:
    return go.Bar(
        x=[f"h{h}" for h in SCORED_HORIZONS], y=means.values, name=name,
        marker=dict(color=ctx.color(name, names), line=dict(color=ctx.palette.surface, width=2), cornerradius=4),
        text=[f"{value:.2f}" if pd.notna(value) else "" for value in means.values], textposition="outside",
        textfont=dict(color=ctx.palette.ink_secondary, size=11), cliponaxis=False,
        hovertemplate=f"<b>{name}</b> · %{{x}}: %{{y:.3f}}<extra></extra>")


# ---------------------------------------------------------------- calibration

def coverage_replay(ctx: ChartContext, coverage, location=None, horizon=None, start=None) -> go.Figure:
    """For each of the 11 central intervals: the share of forecasts whose interval contained the
    observed value, over every forecast up to the round on the slider."""
    coverage = shared_forecasts(as_dict(coverage), location, horizon)
    names = [name for name, table in coverage.items() if len(table)]
    if not names:
        return empty_figure(ctx, "No shared forecasts to compare")
    columns = sorted((c for c in coverage[names[0]].columns if c.startswith("cov_")),
                     key=lambda c: int(c.removeprefix("cov_")))
    nominal = [int(c.removeprefix("cov_")) for c in columns]
    dates = sorted(coverage[names[0]]["reference_date"].unique())
    p = ctx.palette

    figure = new_figure(ctx, "Calibration by interval", "Shared forecasts up to the round on the slider · diagonal = calibrated")
    figure.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines", name="Perfectly calibrated",
                                line=dict(color=p.axis, width=1.5), hoverinfo="skip"))
    frames = []
    for reference_date in dates:
        lines = []
        for name in names:
            table = coverage[name][coverage[name]["reference_date"] <= reference_date]
            share = (table[columns].astype(float).mean() * 100).to_numpy()
            color = ctx.color(name, names)
            lines.append(go.Scatter(
                x=nominal, y=share, mode="lines+markers", name=name, line=dict(color=color, width=2),
                marker=dict(size=8, color=color, line=dict(color=p.surface, width=2)),
                hovertemplate=f"<b>{name}</b><br>the %{{x}}% interval contained what happened "
                              f"%{{y:.0f}}% of the time<extra></extra>"))
        frames.append(go.Frame(name=frame_name(reference_date), data=lines, traces=list(range(1, 1 + len(lines)))))

    figure.update_layout(xaxis=dict(title="Interval (%)", range=[0, 100], tickvals=[n for n in nominal if n != 95]),  # 95 sits too close to 98
                         yaxis=dict(title="What happened was inside it (% of forecasts)", range=[0, 102]))
    add_replay(figure, ctx, frames, [date_label(d) for d in dates], _opening_round(dates, start),
               prefix="Through round: ")
    return figure
