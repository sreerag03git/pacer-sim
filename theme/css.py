"""Injected CSS: sets the active palette as :root variables and restyles
Streamlit's containers so a single toggle flips every surface, border, text and
control. Fonts are IBM Plex Sans (text) and IBM Plex Mono (all numeric values
and tables, with tabular figures)."""

from __future__ import annotations

from theme.palette import palette

_FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=IBM+Plex+Sans:wght@400;500;600&"
    "family=IBM+Plex+Mono:wght@400;500&display=swap');"
)

# Static rules; all colours come through CSS variables so only the :root block
# changes between themes.
_RULES = """
html, body, [class*="css"] { font-family: 'IBM Plex Sans', system-ui, sans-serif; }

.stApp { background: var(--bg); color: var(--text); }
.block-container { padding-top: 0.5rem; padding-bottom: 3rem; max-width: 1280px; }

/* Headings: clear hierarchy, left aligned, no oversized hero. */
h1 { font-size: 1.5rem; font-weight: 600; letter-spacing: -0.01em; color: var(--text); }
h2 { font-size: 1.15rem; font-weight: 600; color: var(--text); margin-top: 0.4rem; }
h3 { font-size: 1.0rem; font-weight: 600; color: var(--text); }
h4, h5 { font-size: 0.92rem; font-weight: 600; color: var(--text); }
p, li, label, .stMarkdown { color: var(--text); }
a { color: var(--accent); }

/* Numeric values and tables use IBM Plex Mono with tabular figures. */
[data-testid="stMetricValue"], .pacer-mono, code, pre,
[data-testid="stDataFrame"], [data-testid="stTable"], .stDataFrame {
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum" 1;
}
[data-testid="stMetricValue"] { font-size: 1.5rem; font-weight: 500; color: var(--text); }
[data-testid="stMetricLabel"] { color: var(--muted); font-family: 'IBM Plex Sans', sans-serif; }
[data-testid="stMetricDelta"] { font-family: 'IBM Plex Mono', monospace; }

/* Sidebar */
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
[data-testid="stSidebar"] .block-container { padding-top: 1rem; }

/* Inputs */
.stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div,
[data-baseweb="input"], [data-baseweb="select"] > div {
  background: var(--bg); color: var(--text); border-color: var(--border);
}
.stNumberInput button { background: var(--bg); border-color: var(--border); color: var(--text); }

/* Sliders */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] { background: var(--accent); }

/* Buttons */
.stButton > button, .stDownloadButton > button {
  border: 1px solid var(--border); background: var(--surface); color: var(--text);
  border-radius: 4px; font-weight: 500; transition: none;
}
.stButton > button:hover, .stDownloadButton > button:hover { border-color: var(--accent); color: var(--accent); }
.stButton > button[kind="primary"] {
  background: var(--accent); color: #fff; border-color: var(--accent);
}
.stButton > button[kind="primary"]:hover { filter: brightness(0.94); color: #fff; }

/* Tabs */
[data-baseweb="tab-list"] { border-bottom: 1px solid var(--border); gap: 0.25rem; }
[data-baseweb="tab"] { color: var(--muted); font-weight: 500; }
[data-baseweb="tab"][aria-selected="true"] { color: var(--text); }
[data-baseweb="tab-highlight"] { background: var(--accent); }

/* Expander */
[data-testid="stExpander"] { border: 1px solid var(--border); border-radius: 4px; background: var(--surface); }
[data-testid="stExpander"] summary { color: var(--text); }

/* DataFrame / table */
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 4px; }
[data-testid="stTable"] table { border-color: var(--border); }
[data-testid="stTable"] thead th { background: var(--bg); color: var(--muted); font-family: 'IBM Plex Sans', sans-serif; }

/* Progress bar */
[data-testid="stProgress"] div[role="progressbar"] > div { background-color: var(--accent); }

/* Alerts keep the semantic palette */
[data-testid="stAlert"] { border-radius: 4px; border: 1px solid var(--border); }

/* Code blocks (copy buttons live here) */
pre, code { background: var(--bg) !important; color: var(--text) !important; border: 1px solid var(--border); border-radius: 4px; }

/* Hide default Streamlit chrome for a clean engineering look */
#MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"], footer { display: none !important; }
[data-testid="stHeader"] { background: transparent; height: 0; }

/* ---- custom components -------------------------------------------------- */

/* Sticky top header: the container holding the header marker sticks to the top. */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"]:first-child .pacer-header-marker) {
  position: sticky; top: 0; z-index: 1000;
  background: var(--surface); border-bottom: 1px solid var(--border);
  padding: 0.5rem 0.25rem 0.5rem 0.25rem; margin-bottom: 0.5rem;
}
.pacer-title { font-weight: 600; font-size: 1.15rem; color: var(--text); line-height: 1.1; }
.pacer-subtitle { color: var(--muted); font-size: 0.78rem; }
.pacer-build { font-family: 'IBM Plex Mono', monospace; color: var(--muted); font-size: 0.78rem; text-align: right; }
.pacer-build b { color: var(--text); font-weight: 500; }

/* Status chips */
.pacer-chip { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 3px; font-size: 0.72rem;
  font-family: 'IBM Plex Mono', monospace; border: 1px solid var(--border); }
.pacer-chip.ok { color: var(--ok); border-color: var(--ok); }
.pacer-chip.danger { color: var(--danger); border-color: var(--danger); }
.pacer-chip.caution { color: var(--caution); border-color: var(--caution); }
.pacer-chip.accent { color: var(--accent); border-color: var(--accent); }

.pacer-foot { color: var(--muted); font-size: 0.76rem; border-top: 1px solid var(--border);
  margin-top: 2rem; padding-top: 0.6rem; font-family: 'IBM Plex Mono', monospace; }

/* Skip-to-content link: visible only on keyboard focus */
.pacer-skip { position: absolute; left: -999px; top: 0; background: var(--accent); color: #fff;
  padding: 0.4rem 0.7rem; border-radius: 0 0 4px 0; z-index: 2000; }
.pacer-skip:focus { left: 0; }

/* Back-to-top link */
.pacer-top-link { font-size: 0.8rem; color: var(--muted); text-decoration: none; }
.pacer-top-link:hover { color: var(--accent); }

/* Print-friendly: hide sidebar and chrome, force light ink on white */
@media print {
  [data-testid="stSidebar"], [data-baseweb="tab-list"], .stButton, .pacer-skip { display: none !important; }
  .stApp { background: #fff; color: #000; }
  .block-container { max-width: 100%; }
}
"""


def theme_css(theme: str) -> str:
    """Return a full ``<style>`` block for the given theme."""
    p = palette(theme)
    root = f"""
:root {{
  --bg: {p['bg']};
  --surface: {p['surface']};
  --border: {p['border']};
  --text: {p['text']};
  --muted: {p['muted']};
  --accent: {p['accent']};
  --danger: {p['danger']};
  --caution: {p['caution']};
  --ok: {p['ok']};
  --accent-soft: {p['accent_soft']};
  --danger-soft: {p['danger_soft']};
  --grid: {p['grid']};
  --outage: {p['outage_band']};
  color-scheme: {'dark' if theme == 'dark' else 'light'};
}}
"""
    return f"<style>{_FONT_IMPORT}\n{root}\n{_RULES}</style>"
