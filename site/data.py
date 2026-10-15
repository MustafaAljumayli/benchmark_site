"""Everything the site reads and computes, kept apart from layout and callbacks.

A Selection is the data behind the current filters: the chosen run, the runs and hub models it is
compared with, their forecasts for the chosen season, the observed data, and their scores.
Every model is scored against the *selected run's* truth, so all models are judged on the same data.
"""
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from flusight import runs
from flusight.data import DataLoader
from flusight.scoring_m import coverage, wis
from benchmark_site.site.config import MAX_MODELS, REFERENCE_MODEL, Paths
from benchmark_site.viz.charts.common import SCORED_HORIZONS, shared_forecasts
from benchmark_site.viz.states import METRICS, cumulative_by_state
from benchmark_site.viz.theme import ChartContext, palette

ALL_SEASONS = "all"
ALL_LOCATIONS = "All"


# ---------------------------------------------------------------- filters

@dataclass
class Filters:
    """The values of the filter controls in the side panel."""
    run: str | None             # a backtest's folder name, e.g. "2026-10-05-linreg"
    compare_runs: list[str]
    hub_models: list[str]
    season: str
    location: str
    horizon: int
    theme: str

    @classmethod
    def from_controls(cls, run, compare_runs, hub_models, season, location, horizon, dark_mode) -> "Filters":
        """Controls hold strings (Mantine selects only take strings); convert them here, once."""
        return cls(
            run=run or None,
            compare_runs=list(compare_runs or []),
            hub_models=list(hub_models or []),
            season=season or ALL_SEASONS,
            location=location or ALL_LOCATIONS,
            horizon=int(horizon) if horizon is not None else 1,
            theme="dark" if dark_mode else "light",
        )

    @property
    def chosen_location(self) -> str | None:
        return None if self.location == ALL_LOCATIONS else self.location

    @property
    def chart_location(self) -> str:
        """Charts for one place show the US total until a state is chosen."""
        return self.chosen_location or "US"


# ---------------------------------------------------------------- seasons

def season_of(date) -> int:
    """The season a forecast round belongs to; 2025 = the 2025/26 season. FluSight seasons end in May, so
    a season runs June through May and every round after the 2025/26 season counts toward 2026/27."""
    date = pd.Timestamp(date)
    return date.year if date.month >= 6 else date.year - 1


def in_season(table: pd.DataFrame, season: str) -> pd.DataFrame:
    if season == ALL_SEASONS:
        return table
    start = pd.Timestamp(f"{int(season)}-06-01")
    end = pd.Timestamp(f"{int(season) + 1}-06-01")
    return table[(table["reference_date"] >= start) & (table["reference_date"] < end)]


def season_options(run: runs.Run) -> list[dict]:
    """Every season the backtest forecast, newest first. A season still being reported is marked
    "in progress" (its newest rounds have no observed values yet), or "forecasts only" if none have."""
    rounds = pd.Series(pd.to_datetime(run.outputs["reference_date"].unique()))
    last_reported = pd.Timestamp(run.truth["date"].max())
    options = []
    for season in sorted(rounds.map(season_of).unique(), reverse=True):
        dates = rounds[rounds.map(season_of) == season]
        note = ("" if dates.max() <= last_reported else
                " · in progress" if dates.min() <= last_reported else " · forecasts only")
        options.append({"value": str(season), "label": f"{season}/{str(season + 1)[2:]}{note}"})
    return options + [{"value": ALL_SEASONS, "label": "All seasons"}]


def default_season(run: runs.Run) -> str:
    """The newest season with scored forecasts, so the site opens on scores rather than an empty map."""
    scored = sorted({season_of(d) for d in run.scores["reference_date"].unique()})
    return str(scored[-1]) if scored else season_options(run)[0]["value"]


def expected_rounds(season: str, forecast_rounds: set) -> set:
    """The rounds a model could have forecast: the hub's rounds (hub-config/tasks.json) in the season, between
    the first and last round any selected model forecast. Without the hub's list, every selected model's rounds."""
    if not forecast_rounds:
        return set()
    try:
        from flusight.releases import official_rounds
        rounds = set(official_rounds())
    except FileNotFoundError:
        return set(forecast_rounds)
    first, last = min(forecast_rounds), max(forecast_rounds)
    return {d for d in rounds if first <= d <= last and (season == ALL_SEASONS or season_of(d) == int(season))}


