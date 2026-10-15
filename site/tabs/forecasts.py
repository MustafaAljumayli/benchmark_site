"""Forecasts tab: forecasts against what happened, and flu across every state in 3D."""
import dash_mantine_components as dmc
from dash import Input, Output

from flusight.data import observed
from benchmark_site.site import components as ui
from benchmark_site.site.config import MAX_FORECAST_MODELS, SURFACE_HEIGHT
from benchmark_site.site.data import vintages
from benchmark_site.site.inputs import filter_states, load
from benchmark_site.viz import charts

INTERVAL_OPTIONS = [("all", "All 11 intervals"), ("key", "50% and 95% only")]


def shown_models(selection, intervals: str = "all") -> list[str]:
    """The models drawn: all of them with the 50% and 95% bands, the first few with all 11 bands."""
    return selection.names[:MAX_FORECAST_MODELS] if intervals == "all" else selection.names


def forecast_figure(selection, ctx, location: str, intervals: str = "all", as_reported: bool = False,
                    log_y: bool = False):
    """The selected models' forecasts for one location."""
    shown = {name: selection.outputs[name] for name in shown_models(selection, intervals)}
    published = (lambda date: observed(vintages().archived(date))) if as_reported else None   # admissions only
    return charts.forecast_replay(ctx, shown, selection.truth, location, intervals, published, log_y)


def render(selection, filters, ctx) -> list:
    if not selection.outputs:
        return [ui.message("No forecasts in this season for the selected models.")]
    notes = []
    if filters.chosen_location is None:
        notes.append("Showing the US total; pick a state in Location to see it instead.")
    hidden = [name for name in selection.names if name not in shown_models(selection)]
    if hidden:
        notes.append(f"With all 11 intervals only {MAX_FORECAST_MODELS} models fit; not shown: {', '.join(hidden)}. "
                     "Choose \"50% and 95% only\" to see every selected model.")
    place = ctx.location_name(filters.chart_location)
    missing = [name for name, output in selection.outputs.items() if not (output["location"] == filters.chart_location).any()]
    alerts = []
    if missing:   # e.g. Google_SAI-FluEns forecasts the states but not the US total
        alerts.append(dmc.Alert(f"{', '.join(missing)} made no forecasts for {place} this season, so nothing of theirs "
                                "is drawn here. Pick a state in Location to see their forecasts.",
                                title=f"No {place} forecasts from {', '.join(missing)}", color="yellow", variant="light"))

    forecast_controls = ui.controls(
        ui.labelled("Intervals", ui.segmented("forecast-intervals", INTERVAL_OPTIONS, "all")),
        dmc.Switch(id="forecast-as-reported", label="Data as reported on each forecast date (first use: ~10 s)"),
        dmc.Switch(id="forecast-log-y", label="Log scale"),
    )
    model = selection.primary.label if selection.primary.label in selection.outputs else selection.names[0]
    rate_figure = charts.rate_surface(ctx, selection.truth, selection.outputs[model], model)
    return [
        ui.chart_card("forecast", dmc.Stack([
            *alerts,
            *(dmc.Text(note, size="xs", c="dimmed") for note in notes),
            ui.graph(forecast_figure(selection, ctx, filters.chart_location), "forecast-graph"),
        ], gap=4), forecast_controls),
        ui.chart_card("rate_surface", ui.graph(rate_figure, height=SURFACE_HEIGHT + 40)),
    ]


def register(app, paths) -> None:
    @app.callback(
        Output("forecast-graph", "figure"),
        Input("forecast-intervals", "value"), Input("forecast-as-reported", "checked"),
        Input("forecast-log-y", "checked"), *filter_states(),
        prevent_initial_call=True)
    def update_forecasts(intervals, as_reported, log_y, *values):
        selection, filters, ctx, _ = load(paths, *values)
        return forecast_figure(selection, ctx, filters.chart_location, intervals, bool(as_reported), bool(log_y))
