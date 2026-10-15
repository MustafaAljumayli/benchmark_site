# FluSight benchmarking site

A local Dash site that compares our saved backtests with other teams' FluSight hub forecasts:
a map by state, forecast distributions, forecasts against what happened, model comparisons and
the history of runs. Every chart replays round by round.

This folder is its own repository. It is kept out of the public FluSight repo (that repo's
`.gitignore` lists `benchmark_site/`), and nothing in `flusight/` imports it.

## Setup

The site reads everything through the `flusight` package, the same way the rest of the project
does (`DataLoader`, `flusight.runs`, `flusight.scoring_m`), so it lives in the root of the FluSight repo:

```
flusight/              the FluSight repo (public)
  flusight/            forecasting code
  data/                downloaded data
  experiments/backtest/
  benchmark_site/      this repo
```

```sh
cd flusight                                    # the FluSight repo root, with its .venv active
git clone https://github.com/MustafaAljumayli/benchmark_site.git benchmark_site
pip install -e .                               # the flusight package, if not installed yet
pip install -r benchmark_site/requirements.txt
```

## Run

From the FluSight repo root:

```sh
python download_data.py                  # hub forecasts and target data -> data/ (re-run weekly)
python run_backtest.py --model RegEns    # a backtest -> experiments/backtest/ and data/backtests/
python -m benchmark_site                 # opens http://127.0.0.1:8050
python -m benchmark_site --port 8060 --no-browser
```

The site won't start until `download_data.py` has run. Seasons run June through May: the 2025/26
FluSight season ends in May 2026, and every round after it is in 2026/27. Backtests forecast every
week up to the latest data release, and the site scores every round whose weeks have been reported,
so a season still being reported is marked "in progress" ("forecasts only" if nothing is reported yet).

## Model leaderboard

The Model leaderboard tab ranks every downloaded hub model, plus the selected backtests, by relative WIS.
"Scored against" picks the rules:

- **CDC end-of-season evaluation** (default for 2023/24, 2024/25, 2025/26): CDC's official ranking
  (cdc.gov/flu-forecasting/evaluation). Rules, truth release and model pool come from
  `flusight/cdc_evaluation.py`, which reproduces CDC's published Table 1 for all three seasons (relative WIS of
  every model to CDC's 2 decimals; see `experiments/2026-10-06-cdc-reproduction/notes.md`). National and, from
  2024/25, Puerto Rico forecasts are left out, models below 75% of forecasts are not in the pool, and each
  season's exclusions apply. Backtests are ranked as if they had been submitted ("Rank if submitted"), with the
  75% rule checked ("Eligible"). They are retrospective: not made in real time, and their settings were tuned on
  these seasons, so their rank is optimistic.
- **Hub weekly report (May 27, 2026)**: the hub's in-season weekly report, `reports/Flu_Hospitalizations_
  Forecasts_WIS_27 May 2026.html` (saved in `site/cdc_reports/2025-26.csv`). This is *not* CDC's official
  evaluation: it keeps Puerto Rico, has no 75% rule, and ranks every hub model including CDC's experimental
  ensembles (58 models). With the May 27, 2026 release we reproduce its numbers for all 58 models.
- **Latest data**: the same in-season rules, scored against the newest data.

To compare a hub team whose forecasts you have as files, copy them into `data/model-output/<model>/`
(named `YYYY-MM-DD-<model>.csv` or `.parquet`); the site reads both. Those models join the pool every model is
ranked against, so do this only for real hub models.

## Tests

```sh
python -m unittest discover -s benchmark_site/tests
```

## Layout

```
__main__.py   starts the site (python -m benchmark_site)
site/         the Dash app: layout, filters, callbacks, one module per tab
  leaderboard.py  CDC-style ranking of every model (no Dash code)
  cdc_reports/    CDC's published season results, to check the leaderboard against
viz/          the Plotly charts, also usable on their own (Plotter2D, Plotter3D, save_html)
  replay.js   glides charts between rounds and runs Play/Pause
tests/        chart tests
```
