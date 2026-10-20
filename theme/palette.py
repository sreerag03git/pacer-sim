"""The two palettes for the PACER design system -- neumorphic + minimalist.

Neumorphism builds depth from light, not from lines. Surfaces share the exact
tone of the canvas; what makes a card feel raised is a *pair* of shadows -- a
dark one cast to the bottom-right and a light highlight to the top-left. Pressed
elements (inputs, the active nav item) invert that pair to look recessed. So the
palette carries no hard borders for cards; instead it exposes ``shadow`` (raised),
``shadow_hover`` (lifted), ``shadow_sm`` (small raised), ``shadow_inset`` and
``shadow_inset_sm`` (pressed).

The colour story is deliberately restrained: a near-neutral grey canvas, one
muted indigo accent, and sober semantic tones (red / amber / teal) reserved for
meaning. No bright greens, violets or roses -- minimalism over decoration. A
separate ``panel`` tone gives the SVG drawings a fill that stays legible against
a same-coloured canvas.

Both light and dark are first-class. Every key here is consumed either by the
injected CSS (:root variables) or by the Plotly template / SVG diagrams, so the
whole app -- surfaces, shadows, text, charts and drawings -- switches in one toggle.
"""

from __future__ import annotations

THEMES = ("light", "dark")

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        # Neumorphic base: canvas and card surfaces share this exact neutral tone.
        "bg": "#E8EBEF",
        "surface": "#E8EBEF",
        "surface_2": "#EFF1F5",          # faint raised tint (hover / sub-surfaces)
        "panel": "#F4F6F9",              # legible fill for SVG drawings
        "panel_border": "#CDD3DD",       # visible stroke for drawings
        "border": "#D6DBE3",             # near-invisible hairline (used sparingly)
        "text": "#272B33",
        "muted": "#646A75",              # WCAG AA (4.5:1) on the light canvas
        "accent": "#4C5EC4",             # one muted indigo -- brand / primary series
        "danger": "#C0373E",             # fuse blow / overload (AA 4.5:1)
        "caution": "#A27328",            # warnings -- deep amber (AA-large / graphical 3:1)
        "ok": "#317568",                 # healthy / safe (deep teal, not a bright green; AA 4.5:1)
        # derived
        "accent_soft": "rgba(76, 94, 196, 0.12)",
        "danger_soft": "rgba(209, 92, 99, 0.12)",
        "grid": "rgba(39, 43, 51, 0.06)",
        "outage_band": "rgba(116, 123, 136, 0.10)",
        # neumorphic shadow pair -- dark to the bottom-right, light to the top-left
        "shadow_dark": "#C5CAD3",
        "shadow_light": "#FFFFFF",
        "shadow": "6px 6px 14px #C5CAD3, -6px -6px 14px #FFFFFF",
        "shadow_hover": "9px 9px 22px #BCC2CC, -9px -9px 22px #FFFFFF",
        "shadow_sm": "3px 3px 7px #CBD0D9, -3px -3px 7px #FFFFFF",
        "shadow_inset": "inset 4px 4px 9px #C5CAD3, inset -4px -4px 9px #FFFFFF",
        "shadow_inset_sm": "inset 2px 2px 5px #CBD0D9, inset -2px -2px 5px #FFFFFF",
        # a quiet single-hue gradient, reserved for the one primary CTA / fills
        "gradient": "linear-gradient(135deg, #4C5EC4 0%, #3E4FB0 100%)",
        "gradient_soft": "linear-gradient(135deg, rgba(76,94,196,0.10), rgba(62,79,176,0.08))",
        # restrained categorical sequence; first three are the three phases
        "cat1": "#4C5EC4",  # indigo
        "cat2": "#317568",  # teal (matches ok)
        "cat3": "#A27328",  # amber (matches caution)
        "cat4": "#6B7791",  # slate
        "cat5": "#B06A66",  # muted terracotta
    },
    "dark": {
        "bg": "#23262F",
        "surface": "#23262F",
        "surface_2": "#2A2E39",
        "panel": "#2E323F",
        "panel_border": "#3A3F4E",
        "border": "#333845",
        "text": "#E6E8EE",
        "muted": "#8990A0",
        "accent": "#7886E6",
        "danger": "#E07179",
        "caution": "#E0A54A",
        "ok": "#4FB39E",
        "accent_soft": "rgba(120, 134, 230, 0.16)",
        "danger_soft": "rgba(224, 113, 121, 0.16)",
        "grid": "rgba(230, 232, 238, 0.08)",
        "outage_band": "rgba(137, 144, 160, 0.12)",
        "shadow_dark": "#171A21",
        "shadow_light": "#2F3440",
        "shadow": "6px 6px 14px #171A21, -6px -6px 14px #2F3440",
        "shadow_hover": "9px 9px 22px #12141A, -9px -9px 22px #333845",
        "shadow_sm": "3px 3px 7px #1B1E26, -3px -3px 7px #2C313C",
        "shadow_inset": "inset 4px 4px 9px #171A21, inset -4px -4px 9px #2F3440",
        "shadow_inset_sm": "inset 2px 2px 5px #1B1E26, inset -2px -2px 5px #2C313C",
        "gradient": "linear-gradient(135deg, #3E4AA8 0%, #333E96 100%)",
        "gradient_soft": "linear-gradient(135deg, rgba(120,134,230,0.16), rgba(90,104,200,0.12))",
        "cat1": "#7886E6",
        "cat2": "#4FB39E",
        "cat3": "#E0A54A",
        "cat4": "#8893AE",
        "cat5": "#CC8683",
    },
}


def palette(theme: str) -> dict[str, str]:
    """Return the colour dict for ``theme`` (falls back to light)."""
    return PALETTES.get(theme, PALETTES["light"])
