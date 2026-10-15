"""The site's charts, model colors and leaderboard."""
import tempfile
import unittest
from pathlib import Path
from statistics import NormalDist
from unittest.mock import patch

import numpy as np
import pandas as pd

from benchmark_site.site import leaderboard as board
from benchmark_site.site.config import Paths
from benchmark_site.site.data import assign_colors, season_of
from benchmark_site.viz import Plotter2D, Plotter3D
from benchmark_site.viz.notes import NOTES
from flusight.constants import ModelOutputConstants
from flusight.data import DataLoader
from flusight.model_output_validator import ModelOutputValidator
from flusight.scoring_m import coverage, wis

DATES = pd.to_datetime(["2025-01-04", "2025-01-11", "2025-01-18", "2025-01-25"])
LOCATIONS = ["13", "48", "US"]


def fake_output(median=100.0, sd=0.3):
    """Log-normal forecasts for every date, location and horizon."""
    return pd.concat([ModelOutputValidator.build_output(ref, [
        (loc, h, q, np.expm1(np.log1p(median) + sd * NormalDist().inv_cdf(q)))
        for loc in LOCATIONS for h in [-1, 0, 1, 2, 3] for q in ModelOutputConstants.QUANTILE_LEVELS]) for ref in DATES], ignore_index=True)


def fake_truth():
    weeks = pd.date_range("2024-12-21", "2025-02-22", freq="W-SAT")
    return pd.DataFrame([(d, loc, 100.0, 10.0) for d in weeks for loc in LOCATIONS],
                        columns=["date", "location", "value", "weekly_rate"])


class ChartTests(unittest.TestCase):
    def setUp(self):
        self.truth = fake_truth()
        self.outputs = {"ours": fake_output(), "FluSight-baseline": fake_output(sd=0.6)}
        self.scores = {k: wis(v, self.truth) for k, v in self.outputs.items()}
        self.cov = {k: coverage(v, self.truth) for k, v in self.outputs.items()}

    def test_every_time_chart_replays_one_frame_per_date(self):
        p2, p3 = Plotter2D("dark"), Plotter3D("light")
        for fig in [p2.forecast_replay(self.outputs, self.truth, "13"),
                    p2.score_timeline(self.scores, relative_to="FluSight-baseline"),
                    p2.coverage_replay(self.cov),
                    p2.state_map(self.scores, "ours", "relative", coverage=self.cov),
                    p3.rate_surface(self.truth, self.outputs["ours"], "ours")]:
            self.assertEqual(len(fig.frames), len(DATES))
            self.assertTrue(all(not f.layout or not f.layout.to_plotly_json() for f in fig.frames))   # slider stays put

    def test_forecast_chart_draws_all_11_intervals(self):
        figure = Plotter2D().forecast_replay({"ours": self.outputs["ours"]}, self.truth, "13")
        self.assertEqual(sum(getattr(t, "fill", None) == "tonexty" for t in figure.frames[0].data), 11)

    def test_forecast_chart_names_models_missing_a_round(self):
        skipped = self.outputs["FluSight-baseline"]
        skipped = skipped[skipped["reference_date"] != DATES[1]]   # the baseline skips the second round
        figure = Plotter2D().forecast_replay({"ours": self.outputs["ours"], "FluSight-baseline": skipped}, self.truth, "13")
        notes = [next(t.text[0] for t in frame.data if t.mode == "text" and t.text and t.text[0] is not None)
                 for frame in figure.frames]
        self.assertEqual(notes[0], "")
        self.assertEqual(notes[1], "No forecast this round for 13 from: FluSight-baseline")
        self.assertEqual(len({len(frame.data) for frame in figure.frames}), 1)   # same traces in every frame

    def test_every_chart_has_a_question_and_formulas(self):
        self.assertTrue(all(n.question.endswith("?") and n.formulas.strip() for n in NOTES.values()))

    def test_seasons_run_june_to_may(self):
        # the 2025/26 FluSight season ends in May 2026; every later round belongs to 2026/27
        self.assertEqual([season_of(d) for d in ["2025-06-07", "2026-05-30", "2026-06-06", "2026-10-03"]],
                         [2025, 2025, 2026, 2026])

    def test_models_keep_their_color(self):
        first = assign_colors({}, ["run-2", "run-1", "FluSight-baseline", "hub-a"], "light")
        later = assign_colors(first, ["run-2", "hub-a"], "light")   # run-1 deselected
        self.assertEqual(later["colors"]["hub-a"], first["colors"]["hub-a"])
        self.assertEqual(first["colors"]["FluSight-baseline"], "#898781")   # the gray reference


