"""Settings for the benchmarking site."""
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HUB_MODELS = ["FluSight-baseline", "FluSight-ensemble"]
REFERENCE_MODEL = "FluSight-baseline"
MAX_MODELS = 6              # beyond this, lines and curves become unreadable
MAX_FORECAST_MODELS = 4     # each model's 11 interval bands overlap; more than 4 turns to mud
SURFACE_HEIGHT = 660        # pixels, for the 3D charts

GRAPH_CONFIG = {"displaylogo": False, "toImageButtonOptions": {"format": "png", "scale": 2}}
# The US state outlines ship with the site (assets/topojson), so the map works offline.
MAP_CONFIG = {**GRAPH_CONFIG, "topojsonURL": "/assets/topojson/"}

# Mantine theme. The dark shades are the chart palette's grays (benchmark_site/viz/theme.py), so cards and
# charts share one background in dark mode.
MANTINE_THEME = {
    "primaryColor": "blue",
    "defaultRadius": "md",
    "fontFamily": 'system-ui, -apple-system, "Segoe UI", sans-serif',
    "colors": {
        "dark": ["#e1e0d9", "#c3c2b7", "#a9a89f", "#898781", "#5d5c58", "#383835",
                 "#1a1a19", "#141413", "#0f0f0e", "#0a0a0a"],
    },
    "components": {"Card": {"defaultProps": {"withBorder": True, "padding": "lg"}}},
}


@dataclass(frozen=True)
class Paths:
    """Where the site reads saved backtests from. Frozen so it can be part of a cache key.
    Other teams' forecasts come from DataLoader (data/model-output, see download_data.py)."""
    backtests: Path        # experiments/backtest/<YYYY-MM-DD-name>: results (run.json, scores, coverage)
    backtest_data: Path    # data/backtests/<YYYY-MM-DD-name>: model output and truth
