"""The filter controls every chart depends on, and turning their values into chart-ready data."""
from dash import Input, State

from benchmark_site.site.config import Paths
from benchmark_site.site.data import Filters, Selection, chart_context

# (component id, property) for each control in the side panel, in Filters.from_controls order
FILTER_CONTROLS = [
    ("run", "value"),
    ("compare-runs", "value"),
    ("hub-models", "value"),
    ("season", "value"),
    ("location", "value"),
    ("horizon", "value"),
    ("dark-mode", "checked"),
]


def filter_inputs() -> list[Input]:
    return [Input(component, prop) for component, prop in FILTER_CONTROLS]


def filter_states() -> list[State]:
    """For callbacks of a tab's own controls: they read the filters but aren't triggered by them."""
    return [State(component, prop) for component, prop in FILTER_CONTROLS] + [State("colors", "data")]


def load(paths: Paths, *values):
    """Filter values (+ the color registry last) -> (Selection, Filters, ChartContext, color registry)."""
    *filter_values, registry = values
    filters = Filters.from_controls(*filter_values)
    selection = Selection(filters, paths)
    ctx, registry = chart_context(selection, filters, registry)
    return selection, filters, ctx, registry