def ranked_models(models, imported=()):
    """The 2024 leaderboard of hub models [(name, output, "parquet" or "csv")] and models copied in without the
    hub's file names [(name, output)], in a temporary data folder."""
    with tempfile.TemporaryDirectory() as root, patch.object(DataLoader, "data_dir", Path(root)):
        for name, output, suffix in models:
            folder = Path(root) / "model-output" / name
            folder.mkdir(parents=True)
            for date, rows in output.groupby("reference_date"):
                path = folder / f"{pd.Timestamp(date):%Y-%m-%d}-{name}.{suffix}"
                rows.to_parquet(path) if suffix == "parquet" else rows.to_csv(path, index=False)
        for name, output in imported:
            folder = Path(root) / "model-output" / name
            folder.mkdir(parents=True)
            for date, rows in output.groupby("reference_date"):
                rows.to_csv(folder / f"{pd.Timestamp(date):%Y-%m-%d}.csv", index=False)   # not YYYY-MM-DD-<model>
        (Path(root) / "target-data").mkdir()
        fake_truth().to_csv(Path(root) / "target-data" / "target-hospital-admissions.csv", index=False)
        for cached in (board.truth, board.season_rounds, board.task_scores):
            cached.cache_clear()
        return board.leaderboard(Paths(Path(root), Path(root)), "2024", None, None, ())


class LeaderboardTests(unittest.TestCase):
    HUB = [("FluSight-baseline", fake_output(sd=0.6), "parquet"), ("Sharp", fake_output(sd=0.2), "parquet")]

    def test_ranks_hub_models_like_cdc(self):
        """Models from parquet or CSV, ranked by pairwise relative WIS over the states (the US is left out)."""
        ranked = ranked_models(self.HUB + [("Georgia-only", fake_output(sd=0.2).query("location == '13'"), "csv")])
        # Georgia-only made 50% of the baseline's forecasts: under CDC's 75% rule it is listed after the eligible models
        self.assertEqual(list(ranked["Model"]), ["Sharp", "FluSight-baseline", "Georgia-only"])
        self.assertEqual(list(ranked["Eligible"]), [True, True, False])
        self.assertAlmostEqual(ranked["Log relative WIS"].iloc[0], ranked["Log relative WIS"].iloc[2])   # same skill
        self.assertEqual(ranked.set_index("Model")["Forecasts scored"].to_dict(),
                         {"Georgia-only": 16, "Sharp": 32, "FluSight-baseline": 32})   # 4 rounds x horizons 0-3

    def test_imported_folder_is_ranked_without_joining_the_pool(self):
        """A model copied in without the hub's file names loads, and leaves the hub models' scores alone."""
        alone = ranked_models(self.HUB).set_index("Model")
        ranked = ranked_models(self.HUB, [("other", fake_output(sd=0.4))]).set_index("Model")
        self.assertEqual(ranked.loc["other", "Source"], "imported")
        self.assertEqual(ranked.loc["other", "Forecasts scored"], 32)
        pd.testing.assert_series_equal(ranked.loc[alone.index, "Log relative WIS"], alone["Log relative WIS"])


if __name__ == "__main__":
    unittest.main()
