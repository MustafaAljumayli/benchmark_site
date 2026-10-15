"""Forecasts against what happened, replayed round by round.

At each round every model's forecast for horizons -1..3 is drawn as its median plus nested
central intervals built from pairs of its 23 quantiles. All 11 intervals CDC scores
(98, 95, 90, 80, 70, 60, 50, 40, 30, 20, 10%) are drawn as overlapping translucent bands, so the
color is darkest where the forecast is most confident.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from benchmark_site.viz.charts.common import as_dict, date_label, observed_series
from benchmark_site.viz.distributions import quantile_table
from benchmark_site.viz.replay import add_replay, frame_name, start_index
from benchmark_site.viz.theme import ChartContext, empty_figure, new_figure, rgba
from flusight.constants import ModelOutputConstants, ScoringConstants
from flusight.weeks import add_weeks, week_ends

QUANTILES = [q for pair in ScoringConstants.INTERVALS.values() for q in pair]
ALL_INTERVALS = list(ScoringConstants.INTERVALS)   # widest (98%) first, so narrower bands are drawn on top
KEY_INTERVALS = [0.95, 0.50]
WEEKS_BEFORE, WEEKS_AFTER = 6, 5  # how much of the season to show around the forecast rounds


def forecast_replay(ctx: ChartContext, outputs, truth: pd.DataFrame, location: str, intervals: str = "all",
                    published=None, log_y: bool = False, start=None) -> go.Figure:
    """Admissions over the season with each model's forecast at the round on the slider.

    intervals: "all" draws the 11 central intervals; "key" draws only the 50% and 95% intervals.
    published: optional function(reference_date) -> DataFrame(date, location, value) with the data as
    it was reported on that date. Drawn next to the final data, it shows how much later revisions
    changed the latest weeks.
    """
    outputs = as_dict(outputs)
    tables = {name: quantile_table(output[output["location"] == location]) for name, output in outputs.items()}
    tables = {name: table for name, table in tables.items() if not table.empty}
    place = ctx.location_name(location)
    if not tables:
        return empty_figure(ctx, f"{place}: no forecasts to show")

    bands = ALL_INTERVALS if intervals == "all" else KEY_INTERVALS
    band_opacity = 0.06 if intervals == "all" else 0.16  # overlapping bands add up toward the median
    dates = sorted(set().union(*(set(table["reference_date"]) for table in tables.values())))
    observed = observed_series(truth, location)
    x_start = add_weeks(dates[0], -WEEKS_BEFORE)
    x_end = add_weeks(dates[-1], WEEKS_AFTER)
    shown = observed[(observed.index >= x_start) & (observed.index <= x_end)]
    y_top = _y_top(tables, shown)

    p = ctx.palette
    interval_note = "all 11 central intervals (10% to 98%)" if intervals == "all" else "50% and 95% intervals"
    subtitle = f"Median and {interval_note} for horizons -1 to 3 · ◆ = what actually happened"
    if published is not None:
        subtitle += " · dark line = data as reported on the forecast date"
    figure = new_figure(ctx, f"{place} · forecasts by round", subtitle)
    figure.add_trace(go.Scatter(
        x=shown.index, y=shown.values, mode="lines", name="Final reported", line=dict(color=p.muted, width=1.5),
        hovertemplate="final reported: %{y:,.0f}<br>week ending %{x|%b %d, %Y}<extra></extra>"))

    frames = []
    for reference_date in dates:
        reference_date = pd.Timestamp(reference_date)
        traces = []
        if published is not None:
            traces.append(_as_reported_then(ctx, published, reference_date, location, week_ends(x_start, x_end)))
        for name, table in tables.items():
            rows = table[table["reference_date"] == reference_date].set_index("horizon").reindex(ModelOutputConstants.HORIZONS)
            traces += _model_traces(ctx, name, rows, reference_date, bands, band_opacity, list(tables))
        traces.append(_actual_markers(ctx, reference_date, observed))
        traces.append(_reference_line(ctx, reference_date, 1 if log_y else 0, y_top))
        absent = [name for name, table in tables.items() if not (table["reference_date"] == reference_date).any()]
        traces.append(_absent_note(ctx, absent, place, x_start, y_top))
        # trace 0 (final reported data) never changes; frames replace traces 1..n
        frames.append(go.Frame(name=frame_name(reference_date), data=traces, traces=list(range(1, 1 + len(traces)))))

    figure.update_layout(
        xaxis=dict(title="Week ending", range=[x_start, x_end]),
        yaxis=dict(title="Weekly hospital admissions", type="log" if log_y else "linear",
                   range=[0, np.log10(y_top)] if log_y else [0, y_top]),
    )
    add_replay(figure, ctx, frames, [date_label(d) for d in dates], start_index(dates, start, observed))
    return figure


def _y_top(tables: dict, shown: pd.Series) -> float:
    """Fit the observed season, and forecasts' 95% ranges unless they exceed 2.5x the season's peak."""
    peak = float(shown.max()) if len(shown) else 1.0
    widest = max(float(table[0.975].max()) for table in tables.values())
    return max(peak, min(widest, 2.5 * peak)) * 1.08


def _model_traces(ctx: ChartContext, name: str, rows: pd.DataFrame, reference_date, bands: list, opacity: float,
                  all_models: list) -> list:
    """Per model: a lower and an upper edge for each interval (the upper fills down to the lower),
    then the median line. rows has one row per horizon (blank where the model didn't forecast)."""
    color = ctx.color(name, all_models)
    group = dict(legendgroup=name)
    x = [add_weeks(reference_date, h) for h in ModelOutputConstants.HORIZONS]
    rows = rows.reindex(columns=list(QUANTILES) + [0.5]).astype(float).assign(horizon=ModelOutputConstants.HORIZONS)
    traces = []
    for coverage in bands:
        lower, upper = ScoringConstants.INTERVALS[coverage]
        edge = dict(mode="lines", line=dict(width=0, color=color), showlegend=False, hoverinfo="skip", **group)
        traces.append(go.Scatter(x=x, y=rows[lower], **edge))
        traces.append(go.Scatter(x=x, y=rows[upper], fill="tonexty", fillcolor=rgba(color, opacity), **edge))

    ranges = np.stack([rows[0.25], rows[0.75], rows[0.10], rows[0.90], rows[0.025], rows[0.975],
                       rows[0.01], rows[0.99], rows["horizon"]], axis=1)
    traces.append(go.Scatter(
        x=x, y=rows[0.5], mode="lines+markers", name=name, line=dict(color=color, width=2),
        marker=dict(size=8, color=color, line=dict(color=ctx.palette.surface, width=2)), customdata=ranges,
        hovertemplate=(f"<b>{name}</b> · horizon %{{customdata[8]}}<br>median %{{y:,.0f}}<br>"
                       "50%: %{customdata[0]:,.0f} – %{customdata[1]:,.0f}<br>"
                       "80%: %{customdata[2]:,.0f} – %{customdata[3]:,.0f}<br>"
                       "95%: %{customdata[4]:,.0f} – %{customdata[5]:,.0f}<br>"
                       "98%: %{customdata[6]:,.0f} – %{customdata[7]:,.0f}<extra></extra>"),
        **group))
    return traces


def _absent_note(ctx: ChartContext, absent: list, place: str, x: pd.Timestamp, y_top: float) -> go.Scatter:
    """Top-left of the plot: the models with no forecast for this place at this round (blank if none). A trace,
    not an annotation, so it changes with the round (see viz/replay.py)."""
    text = f"No forecast this round for {place} from: {', '.join(absent)}" if absent else ""
    return go.Scatter(x=[x], y=[y_top * 0.96], mode="text", text=[text], textposition="middle right",
                      textfont=dict(color=ctx.palette.ink, size=12), showlegend=False, hoverinfo="skip")


def _actual_markers(ctx: ChartContext, reference_date, observed: pd.Series) -> go.Scatter:
    p = ctx.palette
    actual = observed.reindex([add_weeks(reference_date, h) for h in ModelOutputConstants.HORIZONS])
    return go.Scatter(
        x=actual.index, y=actual.values, mode="markers", name="Actual",
        marker=dict(symbol="diamond", size=10, color=p.ink, line=dict(color=p.surface, width=2)),
        hovertemplate="actual: %{y:,.0f}<br>week ending %{x|%b %d, %Y}<extra></extra>")


def _reference_line(ctx: ChartContext, reference_date, y_bottom: float, y_top: float) -> go.Scatter:
    """A vertical line at the reference date, drawn as a trace so it moves with the slider."""
    p = ctx.palette
    return go.Scatter(
        x=[reference_date, reference_date], y=[y_bottom, y_top], mode="lines+text", text=["", " reference date"],
        textposition="bottom right", textfont=dict(color=p.muted, size=11), line=dict(color=p.axis, width=1),
        showlegend=False, hoverinfo="skip")


def _as_reported_then(ctx: ChartContext, published, reference_date, location: str, weeks: list) -> go.Scatter:
    """The data as reported on reference_date, on every week of the chart (blank where not reported yet)."""
    history = published(reference_date)
    if history is None:
        history = pd.DataFrame(columns=["date", "location", "value"])
    history = history[history["location"] == location].drop_duplicates("date", keep="last")
    values = history.set_index(pd.to_datetime(history["date"]))["value"].reindex(weeks)
    return go.Scatter(x=weeks, y=values.to_numpy(dtype=float), name="As reported then", mode="lines",
                      line=dict(color=ctx.palette.ink, width=2),
                      hovertemplate="as reported then: %{y:,.0f}<br>week ending %{x|%b %d, %Y}<extra></extra>")
