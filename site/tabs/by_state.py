"""Map tab ("by state"): every state colored by how a model scored there; pick a state to see its charts."""
import dash_mantine_components as dmc
from dash import Input, Output, State, no_update

from benchmark_site.site import components as ui
from benchmark_site.site.config import MAP_CONFIG, MAX_FORECAST_MODELS, REFERENCE_MODEL
from benchmark_site.site.data import state_table, summary_table
from benchmark_site.site.inputs import filter_states, load
from benchmark_site.site.tabs.forecasts import forecast_figure
from benchmark_site.viz import charts
from benchmark_site.viz.states import FIPS

METRICS = [("relative", "vs FluSight-baseline"), ("wis", "log-WIS"), ("coverage", "95% interval coverage")]


def render(selection, filters, ctx) -> list:
    if not selection.outputs:
        return [ui.message("No forecasts in this season for the selected models.")]
    if not any(len(table) for table in selection.scores().values()):
        return [ui.message("No scored forecasts in this season yet.",
                           "The weeks these rounds forecast haven't been reported yet. "
                           "See the Forecasts tab for the latest projections.")]
    model = selection.primary.label if selection.primary.label in selection.names else selection.names[0]
    metric = "relative" if selection.has_reference else "wis"
    metric_options = [(value, label) for value, label in METRICS if value != "relative" or selection.has_reference]

    map_controls = ui.controls(
        ui.labelled("Model", dmc.Select(id="map-model", data=selection.names, value=model, allowDeselect=False,
                                        w=280)),
        ui.labelled("Color by", ui.segmented("map-metric", metric_options, metric)),
    )
    map_and_table = dmc.Grid([
        dmc.GridCol(ui.graph(state_figure(selection, ctx, model, metric, filters.location), "state-map",
                             config=MAP_CONFIG), span={"base": 12, "lg": 8}),
        dmc.GridCol([dmc.Text("Best to worst · click a row to select", size="xs", c="dimmed", mb=4),
                     ui.clickable_table("state-table", state_table(selection, ctx, model, metric), filters.theme)],
                    span={"base": 12, "lg": 4}),
    ])
    sections = [ui.chart_card("state_map", map_and_table, map_controls)]

    if filters.chosen_location is None:
        sections.append(ui.message("Select a state to see every chart for it here.",
                                   "Click a state on the map, a row in the table, or use the Location filter."))
        return sections
    return sections + state_details(selection, filters, ctx)


def state_details(selection, filters, ctx) -> list:
    """The selected state's forecasts, scores by round and by horizon, and summary table."""
    location = filters.chosen_location
    place = ctx.location_name(location)
    scores = selection.scores()
    reference = REFERENCE_MODEL if selection.has_reference else None
    return [
        ui.chart_card("forecast", ui.graph(forecast_figure(selection, ctx, location, intervals=(
            "all" if len(selection.names) <= MAX_FORECAST_MODELS else "key"))),   # every model, with fewer bands
                      title=f"{place}: forecasts against what happened"),
        ui.chart_card("score_timeline", ui.graph(charts.score_timeline(ctx, scores, location, relative_to=reference)),
                      title=f"{place}: score over the season"),
        dmc.SimpleGrid(cols={"base": 1, "lg": 2}, children=[
            ui.chart_card("horizon_summary",
                          ui.graph(charts.horizon_summary(ctx, scores, relative_to=reference, location=location)),
                          title=f"{place}: by horizon"),
            ui.chart_card("summary_table", ui.simple_table(summary_table(scores, selection.coverage(), location)),
                          title=f"{place}: summary"),
        ]),
    ]


def state_figure(selection, ctx, model: str, metric: str, location):
    return charts.state_map(ctx, selection.scores(), model, metric, coverage=selection.coverage(),
                            relative_to=REFERENCE_MODEL, selected=location)


def register(app, paths) -> None:
    @app.callback(
        Output("state-map", "figure"), Output("state-table", "data"), Output("state-table", "columns"),
        Input("map-model", "value"), Input("map-metric", "value"), *filter_states(),
        prevent_initial_call=True)
    def update_map(model, metric, *values):
        selection, filters, ctx, _ = load(paths, *values)
        rows = state_table(selection, ctx, model, metric)
        columns = [{"name": column, "id": column} for column in rows.columns if column != "code"]
        return state_figure(selection, ctx, model, metric, filters.location), rows.to_dict("records"), columns

    @app.callback(Output("location", "value", allow_duplicate=True), Input("state-map", "clickData"),
                  prevent_initial_call=True)
    def select_clicked_state(click):
        points = (click or {}).get("points") or [{}]
        return FIPS.get(points[0].get("location"), no_update)

    @app.callback(Output("location", "value", allow_duplicate=True), Input("state-table", "active_cell"),
                  State("state-table", "derived_viewport_data"), prevent_initial_call=True)
    def select_clicked_row(cell, rows):
        if not cell or not rows:
            return no_update
        return rows[cell["row"]]["code"]