def _dates(dates: list, shown: int = 6) -> str:
    text = ", ".join(f"{d:%b} {d.day}, {d.year}" for d in dates[:shown])
    return text + (f" and {len(dates) - shown} more" if len(dates) > shown else "")


def season_label(season) -> str:
    return "all seasons" if season == ALL_SEASONS else f"{int(season)}/{str(int(season) + 1)[2:]}"


TARGET_NAMES = {"wk inc flu hosp": "weekly admissions", "wk inc flu prop ed visits": "ED visits",
                "wk flu hosp rate change": "rate change", "peak inc flu hosp": "peak incidence",
                "peak week inc flu hosp": "peak week"}
SITE_TARGET = "wk inc flu hosp"   # every chart and score on the site is of weekly admissions, the target CDC scores
TARGETS_INDEX = DataLoader.data_dir / "model-output" / ".targets-index.json"


@lru_cache(maxsize=1)
def _targets_index() -> dict:
    """File name -> the targets in it, for every downloaded forecast file. Only files not seen before are read
    (two columns each); the index is kept in data/model-output/.targets-index.json."""
    import json
    import pyarrow.parquet as pq
    index = json.loads(TARGETS_INDEX.read_text()) if TARGETS_INDEX.exists() else {}
    changed = False
    for model in DataLoader.list_model_output():
        for path in DataLoader.forecast_files(model):
            key = f"{model}/{path.name}"
            if key in index:
                continue
            if path.suffix == ".parquet":
                frame = pq.read_table(path, columns=["target", "output_type"]).to_pandas()
            else:
                frame = DataLoader.load_model_output(model, path.stem[:10], path.stem[:10]).assign(output_type="quantile")
            index[key] = sorted(frame.loc[frame["output_type"] == "quantile", "target"].unique().tolist()
                                + [t + " (pmf)" for t in frame.loc[frame["output_type"] != "quantile", "target"].unique()])
            changed = True
    if changed:
        TARGETS_INDEX.write_text(json.dumps(index))
    return index


@lru_cache(maxsize=256)
def model_targets(model: str) -> dict:
    """Season -> the targets a hub model forecast that season (from its files; see _targets_index)."""
    index, by_season = _targets_index(), {}
    for path in DataLoader.forecast_files(model):
        targets = index.get(f"{model}/{path.name}", [])
        by_season.setdefault(season_of(path.stem[:10]), set()).update(t.removesuffix(" (pmf)") for t in targets)
        if SITE_TARGET in targets:
            by_season[season_of(path.stem[:10])].add("site")   # weekly-admission quantiles, what the site draws
    return by_season


def model_seasons(model: str) -> tuple:
    """The seasons a hub model has weekly-admission quantile forecasts for: what the site can show."""
    return tuple(sorted(s for s, targets in model_targets(model).items() if "site" in targets))


def other_targets(model: str, season=None) -> str:
    """What a model forecast in seasons (or one season) where it has no weekly-admission forecasts, in words."""
    found = {s: t for s, t in model_targets(model).items() if "site" not in t and (season in (None, ALL_SEASONS) or s == int(season))}
    return "; ".join(f"{season_label(s)}: {', '.join(sorted(TARGET_NAMES.get(x, x) for x in t))} only"
                     for s, t in sorted(found.items()))


# ---------------------------------------------------------------- locations

def location_names(truth: pd.DataFrame) -> dict:
    """Location code -> name, from the hub's locations.csv and the run's truth."""
    known = DataLoader.load_locations()
    names = dict(zip(known["location"], known["location_name"]))
    if "location_name" in truth.columns:
        names.update(zip(truth["location"], truth["location_name"]))
    return names


def location_options(run: runs.Run) -> list[dict]:
    names = location_names(run.truth)
    codes = sorted(run.outputs["location"].unique(), key=lambda code: (code != "US", names.get(code, code)))
    return [{"value": ALL_LOCATIONS, "label": "All locations"}] + \
           [{"value": code, "label": names.get(code, code)} for code in codes]


def with_weekly_rate(truth: pd.DataFrame) -> pd.DataFrame:
    """Add weekly_rate (admissions per 100k) if the run didn't save it, using hub populations."""
    if "weekly_rate" in truth.columns:
        return truth
    population = DataLoader.load_locations().set_index("location")["population"]
    return truth.assign(weekly_rate=truth["value"] / truth["location"].map(population) * 100_000)


# ---------------------------------------------------------------- the selection

