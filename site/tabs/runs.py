"""Runs tab: every saved backtest."""
from benchmark_site.site import components as ui
from benchmark_site.site.data import list_runs, runs_table
from benchmark_site.viz import charts


def render(selection, filters, ctx) -> list:
    table = list_runs(selection.paths)
    if table.empty:
        return [ui.message("No backtests yet.", "Run one with:  python run_backtest.py --model RegEns")]
    return [
        ui.chart_card("run_history", ui.graph(charts.run_history(ctx, table, highlight=[selection.primary.name]))),
        ui.card("Backtest details", "Newest first. Each backtest's results are in experiments/backtest/<name>/ (with its "
                                    "notes.md); its model output and truth are in data/backtests/<name>/.",
                ui.simple_table(runs_table(selection.paths))),
    ]


def register(app, paths) -> None:
    """The Runs tab has no controls of its own."""
