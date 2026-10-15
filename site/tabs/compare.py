"""Compare tab: scores over the season, by horizon, calibration, and errors in 3D, for every selected model."""
import dash_mantine_components as dmc
from dash import Input, Output

from benchmark_site.site import components as ui
from benchmark_site.site.config import REFERENCE_MODEL, SURFACE_HEIGHT
from benchmark_site.site.data import summary_table
from benchmark_site.site.inputs import filter_states, load
from benchmark_site.viz import charts


def score_figures(selection, filters, ctx, relative: bool, only_horizon: bool):
    """The score timeline and the by-horizon bars, which share the 'relative' switch."""
    scores = selection.scores()
    reference = REFERENCE_MODEL if relative and selection.has_reference else None
    horizon = filters.horizon if only_horizon and filters.horizon >= 0 else None
    location = filters.chosen_location
    return (charts.score_timeline(ctx, scores, location, horizon, relative_to=reference),
            charts.horizon_summary(ctx, scores, relative_to=reference, location=location))


def error_surface_models(selection) -> dict:
    """The selected run against FluSight-ensemble if it is shown, otherwise against the next model."""
    scores = selection.scores()
    names = list(scores)
    partner = "FluSight-ensemble" if "FluSight-ensemble" in names[1:] else (names[1] if len(names) > 1 else None)
    return {name: scores[name] for name in [names[0], partner] if name}


def render(selection, filters, ctx) -> list:
    if not selection.outputs:
        return [ui.message("No forecasts in this season for the selected models.")]
    relative = selection.has_reference
    timeline, by_horizon = score_figures(selection, filters, ctx, relative, only_horizon=False)
    score_controls = ui.controls(
        dmc.Switch(id="compare-relative", label=f"Relative to {REFERENCE_MODEL}", checked=relative,
                   disabled=not selection.has_reference),
        dmc.Switch(id="compare-one-horizon", label=f"Only horizon {filters.horizon}", checked=False,
                   disabled=filters.horizon < 0),
    )
    location = filters.chosen_location
    return [
        ui.chart_card("score_timeline", ui.graph(timeline, "timeline-graph"), score_controls),
        dmc.SimpleGrid(cols={"base": 1, "lg": 2}, children=[
            ui.chart_card("horizon_summary", ui.graph(by_horizon, "horizon-graph")),
            ui.chart_card("coverage", ui.graph(charts.coverage_replay(ctx, selection.coverage(), location))),
        ]),
        ui.chart_card("error_surface", ui.graph(charts.error_surface(ctx, error_surface_models(selection), location),
                                                height=SURFACE_HEIGHT)),
        ui.chart_card("summary_table", ui.simple_table(summary_table(selection.scores(), selection.coverage(),
                                                                     location))),
    ]


def register(app, paths) -> None:
    @app.callback(
        Output("timeline-graph", "figure"), Output("horizon-graph", "figure"),
        Input("compare-relative", "checked"), Input("compare-one-horizon", "checked"), *filter_states(),
        prevent_initial_call=True)
    def update_scores(relative, only_horizon, *values):
        selection, filters, ctx, _ = load(paths, *values)
        return score_figures(selection, filters, ctx, bool(relative), bool(only_horizon))
