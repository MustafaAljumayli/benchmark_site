"""Model leaderboard tab: every hub model and our backtests, ranked by relative WIS as CDC ranks them."""
import dash_mantine_components as dmc
from dash import Input, Output, html

from benchmark_site.site import components as ui
from benchmark_site.site.inputs import filter_states, load
from benchmark_site.site.leaderboard import (CDC_REPORTS, cdc_leaderboard, evaluation_season, leaderboard,
                                            matches_cdc, matches_cdc_evaluation)
from benchmark_site.viz import charts

from flusight.constants import CDCEvaluationConstants

LATEST = "latest"
EVALUATION = "cdc-evaluation"   # CDC's end-of-season evaluation rules (the official ranking)


def evaluation_section(paths, filters, ctx) -> list:
    """The board under CDC's end-of-season rules, with how well it matches CDC's published table."""
    backtests = tuple(dict.fromkeys(name for name in [filters.run, *filters.compare_runs] if name))
    if filters.chosen_location is not None:
        return [ui.message("CDC's evaluation ranks models over all jurisdictions together.",
                           "Clear the location filter, or choose \"Latest data\" to rank one location.")]
    board = cdc_leaderboard(paths, filters.season, backtests)
    if board.empty:
        return [ui.message("CDC published no end-of-season evaluation for this season.", "")]
    season = evaluation_season(filters.season)
    matched, published = matches_cdc_evaluation(board)
    sections = [dmc.Alert(
        f"Hub models: our relative WIS rounds to CDC's published value for {matched} of {published} models. "
        f"Source: {CDCEvaluationConstants.SEASONS[season]['url']}. Our backtests are ranked as if submitted ("
        "\"Rank if submitted\"); they are retrospective, not real-time forecasts, and their settings were chosen "
        "on these same seasons, so treat their rank as optimistic. \"Eligible\" is CDC's 75% rule.",
        title="CDC end-of-season evaluation" + (" reproduced" if matched == published else ": differs from CDC"),
        color="green" if matched == published else "yellow", variant="light", mb="sm")]
    shown = board.round({"Log relative WIS": 3, "Log WIS": 3, "50% coverage": 1, "95% coverage": 1,
                         "% of Forecasts Submitted": 1, "CDC log relative WIS": 2})
    return sections + [ui.graph(charts.leaderboard(ctx, board)),
                       dmc.Text("Click a column to sort", size="xs", c="dimmed", mt="sm", mb=4),
                       ui.clickable_table("leaderboard-table", shown, filters.theme, hidden=(), page_size=25)]


def board_section(paths, filters, ctx, scored_against: str) -> list:
    """The ranking chart and table for the current filters."""
    if scored_against == EVALUATION:
        return evaluation_section(paths, filters, ctx)
    report = CDC_REPORTS.get(filters.season)
    as_of = report["as_of"] if scored_against != LATEST and report else None
    backtests = tuple(dict.fromkeys(name for name in [filters.run, *filters.compare_runs] if name))
    board = leaderboard(paths, filters.season, filters.chosen_location, as_of, backtests)
    if board.empty:
        return [ui.message("No hub forecasts to rank in this season.",
                           "The leaderboard ranks the rounds FluSight-baseline forecast; download them with "
                           "python download_data.py, or pick another season.")]
    sections = []
    ineligible = board.loc[~board["Eligible"], "Model"].tolist()
    if ineligible:
        sections.append(dmc.Alert(
            f"{len(ineligible)} models made under 75% of FluSight-baseline's forecasts this season and are listed last: "
            f"{', '.join(ineligible)}. CDC doesn't rank them; their scores cover only the weeks or places they forecast.",
            title="Partial submissions", color="gray", variant="light", mb="sm"))
    matched, published = matches_cdc(board)
    if published:
        sections.append(dmc.Alert(
            f"Our log relative WIS and relative WIS match CDC's published values for {matched} of {published} "
            f"models (to the 2 decimals CDC publishes). Source: {report['source']}.",
            title="Reproduces CDC's report" if matched == published else "Differs from CDC's report",
            color="green" if matched == published else "yellow", variant="light", mb="sm"))
    shown = board.round({"Log relative WIS": 3, "Relative WIS": 3, "WIS": 2, "MAE": 2, "50% coverage": 1,
                         "95% coverage": 1, "CDC log relative WIS": 2, "CDC relative WIS": 2})
    return sections + [ui.graph(charts.leaderboard(ctx, board)),
                       dmc.Text("Click a column to sort", size="xs", c="dimmed", mt="sm", mb=4),
                       ui.clickable_table("leaderboard-table", shown, filters.theme, hidden=(), page_size=25)]


def render(selection, filters, ctx) -> list:
    report = CDC_REPORTS.get(filters.season)
    official = evaluation_season(filters.season) is not None
    options = ([(EVALUATION, "CDC end-of-season evaluation")] if official else []) + [(LATEST, "Latest data")] + \
              ([("cdc", report["label"])] if report else [])
    default = EVALUATION if official else LATEST
    scope = ("the 50 states, DC and Puerto Rico" if filters.chosen_location is None
             else ctx.location_name(filters.chosen_location))
    controls = ui.controls(
        ui.labelled("Scored against", ui.segmented("leaderboard-truth", options, default)),
        dmc.Text(f"Horizons 0-3 · {scope} · every downloaded hub model, plus the selected backtests and any other "
                 "hub-format forecasts in data/model-output, which are ranked against the hub models without changing their scores. "
                 "The first visit takes a few seconds per season while every model is scored.", size="xs", c="dimmed"),
    )
    return [ui.chart_card("leaderboard", html.Div(board_section(selection.paths, filters, ctx, default),
                                                  id="leaderboard-content"), controls)]


def register(app, paths) -> None:
    @app.callback(Output("leaderboard-content", "children"), Input("leaderboard-truth", "value"), *filter_states(),
                  prevent_initial_call=True)
    def update_leaderboard(scored_against, *values):
        _, filters, ctx, _ = load(paths, *values)
        return board_section(paths, filters, ctx, scored_against)
