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
        # Flat, professional: a light canvas with white surfaces and a hairline
        # border. Depth is a whisper of shadow, not a soft-UI extrusion.
        # Dribbble Modern: airy white cards on a soft off-white page, deep-ink
        # text, one vivid pink accent. The data-semantic tones (danger/caution/
        # ok) stay as tuned -- the brand pink is chrome, never a data series.
        "bg": "#F8F8FB",                 # soft off-white page
        "surface": "#FFFFFF",            # white cards
        "surface_2": "#F3F3F4",          # muted fill: hover / table header / inputs
        "panel": "#FFFFFF",              # fill for SVG drawings
        "panel_border": "#E7E7E9",       # visible stroke for drawings
        "border": "#E7E7E9",             # hairline border on cards and inputs
        "text": "#0D0C22",               # deep ink
        "muted": "#6E6D7A",              # secondary gray-lavender (AA 4.5:1)
        "accent": "#EA4C89",             # Dribbble pink -- affordances / fills / emphasis
        "accent_ink": "#C7306B",         # darker pink for small pink TEXT (AA on white)
        "cta_bg": "#0D0C22",             # primary CTA: dark-ink pill (spec button-primary)
        "cta_fg": "#FFFFFF",
        "danger": "#C0373E",             # fuse blow / overload (AA 4.5:1)
        "caution": "#A27328",            # warnings -- deep amber (AA-large / graphical 3:1)
        "ok": "#317568",                 # healthy / safe (deep teal, not a bright green; AA 4.5:1)
        # derived
        "accent_soft": "rgba(234, 76, 137, 0.10)",
        "danger_soft": "rgba(192, 55, 62, 0.10)",
        "grid": "rgba(13, 12, 34, 0.06)",
        "outage_band": "rgba(116, 123, 136, 0.08)",
        # flat elevation: a single soft drop shadow, used sparingly with the border
        "shadow_dark": "#E3E7ED",
        "shadow_light": "#FFFFFF",
        "shadow": "0 1px 2px rgba(23,27,35,0.04), 0 2px 6px rgba(23,27,35,0.05)",
        "shadow_hover": "0 2px 5px rgba(23,27,35,0.07), 0 8px 20px rgba(23,27,35,0.08)",
        "shadow_sm": "0 1px 2px rgba(23,27,35,0.05)",
        "shadow_inset": "none",
        "shadow_inset_sm": "none",
        # a quiet single-hue gradient, reserved for the one primary CTA / fills
        "gradient": "linear-gradient(135deg, #EA4C89 0%, #D83A7D 100%)",
        "gradient_soft": "linear-gradient(135deg, rgba(234,76,137,0.10), rgba(216,58,125,0.08))",
        # restrained categorical sequence; first three are the three phases
        "cat1": "#4C5EC4",  # indigo
        "cat2": "#317568",  # teal (matches ok)
        "cat3": "#A27328",  # amber (matches caution)
        "cat4": "#6B7791",  # slate
        "cat5": "#B06A66",  # muted terracotta
    },
    "dark": {
        "bg": "#1B1E27",
        "surface": "#23262F",
        "surface_2": "#2A2E39",
        "panel": "#2A2E39",
        "panel_border": "#3A3F4E",
        "border": "#333845",
        "text": "#E6E8EE",
        "muted": "#8990A0",
        "accent": "#EA4C89",
        "accent_ink": "#F58CB6",
        "cta_bg": "#EA4C89",
        "cta_fg": "#0D0C22",
        "danger": "#E07179",
        "caution": "#E0A54A",
        "ok": "#4FB39E",
        "accent_soft": "rgba(234, 76, 137, 0.16)",
        "danger_soft": "rgba(224, 113, 121, 0.14)",
        "grid": "rgba(230, 232, 238, 0.08)",
        "outage_band": "rgba(137, 144, 160, 0.10)",
        "shadow_dark": "#15171E",
        "shadow_light": "#2F3440",
        "shadow": "0 1px 2px rgba(0,0,0,0.30), 0 2px 8px rgba(0,0,0,0.30)",
        "shadow_hover": "0 2px 6px rgba(0,0,0,0.40), 0 10px 24px rgba(0,0,0,0.40)",
        "shadow_sm": "0 1px 2px rgba(0,0,0,0.35)",
        "shadow_inset": "none",
        "shadow_inset_sm": "none",
        "gradient": "linear-gradient(135deg, #EA4C89 0%, #D83A7D 100%)",
        "gradient_soft": "linear-gradient(135deg, rgba(234,76,137,0.18), rgba(216,58,125,0.12))",
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
