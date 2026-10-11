"""Theme system: a single source of truth for colours, the injected CSS that
restyles Streamlit's containers, and the Plotly templates bound to the active
theme. The dark/light switch flips every surface, border, text colour and chart
in one action."""

from theme.palette import PALETTES, THEMES, palette
from theme.css import theme_css
from theme.plotly_template import (
    phase_colors,
    semantic,
    style_figure,
    themed_figure,
)

__all__ = [
    "PALETTES",
    "THEMES",
    "palette",
    "theme_css",
    "phase_colors",
    "semantic",
    "style_figure",
    "themed_figure",
]
