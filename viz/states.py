"""State-level benchmark numbers for the map, cumulative by forecast round."""
import numpy as np
import pandas as pd

# FIPS code -> USPS abbreviation (what Plotly's USA map uses). PR and the US total have no shape
# on the map; they stay selectable from the state table and the Location filter.
STATE_ABBR = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC",
    "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT",
    "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY", "72": "PR", "US": "US",
}
FIPS = {abbr: fips for fips, abbr in STATE_ABBR.items()}

METRICS = {
    "relative": "log-WIS vs FluSight-baseline",
    "wis": "mean log-WIS",
    "coverage": "inside the 95% range",
}


def cumulative_by_state(scores: dict, model: str, metric: str = "relative", coverage: dict | None = None,
                        relative_to: str = "FluSight-baseline") -> pd.DataFrame:
    """One row per (reference_date, location): the metric over every forecast up to that round.

    relative: mean log-WIS of `model` / mean log-WIS of `relative_to`, on forecasts both made
    wis:      mean log-WIS of `model`
    coverage: share of `model`'s 95% ranges that contained the observed value
    Columns: reference_date, location, value, forecasts (+ model_wis, reference_wis for relative).
    """
    if metric == "coverage":
        table = coverage[model][coverage[model]["horizon"] >= 0][["reference_date", "location", "cov_95"]]
        return _cumulate(table.rename(columns={"cov_95": "x"}).assign(x=lambda d: d["x"].astype(float)), "x")
    s = scores[model][scores[model]["horizon"] >= 0]
    if metric == "relative":
        base = scores[relative_to][scores[relative_to]["horizon"] >= 0]
        both = s.merge(base, on=["reference_date", "location", "horizon"], suffixes=("_m", "_b"))
        a = _cumulate(both.rename(columns={"wis_m": "x"}), "x").rename(columns={"value": "model_wis"})
        b = _cumulate(both.rename(columns={"wis_b": "x"}), "x").rename(columns={"value": "reference_wis"})
        out = a.merge(b[["reference_date", "location", "reference_wis"]], on=["reference_date", "location"])
        return out.assign(value=out["model_wis"] / out["reference_wis"])
    return _cumulate(s.rename(columns={"wis": "x"}), "x")


def _cumulate(table: pd.DataFrame, column: str) -> pd.DataFrame:
    weekly = table.groupby(["location", "reference_date"])[column].agg(["sum", "count"]).reset_index()
    weekly = weekly.sort_values(["location", "reference_date"])
    grouped = weekly.groupby("location")
    weekly["cum_sum"], weekly["forecasts"] = grouped["sum"].cumsum(), grouped["count"].cumsum()
    # carry each state's latest value forward to every round, so every frame has every state
    dates = sorted(weekly["reference_date"].unique())
    full = pd.MultiIndex.from_product([weekly["location"].unique(), dates], names=["location", "reference_date"])
    weekly = weekly.set_index(["location", "reference_date"])[["cum_sum", "forecasts"]].reindex(full)
    weekly = weekly.groupby(level="location").ffill().reset_index()
    weekly["value"] = weekly["cum_sum"] / weekly["forecasts"]
    return weekly[["reference_date", "location", "value", "forecasts"]].dropna(subset=["value"])


def log_ratio_ticks():
    ratios = [0.5, 0.67, 0.8, 1, 1.25, 1.5, 2]
    return [float(np.log2(r)) for r in ratios], [f"{r:g}×" for r in ratios]
