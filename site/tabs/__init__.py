"""One module per tab. Each has render(selection, filters, ctx) -> list of components, and
register(app, paths) for the callbacks of the tab's own controls."""
from benchmark_site.site.tabs import by_state, compare, forecasts, leaderboard, runs

TAB_MODULES = {"map": by_state, "leaderboard": leaderboard, "forecasts": forecasts, "compare": compare, "runs": runs}
