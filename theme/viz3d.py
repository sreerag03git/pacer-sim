"""3D technical visualisations (Plotly), bound to the active theme.

A 3D transformer object -- oil tank, core and three phase windings -- coloured by
each winding's live hot-spot temperature, so the worst phase literally runs hotter
on screen. Pure Plotly (no three.js), so it works offline and theme-aware.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from theme.plotly_template import semantic, style_figure

# cool -> hot temperature ramp (blue -> amber -> red)
_TEMP_SCALE = [[0.0, "#3B6FB0"], [0.5, "#E0A54A"], [1.0, "#C0373E"]]


def _cylinder(cx, cy, r, z0, z1, *, color=None, value=None, cmin=0.0, cmax=1.0,
              opacity=1.0, showscale=False, name="", n=28):
    """A vertical cylinder as a parametric surface; either a solid ``color`` or a
    ``value`` mapped through the temperature scale."""
    th = np.linspace(0.0, 2.0 * np.pi, n)
    x = cx + r * np.cos(th)
    y = cy + r * np.sin(th)
    big = np.vstack([x, x]), np.vstack([y, y]), np.vstack([np.full(n, z0), np.full(n, z1)])
    if color is not None:
        return go.Surface(x=big[0], y=big[1], z=big[2], surfacecolor=np.zeros((2, n)),
                          colorscale=[[0, color], [1, color]], showscale=False,
                          opacity=opacity, name=name, hoverinfo="name")
    return go.Surface(x=big[0], y=big[1], z=big[2], surfacecolor=np.full((2, n), value),
                      colorscale=_TEMP_SCALE, cmin=cmin, cmax=cmax, showscale=showscale,
                      opacity=opacity, name=name, hoverinfo="name",
                      colorbar=dict(title="C", thickness=12, len=0.6))


def transformer_thermal_3d(temps_c, theme, ambient_c=40.0):
    """A 3D transformer coloured by per-phase winding hot-spot temperature.

    ``temps_c`` is a length-3 array (phases A/B/C). The oil tank and core are
    structural; the three windings carry the live temperature colour, and the
    hottest winding is labelled -- this is the per-phase imbalance made physical.
    """
    temps = np.asarray(temps_c, dtype=float).ravel()
    sem = semantic(theme)
    cmin, cmax = 60.0, max(140.0, float(temps.max()) + 5.0)
    fig = style_figure(go.Figure(), theme, height=440)

    # oil tank (translucent) + core (muted), both structural
    fig.add_trace(_cylinder(0, 0, 3.0, 0.0, 5.0, color=sem["accent"], opacity=0.07, name="oil tank"))
    fig.add_trace(_cylinder(0, 0, 0.6, 0.4, 4.6, color=sem["muted"], opacity=0.55, name="core"))

    # three phase windings around the core, coloured by their hot-spot
    labels = ["A", "B", "C"]
    for i, ang in enumerate(np.deg2rad([90, 210, 330])):
        cx, cy = 1.55 * np.cos(ang), 1.55 * np.sin(ang)
        fig.add_trace(_cylinder(cx, cy, 0.62, 0.8, 4.2, value=float(temps[i]),
                                cmin=cmin, cmax=cmax, showscale=(i == 0),
                                name=f"winding {labels[i]}: {temps[i]:.0f} C"))
        fig.add_trace(go.Scatter3d(x=[cx], y=[cy], z=[4.7], mode="text",
                                   text=[f"&#966;{labels[i]} {temps[i]:.0f}&#176;C"],
                                   textfont=dict(color=sem["text"], size=12), showlegend=False, hoverinfo="skip"))

    hot = labels[int(np.argmax(temps))]
    _noax = dict(showbackground=False, showgrid=False, zeroline=False, showticklabels=False, title="")
    fig.update_layout(title=f"3D transformer -- windings by hot-spot (worst phase {hot})",
                      margin=dict(l=0, r=0, t=36, b=0), showlegend=False,
                      scene=dict(xaxis=_noax, yaxis=_noax, zaxis=_noax, aspectmode="data",
                                 camera=dict(eye=dict(x=1.7, y=1.7, z=1.1))))
    return fig
