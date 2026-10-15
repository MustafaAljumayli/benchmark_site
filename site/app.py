"""Local benchmarking site: every saved backtest run next to other teams' hub forecasts.

    python download_data.py      # once, and again to pick up new hub forecasts
    python -m benchmark_site     # then open http://127.0.0.1:8050

Reads backtests from experiments/backtest and data/backtests, and other teams' forecasts from data/model-output.
Nothing is hosted; the site runs on your machine.

Code layout:
  config.py      settings (models shown, graph options, the Mantine theme)
  data.py        loading runs and hub models, scoring, tables (no Dash code)
  inputs.py      the filter controls and turning their values into chart-ready data
  layout.py      the page: header, filter panel, tabs
  components.py  chart cards, tables, messages
  callbacks.py   header, filters, and rendering the selected tab
  tabs/          one module per tab, with that tab's own controls
"""
from pathlib import Path

from dash import Dash

from flusight.constants import BacktestsConstants
from flusight.data import DataLoader
from benchmark_site.site import callbacks
from benchmark_site.site.config import Paths
from benchmark_site.site.layout import page
from benchmark_site.viz.replay import REPLAY_SCRIPT


def create_app(backtests_dir=BacktestsConstants.RESULTS_DIR, backtest_data_dir=BacktestsConstants.DATA_DIR) -> Dash:
    if not DataLoader.list_model_output():
        raise SystemExit(f"No hub forecasts in {DataLoader.data_dir / 'model-output'}.\n"
                         "Download them first:  python download_data.py")
    paths = Paths(Path(backtests_dir), Path(backtest_data_dir))
    app = Dash(__name__, title="FluSight Benchmarks", assets_folder=str(Path(__file__).parent / "assets"),
               suppress_callback_exceptions=True)   # tab controls only exist while their tab is shown
    app.layout = page()
    app.index_string = app.index_string.replace("</body>", f"<script>{REPLAY_SCRIPT}</script>\n</body>")
    callbacks.register(app, paths)
    return app