class Selection:
    """Forecasts, truth and scores for the current filters."""

    def __init__(self, filters: Filters, paths: Paths):
        self.paths = paths
        self.filters = filters
        self.primary = load_run(paths, filters.run)
        self.truth = with_weekly_rate(self.primary.truth)
        self.sources = self._sources(filters)
        self.outputs = {}
        for name, source in self.sources.items():
            output = in_season(_load_source(paths, *source), filters.season)
            if len(output):
                self.outputs[name] = output
        # selected models with no forecasts in this season: named on the page instead of vanishing
        self.no_data = [name for name in self.sources if name not in self.outputs]

    def _sources(self, filters: Filters) -> dict:
        """Model name -> ("run", backtest name) or ("hub", model id); the selected backtest first."""
        sources = {self.primary.name: ("run", self.primary.name)}
        for name in filters.compare_runs:
            sources.setdefault(name, ("run", name))
        for model_id in filters.hub_models:
            sources[model_id] = ("hub", model_id)
        # past MAX_MODELS the rest are left out, and named (render_tab shows them) rather than dropped silently
        self.dropped = list(sources)[MAX_MODELS:]
        return dict(list(sources.items())[:MAX_MODELS])

    def gaps(self) -> dict:
        """Model -> what it didn't forecast in this season (and location, if one is chosen), in plain words:
        the hub's rounds it has no forecast for, and the locations it never forecast. Only models with some
        forecasts this season; the rest are in self.no_data."""
        location = self.filters.chosen_location
        tables = {name: output if location is None else output[output["location"] == location]
                  for name, output in self.outputs.items()}
        rounds = {name: set(pd.to_datetime(table["reference_date"].unique())) for name, table in tables.items()}
        expected = expected_rounds(self.filters.season, set().union(*rounds.values()))
        places = {name: set(output["location"].astype(str)) for name, output in self.outputs.items()}
        every_place = set().union(*places.values())
        names = location_names(self.truth)
        gaps = {}
        for name in tables:
            notes = []
            missing = sorted(expected - rounds[name])
            if missing:
                where = f" for {names.get(location, location)}" if location else ""
                notes.append(f"no forecast{where} for {len(missing)} of {len(expected)} rounds: {_dates(missing)}")
            unforecast = sorted(names.get(code, code) for code in every_place - places[name])
            if location is None and unforecast:
                notes.append(f"never forecast {', '.join(unforecast)}")
            if notes:
                gaps[name] = notes
        return gaps

    @property
    def names(self) -> list[str]:
        return list(self.outputs)

    @property
    def has_reference(self) -> bool:
        return REFERENCE_MODEL in self.outputs

    def scores(self) -> dict:
        return {name: self._scored(name)[0] for name in self.outputs}

    def coverage(self) -> dict:
        return {name: self._scored(name)[1] for name in self.outputs}

    def _scored(self, name: str):
        return _score(self.paths, *self.sources[name], self.primary.name, self.filters.season)


def load_run(paths: Paths, name: str) -> runs.Run:
    return runs.load_run(name, paths.backtests, paths.backtest_data)


def list_runs(paths: Paths) -> pd.DataFrame:
    return runs.list_runs(paths.backtests)


@lru_cache(maxsize=32)   # read each model once per site session, not on every click
def _load_source(paths: Paths, kind: str, ident) -> pd.DataFrame:
    if kind == "run":
        return load_run(paths, ident).outputs
    return DataLoader.load_model_output(ident)


@lru_cache(maxsize=64)
def _score(paths: Paths, kind: str, ident, truth_run: str, season: str):
    """(WIS table, coverage table) for one model. Cached, so switching tabs or locations doesn't rescore."""
    truth = load_run(paths, truth_run).truth
    output = in_season(_load_source(paths, kind, ident), season)
    return wis(output, truth), coverage(output, truth)


@lru_cache(maxsize=1)
def vintages():
    """The data as published on each date, for the 'as reported then' line. Loaded on first use (~10 s)."""
    from flusight.backtest import BackTestEngine
    return BackTestEngine()


# ---------------------------------------------------------------- colors

