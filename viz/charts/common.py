"""Small helpers shared by the chart modules."""
from collections.abc import Mapping

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from flusight.constants import ScoringConstants


HORIZON_LABEL = {-1: "last week", 0: "this week", 1: "1 week ahead", 2: "2 weeks ahead", 3: "3 weeks ahead"}
SCORED_HORIZONS = [0, 1, 2, 3]  # CDC scores horizons 0-3; horizon -1 is a nowcast of last week


def as_dict(data, name: str = "model") -> dict:
    """Charts take {model name: table}. A single table is accepted too."""
    return dict(data) if isinstance(data, Mapping) else {name: data}


def date_label(date) -> str:
    date = pd.Timestamp(date)
    return f"{date:%b} {date.day}, {date.year}"


def count_label(value) -> str:
    return "–" if value is None or pd.isna(value) else f"{value:,.0f}"


def level_label(level: float) -> str:
    """0.025 -> '2.5%', 0.5 -> '50%'."""
    return f"{level * 100:g}%"


def observed_series(truth: pd.DataFrame, location: str, column: str = "value") -> pd.Series:
    """Final observed values for one location, indexed by week-ending date."""
    rows = truth[truth["location"] == location]
    return rows.set_index("date")[column].sort_index()


def is_all_locations(location) -> bool:
    return location in (None, "All")


def shared_forecasts(tables: dict, location=None, horizon=None) -> dict:
    """Keep only the forecasts (reference_date, location, horizon) that every model made, so models
    are compared on exactly the same tasks. Horizon -1 is dropped, as in CDC's scoring."""
    filtered = {}
    for name, table in tables.items():
        table = table[table["horizon"] >= 0]
        if not is_all_locations(location):
            table = table[table["location"] == location]
        if horizon is not None:
            table = table[table["horizon"] == horizon]
        filtered[name] = table

    shared = None
    for table in filtered.values():
        tasks = table[ScoringConstants.TASK].drop_duplicates()
        shared = tasks if shared is None else shared.merge(tasks, on=ScoringConstants.TASK)
    if shared is None:
        return filtered
    return {name: table.merge(shared, on=ScoringConstants.TASK) for name, table in filtered.items()}


def with_season_gaps(series: pd.Series) -> pd.Series:
    """Insert an empty point wherever rounds are more than a week apart, so a line chart doesn't
    draw a straight line across the off-season."""
    if len(series) < 2:
        return series
    dates = series.index
    gaps = [dates[i - 1] + pd.Timedelta(days=1) for i in range(1, len(dates)) if (dates[i] - dates[i - 1]).days > 7]
    return pd.concat([series, pd.Series(np.nan, index=gaps)]).sort_index()


def placeholder(**style) -> go.Scatter:
    """An invisible trace. Every replay frame must have the same number of traces in the same order,
    so a model with no forecast in some round is drawn as a placeholder there."""
    return go.Scatter(x=[None], y=[None], hoverinfo="skip", **style)
