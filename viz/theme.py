"""Colors, the Plotly template, and the ChartContext every chart function receives.

Color rules (palette validated for colorblind safety in light and dark mode):
  - Models get one of 8 categorical hues, assigned in a fixed order. A model keeps its color when
    others are toggled on or off.
  - FluSight-baseline is always neutral gray: it is the reference everything is compared against.
  - Horizons (-1..3) are one blue hue stepped light to dark, because horizons are ordered.
  - What actually happened is drawn in the primary text color, never in a model color.
"""
from dataclasses import dataclass, field

import plotly.graph_objects as go

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
REFERENCE_MODEL = "FluSight-baseline"


@dataclass(frozen=True)
class Palette:
    surface: str            # chart background
    ink: str                # primary text, observed data
    ink_secondary: str      # secondary text
    muted: str              # axis labels, notes
    grid: str               # gridlines
    axis: str               # axis lines, reference lines
    reference: str          # FluSight-baseline
    series: tuple           # categorical model colors, in assignment order
    horizons: tuple         # horizon -1, 0, 1, 2, 3
    sequential: tuple       # one-hue ramp, low -> high
    sequential_second: tuple  # second one-hue ramp, for a second surface
    diverging: tuple        # better (blue) -> neutral gray -> worse (red)


LIGHT = Palette(
    surface="#ffffff", ink="#0b0b0b", ink_secondary="#52514e", muted="#898781",
    grid="#e1e0d9", axis="#c3c2b7", reference="#898781",
    series=("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"),
    horizons=("#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"),
    sequential=("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"),
    sequential_second=("#fde3d6", "#f8bfa6", "#f39a76", "#eb6834", "#c8501f", "#a03d15", "#782c0c"),
    diverging=("#1c5cab", "#5598e7", "#b7d3f6", "#f0efec", "#f4bcb9", "#e8716f", "#b8302f"),
)

DARK = Palette(
    surface="#1a1a19", ink="#ffffff", ink_secondary="#c3c2b7", muted="#898781",
    grid="#2c2c2a", axis="#383835", reference="#898781",
    series=("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"),
    horizons=("#1c5cab", "#2a78d6", "#5598e7", "#86b6ef", "#b7d3f6"),
    sequential=("#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"),
    sequential_second=("#5a2108", "#782c0c", "#a03d15", "#c8501f", "#eb6834", "#f39a76", "#f8bfa6"),
    diverging=("#86b6ef", "#3987e5", "#1f4a80", "#383835", "#7a2f2d", "#e66767", "#f5aaa8"),
)


def palette(theme: str = "light") -> Palette:
    return DARK if theme == "dark" else LIGHT


def rgba(hex_color: str, alpha: float) -> str:
    red, green, blue = (int(hex_color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({red},{green},{blue},{alpha})"


def colorscale(steps) -> list:
    """Plotly colorscale with the steps spread evenly from 0 to 1."""
    last = len(steps) - 1
    return [[i / last, color] for i, color in enumerate(steps)]


def model_colors(names, theme: str = "light") -> dict:
    """Color for each model name, assigned in the order given. FluSight-baseline is gray; past the
    8th model, extra models are gray too rather than inventing new colors."""
    p = palette(theme)
    colors, next_slot = {}, 0
    for name in names:
        if name in colors:
            continue
        if name == REFERENCE_MODEL or next_slot >= len(p.series):
            colors[name] = p.reference
        else:
            colors[name] = p.series[next_slot]
            next_slot += 1
    return colors


@dataclass
class ChartContext:
    """What every chart function needs besides its data: theme, location names and model colors."""
    theme: str = "light"
    location_names: dict = field(default_factory=dict)
    colors: dict = field(default_factory=dict)

    @property
    def palette(self) -> Palette:
        return palette(self.theme)

    def location_name(self, location: str) -> str:
        return self.location_names.get(location, location)

    def color(self, model: str, all_models=()) -> str:
        """The model's color. Models not given a color up front get the next free one."""
        if model not in self.colors:
            assigned = model_colors([*self.colors, *all_models, model], self.theme)
            self.colors.update({name: c for name, c in assigned.items() if name not in self.colors})
        return self.colors[model]

    def horizon_color(self, horizon: int) -> str:
        return self.palette.horizons[int(horizon) + 1]


def template(theme: str = "light") -> go.layout.Template:
    p = palette(theme)
    axis = dict(
        gridcolor=p.grid, linecolor=p.axis, zeroline=False, ticks="outside", ticklen=4, tickcolor=p.axis,
        tickfont=dict(color=p.muted, size=12), title=dict(font=dict(color=p.ink_secondary, size=13), standoff=10),
        automargin=True,
    )
    scene_axis = dict(
        backgroundcolor=p.surface, gridcolor=p.grid, linecolor=p.axis, zeroline=False, showbackground=True,
        tickfont=dict(color=p.muted, size=11), title=dict(font=dict(color=p.ink_secondary, size=12)),
    )
    return go.layout.Template(layout=dict(
        font=dict(family=FONT, color=p.ink_secondary, size=13),
        title=dict(font=dict(color=p.ink, size=16), x=0, xanchor="left", y=0.97, yanchor="top"),
        paper_bgcolor=p.surface,
        plot_bgcolor=p.surface,
        colorway=list(p.series),
        xaxis={**axis, "showgrid": False, "showline": True},
        yaxis={**axis, "showgrid": True, "showline": False},
        scene=dict(xaxis=scene_axis, yaxis=scene_axis, zaxis=scene_axis),
        legend=dict(orientation="h", x=0, xanchor="left", y=1.02, yanchor="bottom", bgcolor="rgba(0,0,0,0)",
                    font=dict(color=p.ink_secondary, size=12)),
        hoverlabel=dict(bgcolor=p.surface, bordercolor=p.axis, font=dict(family=FONT, color=p.ink, size=12)),
        margin=dict(l=64, r=24, t=112, b=180),
        hovermode="closest",
    ))


def new_figure(ctx: ChartContext, title: str, subtitle: str = "", height: int = 560) -> go.Figure:
    """An empty figure with the theme template and a title (and optional grey subtitle)."""
    figure = go.Figure(layout=dict(template=template(ctx.theme), height=height))
    figure.update_layout(title_text=title_html(ctx, title, subtitle))
    return figure


def title_html(ctx: ChartContext, title: str, subtitle: str = "") -> str:
    if not subtitle:
        return f"<b>{title}</b>"
    return f"<b>{title}</b><br><span style='font-size:12px;color:{ctx.palette.muted}'>{subtitle}</span>"


def empty_figure(ctx: ChartContext, message: str) -> go.Figure:
    return new_figure(ctx, message, height=320)
