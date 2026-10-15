"""Every model ranked by relative WIS, as one bar each."""
import pandas as pd
import plotly.graph_objects as go

from benchmark_site.viz.theme import REFERENCE_MODEL, ChartContext, new_figure

ENSEMBLE = "FluSight-ensemble"


def leaderboard(ctx: ChartContext, board: pd.DataFrame, column: str = "Log relative WIS") -> go.Figure:
    """One bar per model, best at the top, with a line at 1 (FluSight-baseline). `board` comes from
    benchmark_site.site.leaderboard.leaderboard(): Model, Source, the score columns. Our backtests are
    drawn in the first series color, FluSight-ensemble in the second, the baseline in gray."""
    p = ctx.palette
    board = board.sort_values(column, ascending=False)   # Plotly draws the first bar at the bottom
    colors = [p.series[0] if source == "our backtest" else p.series[1] if model == ENSEMBLE
              else p.reference if model == REFERENCE_MODEL else p.grid
              for model, source in zip(board["Model"], board["Source"])]
    ours = board["Source"] == "our backtest"
    name = column[0].lower() + column[1:]   # "log relative WIS"
    figure = new_figure(ctx, f"Models ranked by {name}",
                        "1 = as good as FluSight-baseline · lower is better · blue = our backtests",
                        height=max(420, 22 * len(board) + 170))
    figure.add_trace(go.Bar(
        x=board[column], y=board["Model"], orientation="h", marker=dict(color=colors, line=dict(width=0)),
        text=[f"{value:.2f}" for value in board[column]], textposition="outside", cliponaxis=False,
        textfont=dict(color=p.ink_secondary, size=11),
        customdata=board[["Rank", "Forecasts scored", "Locations"]].to_numpy(),
        hovertemplate=(f"<b>%{{y}}</b> · rank %{{customdata[0]}}<br>{name} %{{x:.3f}}<br>"
                       "%{customdata[1]:,} forecasts scored in %{customdata[2]} locations<extra></extra>")))
    figure.add_vline(x=1, line=dict(color=p.axis, width=1, dash="dot"))
    figure.update_layout(
        showlegend=False, bargap=0.25, margin=dict(l=8, r=48, t=96, b=48),
        xaxis=dict(title=f"{column} (FluSight-baseline = 1)", showgrid=True, rangemode="tozero"),
        yaxis=dict(showgrid=False, automargin=True, tickfont=dict(size=11),
                   ticktext=[f"<b>{m}</b>" if our else m for m, our in zip(board["Model"], ours)],
                   tickvals=list(board["Model"])))
    return figure
