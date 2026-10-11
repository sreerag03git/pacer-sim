"""The two engineering-grade palettes (exact hexes) plus derived tints.

Desaturated, restrained, no neon. ``danger`` is reserved for genuinely bad
states (fuse blow, overload), ``caution`` for warnings, ``accent`` for the
primary series. The categorical sequence is an explicit muted set -- never a
rainbow default.
"""

from __future__ import annotations

THEMES = ("light", "dark")

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#F7F7F5",
        "surface": "#FFFFFF",
        "border": "#E4E4E1",
        "text": "#27272A",
        "muted": "#71717A",
        "accent": "#3D5A80",  # steel blue -- primary series
        "danger": "#8B4A47",  # brick -- fuse blow / overload only
        "caution": "#8A6D3B",  # amber -- warnings
        "ok": "#4A6B52",  # sage -- healthy / safe
        # derived
        "accent_soft": "rgba(61, 90, 128, 0.12)",
        "danger_soft": "rgba(139, 74, 71, 0.12)",
        "grid": "rgba(39, 39, 42, 0.10)",
        "outage_band": "rgba(113, 113, 122, 0.10)",
        # muted categorical sequence (no rainbow); first three = the three phases
        "cat1": "#3D5A80",  # steel blue
        "cat2": "#5E8B7E",  # muted teal-green
        "cat3": "#6E7681",  # slate grey
        "cat4": "#A0885B",  # muted tan
        "cat5": "#7E5D6B",  # muted mauve
    },
    "dark": {
        "bg": "#141517",
        "surface": "#1E2024",
        "border": "#33373D",
        "text": "#E4E4E2",
        "muted": "#A1A1A3",
        "accent": "#6B8CAE",
        "danger": "#B5706C",
        "caution": "#B39760",
        "ok": "#7A9B82",
        # derived
        "accent_soft": "rgba(107, 140, 174, 0.16)",
        "danger_soft": "rgba(181, 112, 108, 0.16)",
        "grid": "rgba(228, 228, 226, 0.10)",
        "outage_band": "rgba(161, 161, 163, 0.12)",
        "cat1": "#6B8CAE",
        "cat2": "#7FB0A1",
        "cat3": "#9AA2AD",
        "cat4": "#C2A977",
        "cat5": "#AD8898",
    },
}


def palette(theme: str) -> dict[str, str]:
    """Return the colour dict for ``theme`` (falls back to light)."""
    return PALETTES.get(theme, PALETTES["light"])
