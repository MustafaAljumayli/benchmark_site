"""The model leaderboard: every hub model we have downloaded, and our backtests, ranked by relative WIS
the way CDC's FluSight season reports rank them. No Dash code.

Two sets of rules:
  - cdc_leaderboard(): CDC's end-of-season evaluation (cdc.gov/flu-forecasting/evaluation), the official
    ranking. Rules, truth and model pool come from flusight/cdc_evaluation.py, which reproduces CDC's published
    Table 1 for 2023/24, 2024/25 and 2025/26. Our backtests are ranked as if they had been submitted, with
    CDC's 75% rule checked. They are retrospective: they were not submitted in real time.
  - leaderboard(): the hub's in-season weekly report (reports/ in the hub; it keeps Puerto Rico, has no 75%
    rule and ranks every hub model, CDC's experimental ensembles included). It is NOT CDC's official
    evaluation; with the May 27, 2026 data it reproduces that weekly report's 2025/26 table.

The in-season report's rules:
  - forecasts of weekly flu admissions, horizons 0-3
  - the 50 states, DC and Puerto Rico; the US total is left out (or one location, if one is chosen)
  - the season's rounds: every reference date FluSight-baseline forecast that season
  - relative WIS from pairwise comparisons (flusight.scoring_m.pairwise_relative_wis), with the hub models
    as the pool; our backtests and imported models (hub-format files in data/model-output not named like the hub's) are
    ranked against them without changing the hub models' scores
"""
from functools import lru_cache
from pathlib import Path

import pandas as pd

from flusight import cdc_evaluation
from flusight.constants import CDCEvaluationConstants, ModelOutputConstants, ScoringConstants
from flusight.data import DataLoader
from flusight.scoring_m import pairwise_relative_wis, quantile_forecasts, wis_values
from benchmark_site.site.config import REFERENCE_MODEL, Paths
from benchmark_site.site.data import in_season, load_run, vintages

# The hub's in-season weekly report, from FluSight-forecast-hub/reports/, for checking our numbers against.
# (Not CDC's end-of-season evaluation: that one is cdc_leaderboard() below.)
CDC_REPORTS = {
    "2025": {"as_of": "2026-05-27", "file": "2025-26.csv",
             "label": "Hub weekly report (May 27, 2026 data; with Puerto Rico, no 75% rule)",
             "source": "FluSight-forecast-hub/reports/Flu_Hospitalizations_Forecasts_WIS_27 May 2026.html"},
}
REPORTS_DIR = Path(__file__).with_name("cdc_reports")


@lru_cache(maxsize=4)
def truth(as_of: str | None) -> pd.DataFrame:
    """Weekly admissions to score against: the latest data, or the release published on as_of."""
    if as_of is None:
        return DataLoader.load_target()[["date", "location", "value"]]
    releases = vintages().vintages
    release = releases[(releases["as_of"] == pd.Timestamp(as_of)) & (releases["target"] == ScoringConstants.TARGET)]
    return release.drop_duplicates(["date", "location"], keep="last")[["date", "location", "value"]]


def is_hub_model(model: str) -> bool:
    """Whether a model in data/model-output came from the FluSight hub: its files are named YYYY-MM-DD-<model>,
    as the hub names them. Files copied in under other names (YYYY-MM-DD.csv) don't join the pool."""
    return all(path.stem.endswith(f"-{model}") for path in DataLoader.forecast_files(model))


@lru_cache(maxsize=16)
def season_rounds(season: str) -> tuple | None:
    """(first, last) reference date FluSight-baseline forecast in the season, or None."""
    rounds = in_season(DataLoader.load_model_output(REFERENCE_MODEL), season)["reference_date"]
    return (rounds.min(), rounds.max()) if len(rounds) else None


@lru_cache(maxsize=512)
def task_scores(paths: Paths, kind: str, name: str, first, last, as_of: str | None) -> pd.DataFrame:
    """One row per scored forecast (TASK, location) of a hub model or a backtest, rounds first..last:
    log_wis, wis, abs_error (of the median), in_50, in_95."""
    if kind == "hub":
        output = DataLoader.load_model_output(name, first, last)
    else:
        output = load_run(paths, name).outputs
        output = output[output["reference_date"].between(first, last)]
    output = output[output["horizon"].between(*CDCEvaluationConstants.SCORED_HORIZONS)]
    forecasts = quantile_forecasts(output, truth(as_of)) if len(output) else pd.DataFrame()
    if forecasts.empty or not set(ModelOutputConstants.QUANTILE_LEVELS) <= set(forecasts.columns):
        return pd.DataFrame(columns=ScoringConstants.TASK + ["log_wis", "wis", "abs_error", "in_50", "in_95"])
    observed = forecasts["observed"]
    return forecasts[ScoringConstants.TASK].assign(
        log_wis=wis_values(forecasts), wis=wis_values(forecasts, log=False), abs_error=(observed - forecasts[0.5]).abs(),
        in_50=observed.between(forecasts[0.25], forecasts[0.75]), in_95=observed.between(forecasts[0.025], forecasts[0.975]))


