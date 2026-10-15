"""Reusable pieces of the page, built from Dash Mantine Components."""
import dash_mantine_components as dmc
import pandas as pd
from dash import dash_table, dcc

from benchmark_site.site.config import GRAPH_CONFIG
from benchmark_site.viz.notes import note
from benchmark_site.viz.theme import palette


def chart_card(chart_id: str, graph, controls=None, title: str | None = None):
    """A card with the chart's title, the research question it answers, optional controls, the chart,
    and a collapsible "How it's calculated" panel with its formulas (see benchmark_site/viz/notes.py)."""
    chart_note = note(chart_id)
    return dmc.Card([
        dmc.Title(title or chart_note.title, order=3),
        dmc.Text([dmc.Text("Research question: ", fw=600, span=True), chart_note.question],
                 c="dimmed", size="sm", mt=4, mb="sm"),
        controls if controls is not None else None,
        graph,
        dmc.Accordion(variant="contained", mt="sm", children=[dmc.AccordionItem(value="how", children=[
            dmc.AccordionControl("How it's calculated"),
            dmc.AccordionPanel([
                dmc.Text(chart_note.reading, size="sm", mb="xs"),
                dmc.ScrollArea(dcc.Markdown(chart_note.formulas, mathjax=True), type="auto"),
            ]),
        ])]),
    ])


def card(title: str, description: str, *children):
    """A plain card (for tables and messages that aren't charts)."""
    return dmc.Card([dmc.Title(title, order=3), dmc.Text(description, c="dimmed", size="sm", mt=4, mb="sm"),
                     *children])


def graph(figure, graph_id: str | None = None, height: int | None = None, config=GRAPH_CONFIG):
    extra = {"id": graph_id} if graph_id else {}
    style = {"height": f"{height}px"} if height else {}
    return dcc.Graph(figure=figure, config=config, style=style, **extra)


def controls(*items):
    """A row of labelled controls above a chart."""
    return dmc.Group(list(items), gap="lg", mb="sm", align="flex-end")


def labelled(label: str, control):
    return dmc.Stack([dmc.Text(label, size="xs", fw=600, c="dimmed"), control], gap=4)


def segmented(control_id: str, options: list[tuple[str, str]], value: str):
    """A SegmentedControl from (value, label) pairs."""
    return dmc.SegmentedControl(id=control_id, value=value, size="xs",
                                data=[{"value": v, "label": label} for v, label in options])


def message(title: str, hint: str | None = None):
    """Shown instead of a chart when there is nothing to draw."""
    return dmc.Alert(hint, title=title, color="gray", variant="light")


def simple_table(table: pd.DataFrame):
    """A read-only table."""
    if table.empty:
        return message("Nothing to show")
    body = [[_cell(value) for value in row] for row in table.itertuples(index=False)]
    return dmc.ScrollArea(dmc.Table(data={"head": list(table.columns), "body": body}, striped=True,
                                    highlightOnHover=True, tabularNums=True, verticalSpacing="xs"))


def clickable_table(table_id: str, table: pd.DataFrame, theme: str, hidden=("code",), page_size: int = 14):
    """A sortable table whose clicked cell is available as `active_cell` (used to pick a state).
    DataTable takes its styling as Python dicts, colored from the chart palette."""
    p = palette(theme)
    font = {"fontFamily": 'system-ui, -apple-system, "Segoe UI", sans-serif', "fontSize": 13}
    return dash_table.DataTable(
        id=table_id, data=table.to_dict("records"),
        columns=[{"name": column, "id": column} for column in table.columns if column not in hidden],
        page_size=page_size, sort_action="native", style_as_list_view=True,
        style_table={"overflowX": "auto"},
        style_header={**font, "backgroundColor": "transparent", "color": p.muted, "fontWeight": 600,
                      "borderBottom": f"1px solid {p.axis}"},
        style_cell={**font, "backgroundColor": "transparent", "color": p.ink, "border": "none",
                    "borderBottom": f"1px solid {p.grid}", "padding": "8px 10px", "textAlign": "left",
                    "cursor": "pointer"},
        style_data_conditional=[{"if": {"state": "active"}, "backgroundColor": p.grid, "border": "none"}],
    )


def _cell(value):
    if isinstance(value, float):
        return "–" if pd.isna(value) else f"{value:g}"
    return str(value)


def gaps_alert(gaps: dict, season: str):
    """Which selected models are missing which rounds or places. Their charts show nothing there, and scores
    compared across models use only the forecasts every model made."""
    lines = [dmc.Text([dmc.Text(name, span=True, fw=600), f": {'; '.join(notes)}"], size="xs") for name, notes in gaps.items()]
    return dmc.Alert(lines + [dmc.Text("Nothing is drawn where a model has no forecast; comparisons use only the "
                                       "forecasts every selected model made.", size="xs", c="dimmed", mt=4)],
                     title=f"Missing forecasts in {season}", color="yellow", variant="light", mb="sm")
