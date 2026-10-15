"""Every saved backtest run on one chart."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from benchmark_site.viz.theme import ChartContext, model_colors, new_figure


def run_history(ctx: ChartContext, runs: pd.DataFrame, highlight: list[str] | None = None) -> go.Figure:
    """Mean log-WIS of every saved backtest, oldest to newest. `runs` comes from flusight.runs.list_runs()
    (sorted by when each backtest ran); `highlight` lists backtest names to draw larger.
    Backtests are not a time series of the season, so this chart has no slider."""
    p = ctx.palette
    figure = new_figure(ctx, "Backtests", "Mean log-WIS of each saved backtest, oldest to newest · lower is better",
                        height=420)
    if runs.empty:
        return figure
    runs = runs.assign(order=range(len(runs)))   # x position: 0 = oldest

    models = list(dict.fromkeys(runs["model"]))
    colors = model_colors(models, ctx.theme)
    figure.add_trace(go.Scatter(x=runs["order"], y=runs["mean_wis"], mode="lines", showlegend=False,
                                line=dict(color=p.axis, width=1.5), hoverinfo="skip"))
    for model in models:
        model_runs = runs[runs["model"] == model]
        coverage_95 = [c.get("95%") if isinstance(c, dict) else None for c in model_runs["coverage"]]
        details = np.stack([
            model_runs["label"], model_runs["first_reference_date"], model_runs["last_reference_date"],
            model_runs["tasks"], ["–" if c is None else f"{c:.0%}" for c in coverage_95], model_runs["created_at"],
        ], axis=1)
        figure.add_trace(go.Scatter(
            x=model_runs["order"], y=model_runs["mean_wis"], mode="markers+text", name=model,
            text=[f"{wis:.3f}" for wis in model_runs["mean_wis"]], textposition="top center", textfont=dict(color=p.ink_secondary, size=11),
            marker=dict(size=[14 if highlight and name in highlight else 10 for name in model_runs["label"]],
                        color=colors[model], line=dict(color=p.surface, width=2)),
            customdata=details,
            hovertemplate=("<b>%{customdata[0]}</b><br>mean log-WIS %{y:.3f}<br>"
                           "rounds %{customdata[1]} → %{customdata[2]}<br>"
                           "%{customdata[3]:,} forecasts · 95% interval coverage %{customdata[4]}<br>"
                           "ran %{customdata[5]}<extra></extra>")))

    low, high = float(runs["mean_wis"].min()), float(runs["mean_wis"].max())
    padding = max((high - low) * 0.25, 0.02)
    figure.update_layout(
        xaxis=dict(title="Backtest", tickmode="array", tickvals=list(runs["order"]), ticktext=list(runs["label"]),
                   showgrid=False, range=[-0.5, len(runs) - 0.5]),
        yaxis=dict(title="Mean log-WIS", range=[low - padding, high + padding]),
        margin=dict(b=72))
    return figure
