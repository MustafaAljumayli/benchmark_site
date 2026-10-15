"""A forecast's 23 quantiles as one row per forecast, one column per quantile level."""
import pandas as pd

from flusight.constants import ModelOutputConstants, ScoringConstants


KEYS = ["reference_date", "location", "horizon", "target_end_date"]
LEVELS = [float(level) for level in ModelOutputConstants.QUANTILE_LEVELS]


def quantile_table(output: pd.DataFrame) -> pd.DataFrame:
    """One row per forecast (KEYS) with one column per quantile level (as a float), in order."""
    rows = output[(output["target"] == ScoringConstants.TARGET) & (output["output_type"] == "quantile")]
    wide = (
        rows.assign(level=rows["output_type_id"].astype(float))
        .pivot_table(index=KEYS, columns="level", values="value", aggfunc="first")
    )
    wide = wide.reindex(columns=[level for level in LEVELS if level in wide.columns])
    return wide.reset_index()