def assign_colors(registry: dict | None, names: list[str], theme: str) -> dict:
    """Keep each model's color for the whole session.

    A model keeps its color slot while it is shown, a new model takes the lowest free slot, and
    FluSight-baseline is always the gray reference. Returns the updated registry:
    {"slots": {name: slot}, "colors": {name: color in the current theme}}.
    """
    series = palette(theme).series
    remembered = dict((registry or {}).get("slots", {}))
    current, taken = {}, set()
    for name in names:   # models already shown keep their slot
        slot = remembered.get(name)
        if name != REFERENCE_MODEL and slot is not None and slot not in taken:
            current[name] = slot
            taken.add(slot)
    for name in names:   # new models take the lowest free slot
        if name == REFERENCE_MODEL or name in current:
            continue
        free = next((slot for slot in range(len(series)) if slot not in taken), None)
        if free is not None:
            current[name] = free
            taken.add(free)
    remembered.update(current)
    colors = {name: series[current[name]] if name in current else palette(theme).reference for name in names}
    return {"slots": remembered, "colors": colors}


def chart_context(selection: Selection, filters: Filters, registry: dict | None) -> tuple[ChartContext, dict]:
    """The ChartContext for this selection, plus the updated color registry to store."""
    registry = assign_colors(registry, selection.names, filters.theme)
    names = location_names(selection.truth)
    return ChartContext(filters.theme, names, dict(registry["colors"])), registry


# ---------------------------------------------------------------- tables

def summary_table(scores: dict, coverage_tables: dict, location) -> pd.DataFrame:
    """One row per model on the shared forecasts: mean log-WIS overall and by horizon, the ratio to
    FluSight-baseline, and 50%/95% interval coverage."""
    scores = shared_forecasts(scores, location)
    coverage_tables = shared_forecasts(coverage_tables, location)
    reference = scores.get(REFERENCE_MODEL)
    rows = []
    for name, table in scores.items():
        row = {"model": name, "forecasts": len(table), "mean log-WIS": round(table["wis"].mean(), 4)}
        if reference is not None:
            row["vs FluSight-baseline"] = round(table["wis"].mean() / reference["wis"].mean(), 3)
        for h in SCORED_HORIZONS:
            row[f"h{h}"] = round(table.loc[table["horizon"] == h, "wis"].mean(), 4)
        for interval in (50, 95):
            column = f"cov_{interval}"
            if name in coverage_tables and column in coverage_tables[name]:
                row[f"inside {interval}%"] = f"{coverage_tables[name][column].astype(float).mean():.0%}"
        rows.append(row)
    return pd.DataFrame(rows).sort_values("mean log-WIS")


def state_table(selection: Selection, ctx: ChartContext, model: str, metric: str) -> pd.DataFrame:
    """Season-to-date value per location, best first (includes PR and the US total, which the map can't show).
    The hidden `code` column lets a clicked row select its location."""
    scores = selection.scores()
    if metric == "relative" and REFERENCE_MODEL not in scores:
        metric = "wis"
    data = cumulative_by_state(scores, model, metric, selection.coverage(), REFERENCE_MODEL)
    latest = data.sort_values("reference_date").groupby("location").tail(1)
    latest = latest.sort_values("value", ascending=metric != "coverage")
    formats = {"relative": "{:.2f}×", "wis": "{:.3f}", "coverage": "{:.0%}"}
    return pd.DataFrame({
        "code": latest["location"],
        "location": [ctx.location_name(code) for code in latest["location"]],
        METRICS[metric]: [formats[metric].format(value) for value in latest["value"]],
        "forecasts": latest["forecasts"].astype(int),
    })


def runs_table(paths: Paths) -> pd.DataFrame:
    """Every saved backtest, newest first, for the Runs tab."""
    table = list_runs(paths)
    if table.empty:
        return table
    coverage_95 = [c.get("95%") if isinstance(c, dict) else None for c in table["coverage"]]
    return pd.DataFrame({
        "backtest": table["label"],
        "vs FluSight-baseline": [("–" if pd.isna(v) else f"{v:.3f}") for v in
                                 table.get("relative_wis_vs_baseline", pd.Series([None] * len(table)))],
        "ran": table["created_at"].str.replace("T", " ").str[:16],
        "rounds": table["first_reference_date"] + " → " + table["last_reference_date"],
        "forecasts": table["tasks"],
        "mean log-WIS": table["mean_wis"],
        "inside 95%": ["–" if c is None else f"{c:.0%}" for c in coverage_95],
        "skipped rounds": [len(skipped) for skipped in table["skipped_reference_dates"]],
        "settings": [str(settings) for settings in table["hyperparameters"]],
    }).iloc[::-1]
