"""Plotly templates bound to the active theme.

Charts are transparent to the surface, with muted gridlines, thin lines, no
shadows and no 3D. The categorical sequence is the explicit muted set from the
palette -- never a rainbow default. Semantic colours (danger / caution / ok) are
exposed separately so callers reserve danger for genuinely bad states.
"""

from __future__ import annotations

import plotly.graph_objects as go

from theme.palette import palette

_FONT = "Inter, system-ui, sans-serif"
_MONO = "JetBrains Mono, monospace"


def _template(theme: str) -> go.layout.Template:
    p = palette(theme)
    seq = [p["cat1"], p["cat2"], p["cat3"], p["cat4"], p["cat5"]]
    tpl = go.layout.Template()
    tpl.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=_FONT, color=p["text"], size=13),
        colorway=seq,
        margin=dict(l=56, r=20, t=36, b=44),
        xaxis=dict(
            gridcolor=p["grid"], zerolinecolor=p["grid"], linecolor=p["border"],
            tickfont=dict(family=_MONO, size=11, color=p["muted"]),
            title=dict(font=dict(family=_FONT, size=12, color=p["muted"])),
        ),
        yaxis=dict(
            gridcolor=p["grid"], zerolinecolor=p["grid"], linecolor=p["border"],
            tickfont=dict(family=_MONO, size=11, color=p["muted"]),
            title=dict(font=dict(family=_FONT, size=12, color=p["muted"])),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", font=dict(size=11, color=p["text"]),
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
        ),
        hoverlabel=dict(font=dict(family=_MONO, size=11), bordercolor=p["border"]),
        title=dict(font=dict(family=_FONT, size=13, color=p["text"]), x=0, xanchor="left"),
    )
    return tpl


def phase_colors(theme: str) -> list[str]:
    """The three per-phase line colours (muted, non-semantic)."""
    p = palette(theme)
    return [p["cat1"], p["cat2"], p["cat3"]]


def semantic(theme: str) -> dict[str, str]:
    """Semantic colours: danger / caution / ok / accent / muted / border / grid / outage."""
    p = palette(theme)
    out = {k: p[k] for k in ("danger", "caution", "ok", "accent", "muted", "border", "grid", "text", "surface")}
    out["outage"] = p["outage_band"]  # palette stores this as 'outage_band'
    return out


def style_figure(fig: go.Figure, theme: str, height: int | None = None) -> go.Figure:
    """Apply the themed template (and optional height) to an existing figure.

    The backgrounds are forced transparent *directly on the layout* (not only via
    the template) so the chart always shows the themed page through it -- otherwise
    Streamlit injects its static config ``[theme]`` colours and the plot would read
    light even in dark mode.
    """
    fig.update_layout(template=_template(theme))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    if height is not None:
        fig.update_layout(height=height)
    return fig


def themed_figure(theme: str, height: int | None = None) -> go.Figure:
    """A new figure with the themed template already applied."""
    fig = go.Figure()
    return style_figure(fig, theme, height)
