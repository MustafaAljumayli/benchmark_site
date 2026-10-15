"""US map colored by how a model scored in each state, season to date at the round on the slider."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from benchmark_site.viz.charts.common import as_dict, date_label
from benchmark_site.viz.replay import add_replay, frame_name, start_index
from benchmark_site.viz.states import METRICS, STATE_ABBR, cumulative_by_state, log_ratio_ticks
from benchmark_site.viz.theme import REFERENCE_MODEL, ChartContext, colorscale, empty_figure, new_figure

NOT_ON_MAP = ["US", "72"]   # the national total and Puerto Rico have no shape on Plotly's US map
COVERAGE_TARGET = 95


def state_map(ctx: ChartContext, scores, model: str, metric: str = "relative", coverage=None,
              relative_to: str = REFERENCE_MODEL, selected: str | None = None, start=None) -> go.Figure:
    """metric: "relative" (log-WIS ÷ relative_to's: blue better, red worse), "wis" (mean log-WIS:
    darker is worse) or "coverage" (share of 95% intervals that contained what happened).
    Clicking a state sends its abbreviation in clickData (the site uses it to select the state)."""
    scores = as_dict(scores)
    if metric == "relative" and relative_to not in scores:
        metric = "wis"
    data = cumulative_by_state(scores, model, metric, as_dict(coverage) if coverage is not None else None, relative_to)
    data = data[data["location"].isin(STATE_ABBR) & ~data["location"].isin(NOT_ON_MAP)]
    title = f"{model} by state · {METRICS[metric]}"
    if data.empty:
        return empty_figure(ctx, f"{title}: no state forecasts to show")

    style = _metric_style(ctx, metric, data, relative_to)
    p = ctx.palette
    figure = new_figure(ctx, title, style["subtitle"], height=600)
    dates = sorted(data["reference_date"].unique())
    frames = []
    for reference_date in dates:
        rows = data[data["reference_date"] == reference_date]
        hover = [f"<b>{ctx.location_name(row.location)}</b><br>{style['describe'](row)}<br>"
                 f"{int(row.forecasts):,} forecasts · click to select" for row in rows.itertuples()]
        choropleth = go.Choropleth(
            locations=rows["location"].map(STATE_ABBR), z=style["z"](rows), locationmode="USA-states",
            text=hover, hovertemplate="%{text}<extra></extra>", marker=dict(line=dict(color=p.surface, width=1)),
            **style["colors"])
        frames.append(go.Frame(name=frame_name(reference_date), data=[choropleth], traces=[0]))

    add_replay(figure, ctx, frames, [date_label(d) for d in dates],
               len(dates) - 1 if start is None else start_index(dates, start), prefix="Season through round: ")
    figure.add_trace(_selected_outline(ctx, selected))
    figure.update_layout(
        geo=dict(scope="usa", projection=dict(type="albers usa"), bgcolor=p.surface, showlakes=False,
                 landcolor=p.grid, subunitcolor=p.surface),
        margin=dict(l=8, r=8, t=112), clickmode="event")
    return figure


def _metric_style(ctx: ChartContext, metric: str, data: pd.DataFrame, relative_to: str) -> dict:
    """Color scale, z values, subtitle and hover text for one metric."""
    p = ctx.palette
    colorbar = dict(thickness=12, len=0.75, outlinewidth=0, x=1.0, xanchor="left",
                    tickfont=dict(color=p.muted, size=11))

    if metric == "relative":
        tick_values, tick_text = log_ratio_ticks()
        return dict(
            # log2 of the ratio, so 2x worse and 2x better are the same distance from gray
            z=lambda rows: np.log2(rows["value"].clip(0.25, 4)),
            colors=dict(colorscale=colorscale(p.diverging), zmin=-1, zmax=1, zmid=0,
                        colorbar=dict(colorbar, tickvals=tick_values, ticktext=tick_text, title=dict(text="vs baseline"))),
            subtitle=f"Blue = better than {relative_to}, red = worse · season to date at the round on the slider",
            describe=lambda row: (f"{row.value:.2f}× {relative_to}<br>"
                                  f"log-WIS {row.model_wis:.3f} vs {row.reference_wis:.3f}"))

    if metric == "coverage":
        # red = intervals too narrow (below 95%), gray = calibrated (95%), blue = too wide
        low, high = 55, 100
        target = (COVERAGE_TARGET - low) / (high - low)
        stops = [0, target * 0.35, target * 0.7, target, target + (1 - target) / 3, target + 2 * (1 - target) / 3, 1]
        colors = list(reversed(p.diverging))
        return dict(
            z=lambda rows: rows["value"] * 100,
            colors=dict(colorscale=[[stop, color] for stop, color in zip(stops, colors)], zmin=low, zmax=high,
                        colorbar=dict(colorbar, ticksuffix="%", title=dict(text="inside 95%"))),
            subtitle="Calibrated ≈ 95% · red = intervals too narrow, blue = too wide · season to date",
            describe=lambda row: f"{row.value:.0%} of 95% intervals contained what happened")

    return dict(
        z=lambda rows: rows["value"],
        colors=dict(colorscale=colorscale(p.sequential), zmin=0, zmax=float(np.nanquantile(data["value"], 0.98)),
                    colorbar=dict(colorbar, title=dict(text="log-WIS"))),
        subtitle="Darker = larger error · season to date at the round on the slider",
        describe=lambda row: f"mean log-WIS {row.value:.3f}")


def _selected_outline(ctx: ChartContext, selected) -> go.Choropleth:
    """A thick outline around the selected state (an empty trace when no state is selected)."""
    abbreviation = STATE_ABBR.get(selected) if selected not in (None, "All", *NOT_ON_MAP) else None
    transparent = [[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]]
    return go.Choropleth(
        locations=[abbreviation] if abbreviation else [], z=[0] if abbreviation else [], locationmode="USA-states",
        colorscale=transparent, showscale=False, hoverinfo="skip",
        marker=dict(line=dict(color=ctx.palette.ink, width=2.5)))
