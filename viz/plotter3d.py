"""Plotter3D: the 3D surfaces for notebooks. Same inputs and options as Plotter2D."""
import plotly.graph_objects as go

from benchmark_site.viz import charts
from benchmark_site.viz.plotter2d import Plotter2D


class Plotter3D(Plotter2D):
    def error_surface(self, scores, location=None, start=None) -> go.Figure:
        return charts.error_surface(self.ctx, scores, location, start)

    def rate_surface(self, truth, output, name="model", start=None) -> go.Figure:
        return charts.rate_surface(self.ctx, truth, output, name, start=start)