def leaderboard(paths: Paths, season: str, location: str | None, as_of: str | None, backtests: tuple) -> pd.DataFrame:
    """Every model with scored forecasts in the season, best first. Empty if FluSight-baseline has none."""
    rounds = season_rounds(season)
    if rounds is None:
        return pd.DataFrame()
    sources = [("hub" if is_hub_model(name) else "imported", name) for name in DataLoader.list_model_output()]
    sources += [("backtest", name) for name in backtests]
    tables, kinds = {}, {}
    for kind, name in sources:
        table = task_scores(paths, "run" if kind == "backtest" else "hub", name, *rounds, as_of)
        table = table[table["location"] != "US"] if location is None else table[table["location"] == location]
        if len(table):
            tables[name], kinds[name] = table, kind
    pool = [name for name in tables if kinds[name] == "hub"]
    if REFERENCE_MODEL not in pool:
        return pd.DataFrame()

    def relative(column):
        return pairwise_relative_wis({name: t[ScoringConstants.TASK].assign(wis=t[column]) for name, t in tables.items()}, pool=pool)

    log_relative, count_relative = relative("log_wis"), relative("wis")
    board = pd.DataFrame([{
        "Model": name, "Source": {"backtest": "our backtest", "imported": "imported"}.get(kinds[name], "hub"),
        "Log relative WIS": log_relative[name], "Relative WIS": count_relative[name], "WIS": t["wis"].mean(),
        "MAE": t["abs_error"].mean(), "50% coverage": 100 * t["in_50"].mean(), "95% coverage": 100 * t["in_95"].mean(),
        "Forecasts scored": len(t), "Locations": t["location"].nunique(),
    } for name, t in tables.items()])
    report = CDC_REPORTS.get(season)
    if report and as_of == report["as_of"] and location is None:
        cdc = pd.read_csv(REPORTS_DIR / report["file"])[["Model", "Log Relative WIS", "Relative WIS"]]
        board = board.merge(cdc.rename(columns={"Log Relative WIS": "CDC log relative WIS",
                                                "Relative WIS": "CDC relative WIS"}), on="Model", how="left")
    # CDC's 75% rule: a model that made under 75% of the forecasts FluSight-baseline made isn't ranked by CDC
    # (a handful of easy rounds, or one state, can put it on top). Those are listed after every eligible model.
    baseline_count = board.loc[board["Model"] == REFERENCE_MODEL, "Forecasts scored"].iloc[0]
    board["% of forecasts"] = 100 * board["Forecasts scored"] / baseline_count
    board["Eligible"] = board["% of forecasts"] >= 75
    board = board.sort_values(["Eligible", "Log relative WIS", "Model"], ascending=[False, True, True]).reset_index(drop=True)
    return board.assign(Rank=range(1, len(board) + 1))[["Rank", *board.columns]]


def matches_cdc(board: pd.DataFrame) -> tuple[int, int]:
    """(models whose log relative WIS and relative WIS both round to CDC's, models in CDC's table)."""
    if "CDC log relative WIS" not in board:
        return 0, 0
    published = board.dropna(subset=["CDC log relative WIS"])
    same = ((published["Log relative WIS"] - published["CDC log relative WIS"]).abs() <= 0.005) & \
           ((published["Relative WIS"] - published["CDC relative WIS"]).abs() <= 0.005)   # CDC rounds to 2 decimals
    return int(same.sum()), len(published)


def evaluation_season(season: str) -> str | None:
    """The CDC end-of-season evaluation for a site season ("2025" -> "2025-26"), if CDC published one."""
    try:
        label = f"{int(season)}-{(int(season) + 1) % 100:02d}"
    except (TypeError, ValueError):
        return None
    return label if label in CDCEvaluationConstants.SEASONS else None


def cdc_leaderboard(paths: Paths, season: str, backtests: tuple) -> pd.DataFrame:
    """CDC's end-of-season Table 1 for the season, recomputed (flusight.cdc_evaluation), with our backtests
    ranked as if submitted. Columns as leaderboard(), plus CDC's published value, "Eligible" (CDC's 75% rule)
    and "Rank if submitted". Empty if CDC has no evaluation for the season."""
    label = evaluation_season(season)
    if label is None:
        return pd.DataFrame()
    extra = {name: load_run(paths, name).outputs for name in backtests}
    table = cdc_evaluation.evaluate(label, extra=extra)
    published = cdc_evaluation.cdc_table(label)[["Model", "Relative WIS"]].rename(columns={"Relative WIS": "CDC log relative WIS"})
    board = table.rename(columns={"Relative WIS": "Log relative WIS", "50% Coverage (%)": "50% coverage",
                                  "95% Coverage (%)": "95% coverage", "Mean log WIS": "Log WIS"})
    board["Source"] = board["Source"].map({"CDC": "hub", "ours": "our backtest"})
    return board.merge(published, on="Model", how="left")


def matches_cdc_evaluation(board: pd.DataFrame) -> tuple[int, int]:
    """(models whose log relative WIS rounds to CDC's end-of-season value, models in CDC's table)."""
    published = board.dropna(subset=["CDC log relative WIS"])
    same = (published["Log relative WIS"] - published["CDC log relative WIS"]).abs() < 0.005 + 1e-9
    return int(same.sum()), len(published)
