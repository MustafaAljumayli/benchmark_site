"""The page: a header, a side panel of filters, the tabs, and the area each tab renders into."""
import dash_mantine_components as dmc
from dash import dcc

from benchmark_site.site.components import labelled
from benchmark_site.site.config import MANTINE_THEME, MAX_MODELS
from benchmark_site.viz.theme import LIGHT

TABS = [
    ("map", "Map"),
    ("leaderboard", "Model leaderboard"),
    ("forecasts", "Forecasts"),
    ("compare", "Compare models"),
    ("runs", "Runs"),
]
HORIZONS = [("-1", "h-1"), ("0", "h0"), ("1", "h1"), ("2", "h2"), ("3", "h3")]


def page():
    return dmc.MantineProvider(id="provider", theme=MANTINE_THEME, forceColorScheme="light", children=[
        dcc.Store(id="colors", data={}),   # each model's color slot, kept for the session
        dmc.AppShell(
            header={"height": 68}, navbar={"width": 300, "breakpoint": "sm"}, padding="lg",
            children=[
                dmc.AppShellHeader(header(), px="lg"),
                dmc.AppShellNavbar(filters(), p="md"),
                dmc.AppShellMain([
                    dmc.Tabs(id="tab", value="map", mb="lg", children=dmc.TabsList(
                        [dmc.TabsTab(label, value=value) for value, label in TABS])),
                    dcc.Loading(dmc.Stack(id="content", gap="lg"), type="dot", color=LIGHT.series[0],
                                delay_show=250),
                ]),
            ],
        ),
    ])


def header():
    return dmc.Group(justify="space-between", h="100%", children=[
        dmc.Stack(gap=0, children=[
            dmc.Title("FluSight Benchmarks", order=3),
            dmc.Text(id="subtitle", size="xs", c="dimmed"),
        ]),
        dmc.Group(gap="lg", children=[
            dmc.Button("Reload runs", id="reload", variant="default", size="xs"),
            dmc.Switch(id="dark-mode", label="Dark mode", checked=False, persistence=True,
                       persisted_props=["checked"], persistence_type="local"),
        ]),
    ])


def filters():
    return dmc.Stack(gap="md", children=[
        dmc.Select(id="run", label="Run", allowDeselect=False),
        dmc.MultiSelect(id="compare-runs", label="Compare with runs", placeholder="Earlier runs", clearable=True),
        dmc.MultiSelect(id="hub-models", label="Compare with hub models", placeholder="Other teams' models",
                        searchable=True, clearable=True, maxValues=MAX_MODELS - 1),
        dmc.Select(id="season", label="Season", allowDeselect=False),
        dmc.Select(id="location", label="Location", searchable=True, allowDeselect=False),
        labelled("Horizon", dmc.SegmentedControl(id="horizon", value="1", fullWidth=True, size="xs",
                                                 data=[{"value": v, "label": label} for v, label in HORIZONS])),
        dmc.Text(f"Up to {MAX_MODELS} models are shown at once; the selected run always comes first.",
                 size="xs", c="dimmed"),
    ])
