"""Open the local benchmarking site for saved backtest runs. From the FluSight repo root:

    python download_data.py                         # first time: every team's forecasts in data/model-output
    python -m benchmark_site                        # http://127.0.0.1:8050
    python -m benchmark_site --port 8060 --no-browser

Reads backtest results from experiments/backtest/<YYYY-MM-DD-name>/, their model output and truth from
data/backtests/<YYYY-MM-DD-name>/, and other teams' forecasts from data/model-output.
"""
import argparse
import webbrowser
from pathlib import Path

from flusight.constants import BacktestsConstants
from benchmark_site.site.app import create_app

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--port", type=int, default=8050)
parser.add_argument("--backtests-dir", type=Path, default=BacktestsConstants.RESULTS_DIR)
parser.add_argument("--backtest-data-dir", type=Path, default=BacktestsConstants.DATA_DIR)
parser.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
args = parser.parse_args()

app = create_app(args.backtests_dir.expanduser(), args.backtest_data_dir.expanduser())
url = f"http://127.0.0.1:{args.port}"
print(f"FluSight benchmarks: {url}  (Ctrl+C to stop)")
if not args.no_browser:
    webbrowser.open(url)
app.run(host="127.0.0.1", port=args.port, debug=False)
