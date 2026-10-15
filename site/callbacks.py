"""Callbacks for the header and the filter panel, and the one that renders the selected tab.
Each tab's own controls have their callbacks in benchmark_site/site/tabs/<tab>.py."""
from dash import Input, Output, State

from flusight.data import DataLoader
from benchmark_site.site import components as ui
from benchmark_site.site.config import DEFAULT_HUB_MODELS, MAX_MODELS, Paths
from benchmark_site.site.data import (default_season, list_runs, load_run, location_options, model_seasons,
                                      other_targets, season_label, season_options)
from benchmark_site.site.inputs import filter_inputs, load
from benchmark_site.site.tabs import TAB_MODULES


def model_label(model: str) -> str:
    """A hub model as listed in the picker: the seasons it has weekly-admission forecasts for (what the site
    shows), and what it forecast instead in other seasons."""
    seasons = ", ".join(season_label(s) for s in model_seasons(model)) or "no weekly admissions"
    other = other_targets(model)
    return f"{model} ({seasons}{'; ' + other if other else ''})"


def no_data_message(name: str, season, hub: bool):
    """Why a selected model draws nothing this season."""
    season_text = season_label(season)
    other = other_targets(name, season) if hub else ""
    if other:   # it has files this season, but none of weekly admissions
        title = f"No weekly-admission forecasts from {name} in {season_text}; it forecast {other.split(': ', 1)[1]}."
    else:
        seasons = ", ".join(season_label(s) for s in model_seasons(name)) if hub else ""
        title = f"No forecasts from {name} in {season_text}" + (f"; its weekly-admission forecasts are in {seasons}." if seasons else ".")
    return ui.message(title, "The site draws and scores weekly hospital admissions (the target CDC scores), so nothing is "
                             "shown for this model here.")


def register(app, paths: Paths) -> None:
    @app.callback(Output("provider", "forceColorScheme"), Input("dark-mode", "checked"))
    def apply_color_scheme(dark_mode):
        return "dark" if dark_mode else "light"

    @app.callback(
        Output("run", "data"), Output("run", "value"),
        Output("hub-models", "data"), Output("hub-models", "value"), Output("subtitle", "children"),
        Input("reload", "n_clicks"), State("run", "value"), State("hub-models", "value"))
    def load_runs_and_models(_, current_run, current_models):
        """On page load and on "Reload runs": list the saved backtests (newest first) and the hub models."""
        table = list_runs(paths)
        models = DataLoader.list_model_output()
        chosen_models = current_models if current_models is not None else \
            [model for model in DEFAULT_HUB_MODELS if model in models]
        hub_note = f"{len(models)} hub models downloaded"
        # each model labelled with the seasons it forecast, so it's clear which seasons it can be compared in
        models = [{"value": m, "label": model_label(m)} for m in models]
        if table.empty:
            return [], None, models, chosen_models, f"No backtests yet in {paths.backtests} · {hub_note}"
        options = [{"value": row.label, "label": row.label} for row in table.iloc[::-1].itertuples()]
        names = list(table["label"])
        run = current_run if current_run in names else names[-1]
        return options, run, models, chosen_models, f"{len(names)} saved backtests · {hub_note}"

    @app.callback(
        Output("compare-runs", "data"), Output("compare-runs", "value"),
        Output("season", "data"), Output("season", "value"),
        Output("location", "data"), Output("location", "value"),
        Input("run", "value"), State("compare-runs", "value"), State("season", "value"), State("location", "value"))
    def run_changed(run_value, compared, season, location):
        """A new backtest sets which backtests it can be compared with, its seasons and its locations."""
        if not run_value:
            return [], [], [], None, [], None
        names = list(list_runs(paths)["label"])   # oldest first
        others = [name for name in names if name != run_value]
        compare_options = [{"value": name, "label": name} for name in reversed(others)]
        if compared is None:   # first load: compare with the backtest before this one
            earlier = names[:names.index(run_value)] if run_value in names else []
            compared = earlier[-1:]
        compared = [value for value in compared if value != run_value]

        run = load_run(paths, run_value)
        seasons = season_options(run)
        season = season if season in [option["value"] for option in seasons] else default_season(run)
        return compare_options, compared, seasons, season, location_options(run), location or "All"

    @app.callback(Output("content", "children"), Output("colors", "data"),
                  Input("tab", "value"), *filter_inputs(), State("colors", "data"))
    def render_tab(tab, *values):
        """Draw the selected tab for the current filters."""
        run_value, registry = values[0], values[-1]
        if not run_value:
            return [ui.message("No backtest runs found.", "Run one with:  python run_backtest.py --model RegEns")], \
                registry
        selection, filters, ctx, registry = load(paths, *values)
        notes = [ui.message(f"Not shown: {', '.join(selection.dropped)}",
                            f"At most {MAX_MODELS} models are shown at once (the selected run, then the compared runs, "
                            "then the hub models). Remove a compared run to make room.")] if selection.dropped else []
        for name in selection.no_data:
            notes.append(no_data_message(name, filters.season, hub=name in filters.hub_models))
        gaps = selection.gaps()
        if gaps:
            notes.append(ui.gaps_alert(gaps, season_label(filters.season)))
        return notes + TAB_MODULES[tab].render(selection, filters, ctx), registry

    for module in TAB_MODULES.values():
        module.register(app, paths)
