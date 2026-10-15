"""Charts for backtests (Plotly), used by the benchmarking site and by notebooks.

    from benchmark_site.viz import Plotter2D, Plotter3D, save_html
    figure = Plotter2D(theme="light").forecast_replay(run.outputs, run.truth, location="13")
    figure.show()

Layout of this package:
  theme.py          colors, the Plotly template, ChartContext
  distributions.py  a forecast's 23 quantiles as one row per forecast
  replay.py         the slider and Play button
  states.py         state codes and season-to-date numbers for the map
  notes.py          each chart's research question and formulas
  charts/           one module per chart family
"""
from benchmark_site.viz.plotter2d import Plotter2D, save_html
from benchmark_site.viz.plotter3d import Plotter3D

__all__ = ["Plotter2D", "Plotter3D", "save_html"]
