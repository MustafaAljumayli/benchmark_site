"""Chart functions. Each takes a ChartContext (theme, location names, model colors) first and returns
a Plotly figure. Charts that move through the season have a slider and Play button (see replay.py)."""
from benchmark_site.viz.charts.forecast import forecast_replay
from benchmark_site.viz.charts.leaderboard import leaderboard
from benchmark_site.viz.charts.runs import run_history
from benchmark_site.viz.charts.scores import coverage_replay, horizon_summary, score_timeline
from benchmark_site.viz.charts.state_map import state_map
from benchmark_site.viz.charts.surfaces import error_surface, rate_surface

__all__ = ["coverage_replay", "error_surface", "forecast_replay", "horizon_summary", "leaderboard", "rate_surface",
           "run_history", "score_timeline", "state_map"]
