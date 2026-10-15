"""Plotter2D: the 2D charts for notebooks, with the theme and model colors set once.

    from benchmark_site.viz import Plotter2D, save_html
    plotter = Plotter2D(theme="light", location_names={"13": "Georgia"})
    figure = plotter.forecast_replay({"RegEns": run.outputs}, run.truth, location="13")
    save_html(figure, "georgia.html")

Every method takes the same uniform inputs, so it works for any model, ours or a hub team's:
  outputs   {name: model output in the hub format}       (flusight/model_output.py)
  truth     date, location, value[, weekly_rate]         (final observed data)
  scores    {name: flusight.scoring_m.wis(output, truth)}
  coverage  {name: flusight.scoring_m.coverage(output, truth)}
A single DataFrame is accepted wherever a dict is expected. The chart code lives in benchmark_site/viz/charts.
"""
import plotly.graph_objects as go

from benchmark_site.viz import charts
from benchmark_site.viz.replay import REPLAY_SCRIPT
from benchmark_site.viz.theme import ChartContext


class Plotter2D:
    def __init__(self, theme: str = "light", location_names: dict | None = None, colors: dict | None = None):
        self.ctx = ChartContext(theme, location_names or {}, dict(colors or {}))

    def forecast_replay(self, outputs, truth, location, intervals="all", published=None, log_y=False,
                        start=None) -> go.Figure:
        return charts.forecast_replay(self.ctx, outputs, truth, location, intervals, published, log_y, start)

    def score_timeline(self, scores, location=None, horizon=None, relative_to=None, start=None) -> go.Figure:
        return charts.score_timeline(self.ctx, scores, location, horizon, relative_to, start)

    def horizon_summary(self, scores, relative_to=None, location=None, start=None) -> go.Figure:
        return charts.horizon_summary(self.ctx, scores, relative_to, location, start)

    def coverage_replay(self, coverage, location=None, horizon=None, start=None) -> go.Figure:
        return charts.coverage_replay(self.ctx, coverage, location, horizon, start)

    def state_map(self, scores, model, metric="relative", coverage=None, relative_to="FluSight-baseline",
                  selected=None, start=None) -> go.Figure:
        return charts.state_map(self.ctx, scores, model, metric, coverage, relative_to, selected, start)

    def run_history(self, runs, highlight=None) -> go.Figure:
        return charts.run_history(self.ctx, runs, highlight)


def save_html(figure: go.Figure, path) -> None:
    """Write a chart to a standalone HTML file that works offline. It opens paused on its start round;
    plain figure.write_html() would start playing the replay as soon as the file opens."""
    figure.write_html(path, include_plotlyjs=True, auto_play=False, full_html=True, post_script=REPLAY_SCRIPT)
