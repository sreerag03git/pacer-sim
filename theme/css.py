"""Injected CSS -- the PACER neumorphic (soft UI) design system.

Depth here comes from light, not from lines. The canvas and every card share one
tone; a card reads as *raised* because it casts a dark shadow to the bottom-right
and a light highlight to the top-left (``--shadow``). Inputs and the active nav
item invert that pair (``--shadow-inset``) so they read as *pressed into* the
surface. There are almost no borders. A single toggle flips the whole set between
the soft-light and soft-dark palettes.

Type: Space Grotesk for display and stat numbers, Inter for body, JetBrains Mono
for data. The SVG drawings fill against a dedicated ``--panel`` tone so they stay
legible even though cards are the same colour as the page.
"""

from __future__ import annotations

from theme.palette import palette

_FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Inter:wght@400;500;600;700&"
    "family=Space+Grotesk:wght@500;600;700&"
    "family=JetBrains+Mono:wght@400;500;600&display=swap');"
)

_RULES = """
:root { --radius: 10px; --radius-sm: 7px; --radius-pill: 999px; }

html, body, [class*="css"], .stMarkdown, p, li, label, input, button, select, textarea {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
/* Flat neutral canvas -- the soft tiles earn their depth from shadow alone */
.stApp { background: var(--bg); color: var(--text); }
.block-container { padding-top: 0.6rem; padding-bottom: 4rem; max-width: 1280px; }

/* Display type */
h1, h2, h3, h4, h5, .pacer-display {
  font-family: 'Space Grotesk', 'Inter', sans-serif; color: var(--text); letter-spacing: -0.01em;
}
h1 { font-size: 1.7rem; font-weight: 700; }
h2 { font-size: 1.3rem; font-weight: 600; }
h3 { font-size: 1.08rem; font-weight: 600; margin-top: 0.3rem; }
h4 { font-size: 0.98rem; font-weight: 600; }
p, li, label, .stMarkdown { color: var(--text); }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Data / mono */
[data-testid="stMetricValue"], .pacer-mono, code, pre, [data-testid="stDataFrame"],
[data-testid="stTable"], .stDataFrame, .stCode {
  font-family: 'JetBrains Mono', ui-monospace, monospace; font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum" 1;
}
[data-testid="stMetricLabel"] { color: var(--muted); font-family: 'Inter', sans-serif; font-size: 0.82rem; }
[data-testid="stMetricDelta"] { font-family: 'JetBrains Mono', monospace; }

/* Metric -> flat bordered tile */
[data-testid="stMetric"] {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 0.85rem 1rem;
}
[data-testid="stMetricValue"] {
  font-family: 'Space Grotesk', sans-serif; font-size: 1.7rem; font-weight: 600; color: var(--text);
}

/* Sidebar -- flat, a single hairline divider */
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
[data-testid="stSidebar"] h3 { font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.09em;
  color: var(--muted); font-family: 'Inter', sans-serif; font-weight: 600; }

/* Sidebar nav: a flat menu; the active item is tinted with an accent marker */
[data-testid="stSidebar"] div[role="radiogroup"] { gap: 0.15rem; }
[data-testid="stSidebar"] div[role="radiogroup"] > label {
  display: flex; align-items: center; width: 100%;
  padding: 0.5rem 0.75rem; margin: 0; border-radius: var(--radius-sm);
  cursor: pointer; transition: background 0.12s ease, color 0.12s ease;
  border-left: 2px solid transparent;
  color: var(--muted); font-weight: 500; font-size: 0.92rem; background: transparent;
}
[data-testid="stSidebar"] div[role="radiogroup"] > label:hover { color: var(--text); background: var(--surface-2); }
[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display: none; }  /* hide radio dot */
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
  color: var(--accent); font-weight: 600; background: var(--accent-soft); border-left-color: var(--accent);
}

/* Buttons -- flat bordered; primary is solid accent */
.stButton > button, .stDownloadButton > button {
  border: 1px solid var(--border); background: var(--surface); color: var(--text);
  border-radius: var(--radius-sm); font-weight: 600; font-size: 0.9rem; transition: all 0.12s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover { color: var(--accent); border-color: var(--accent); }
.stButton > button:active, .stDownloadButton > button:active { background: var(--surface-2); }
.stButton > button[kind="primary"] {
  background: var(--accent); color: #fff; border-color: var(--accent);
}
.stButton > button[kind="primary"]:hover { filter: brightness(1.06); color: #fff; }
.stButton > button[kind="primary"]:active { filter: brightness(0.96); }

/* Inputs -- flat, hairline border */
.stTextInput input, .stNumberInput input, [data-baseweb="input"], [data-baseweb="select"] > div,
.stTextArea textarea {
  background: var(--surface) !important; color: var(--text); border: 1px solid var(--border) !important; border-radius: var(--radius-sm);
}
[data-baseweb="input"], [data-baseweb="select"] > div { border-radius: var(--radius-sm); }
.stNumberInput button { background: var(--surface); border: 1px solid var(--border); color: var(--muted); }
.stNumberInput button:hover { color: var(--accent); }
[data-baseweb="slider"] div[role="slider"] { background: var(--accent); }
[data-testid="stSlider"] [data-baseweb="slider"] > div > div > div { background: var(--accent); }

/* Tabs -- flat, the active tab carries an accent underline */
[data-baseweb="tab-list"] { border-bottom: 1px solid var(--border); gap: 0.1rem; flex-wrap: wrap; }
[data-baseweb="tab"] {
  color: var(--muted); font-weight: 600; font-size: 0.9rem; padding: 0.45rem 0.85rem;
  background: transparent; transition: color 0.12s ease;
}
[data-baseweb="tab"]:hover { color: var(--text); }
[data-baseweb="tab"][aria-selected="true"] { color: var(--accent); }
[data-baseweb="tab-highlight"] { background: var(--accent); height: 2px; }
[data-baseweb="tab-border"] { background: transparent; height: 0; }

/* Expander -- flat bordered panel */
[data-testid="stExpander"] { border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); overflow: hidden; }
[data-testid="stExpander"] summary { color: var(--text); font-weight: 600; }
[data-testid="stExpander"] summary:hover { color: var(--accent); }

/* DataFrame / table -- flat bordered */
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; }
[data-testid="stTable"] table { border-color: var(--border); }
[data-testid="stTable"] thead th { background: var(--surface-2); color: var(--muted); font-family: 'Inter', sans-serif; font-weight: 600; }

/* Progress -- flat track, accent fill */
[data-testid="stProgress"] > div { background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius-pill); }
[data-testid="stProgress"] div[role="progressbar"] > div { background: var(--accent); border-radius: var(--radius-pill); }

/* Code blocks -- flat bordered */
pre, code, .stCode { background: var(--surface-2) !important; color: var(--text) !important; border: 1px solid var(--border); border-radius: var(--radius-sm); }

/* Alerts -- flat bordered */
[data-testid="stAlert"] { border-radius: var(--radius-sm); border: 1px solid var(--border); }

/* Hide default chrome */
#MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"], footer { display: none !important; }
[data-testid="stHeader"] { background: transparent; height: 0; }

/* Accessibility: visible keyboard focus (WCAG 2.4.7). The borderless soft
   controls strip the default outline, so keyboard users need an explicit ring. */
.stButton > button:focus-visible, .stDownloadButton > button:focus-visible,
.stNumberInput button:focus-visible,
.stTextInput input:focus-visible, .stNumberInput input:focus-visible, .stTextArea textarea:focus-visible,
[data-baseweb="tab"]:focus-visible,
[data-baseweb="slider"] div[role="slider"]:focus-visible,
[data-testid="stExpander"] summary:focus-visible,
a:focus-visible {
  outline: 2px solid var(--accent); outline-offset: 3px;
}
/* baseweb wraps inputs/selects -- ring the wrapper when the inner control is focused */
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {
  outline: 2px solid var(--accent); outline-offset: 2px;
}
/* the sidebar nav hides the radio dot, so surface focus on the label itself */
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:focus-visible) {
  outline: 2px solid var(--accent); outline-offset: 2px; color: var(--text);
}

/* Respect reduced-motion (WCAG 2.3.3): drop the hover lifts and transitions */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition-duration: 0.001ms !important; animation-duration: 0.001ms !important; }
  .pacer-stat:hover, .pacer-card:hover { transform: none !important; }
}

/* ---- custom components -------------------------------------------------- */

/* Sticky header -- a flat band with a hairline divider */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"]:first-child .pacer-header-marker) {
  position: sticky; top: 0; z-index: 1000;
  background: var(--bg); border-bottom: 1px solid var(--border);
  padding: 0.6rem 0.9rem 0.7rem; margin-bottom: 0.8rem;
}
.pacer-title { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 1.22rem; color: var(--text); line-height: 1.05; letter-spacing: -0.02em; }
.pacer-title .dot { color: var(--accent); }
.pacer-subtitle { color: var(--muted); font-size: 0.78rem; }
.pacer-build { font-family: 'JetBrains Mono', monospace; color: var(--muted); font-size: 0.74rem; text-align: right; line-height: 1.5; }
.pacer-build b { color: var(--text); font-weight: 600; }

/* Hero -- a flat bordered panel with a thin accent top rule */
.pacer-hero { position: relative; border-radius: var(--radius); overflow: hidden; padding: 2rem 2rem; margin: 0.3rem 0 1.2rem 0;
  background: var(--surface); color: var(--text); border: 1px solid var(--border); border-top: 2px solid var(--accent); }
.pacer-hero .eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 0.74rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--accent); font-weight: 600; }
.pacer-hero h1 { color: var(--text); font-size: 2.05rem; font-weight: 700; margin: 0.4rem 0 0.3rem 0; line-height: 1.08; }
.pacer-hero p { color: var(--muted); font-size: 1.0rem; max-width: 760px; margin: 0; line-height: 1.55; }
.pacer-hero .tags { margin-top: 1.1rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
.pacer-hero .tag { font-family: 'JetBrains Mono', monospace; font-size: 0.74rem; padding: 0.25rem 0.6rem; border-radius: var(--radius-sm);
  background: var(--surface-2); color: var(--muted); border: 1px solid var(--border); }

/* Section kicker + lead */
.pacer-kicker { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 0.15rem; }
.pacer-lead { color: var(--muted); font-size: 0.98rem; line-height: 1.55; margin: 0.2rem 0 0.9rem 0; }

/* Stat tile -- flat bordered */
.pacer-stat { border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface);
  padding: 1rem 1.05rem; height: 100%; transition: border-color 0.12s ease; }
.pacer-stat:hover { border-color: var(--accent); }
.pacer-stat .n { font-family: 'Space Grotesk', sans-serif; font-variant-numeric: tabular-nums;
  font-size: 1.7rem; font-weight: 700; color: var(--text); line-height: 1.1; letter-spacing: -0.02em; }
.pacer-stat .l { color: var(--muted); font-size: 0.8rem; margin-top: 0.35rem; line-height: 1.35; }
.pacer-stat.ok .n { color: var(--ok); }
.pacer-stat.danger .n { color: var(--danger); }
.pacer-stat.caution .n { color: var(--caution); }

/* Content card -- flat bordered */
.pacer-card { border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface);
  padding: 1.1rem 1.15rem; height: 100%; transition: border-color 0.12s ease; }
.pacer-card:hover { border-color: var(--accent); }
.pacer-card h4 { margin: 0 0 0.5rem 0; font-size: 0.98rem; }
.pacer-card ul { margin: 0.2rem 0 0 1.05rem; padding: 0; }
.pacer-card li { color: var(--muted); font-size: 0.86rem; margin: 0.25rem 0; line-height: 1.45; }
.pacer-card.accent h4 { color: var(--accent); }
.pacer-card.ok h4 { color: var(--ok); }
.pacer-card.caution h4 { color: var(--caution); }
.pacer-card.danger h4 { color: var(--danger); }

/* Chips -- flat bordered pills */
.pacer-chip { display: inline-block; padding: 0.16rem 0.6rem; border-radius: var(--radius-sm); font-size: 0.72rem;
  font-family: 'JetBrains Mono', monospace; border: 1px solid var(--border); color: var(--muted); background: var(--surface-2); }
.pacer-chip.ok { color: var(--ok); }
.pacer-chip.danger { color: var(--danger); }
.pacer-chip.caution { color: var(--caution); }
.pacer-chip.accent { color: var(--accent); }

.pacer-foot { color: var(--muted); font-size: 0.76rem; margin-top: 2.2rem; padding-top: 0.9rem;
  font-family: 'JetBrains Mono', monospace; border-top: 1px solid var(--border); }

/* Loading screen (shown while the opening analysis runs) */
.pacer-loading { text-align: center; padding: 3.2rem 1rem 1.6rem; }
.pacer-loading .ring { width: 52px; height: 52px; margin: 0 auto 1.2rem; border-radius: 50%;
  border: 3px solid var(--border); border-top-color: var(--accent); animation: pacer-spin 0.9s linear infinite; }
@keyframes pacer-spin { to { transform: rotate(360deg); } }
.pacer-loading h3 { font-size: 1.15rem; margin: 0 0 0.25rem; }
.pacer-loading .msg { color: var(--muted); font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; margin: 0; }

/* Skip + back-to-top */
.pacer-skip { position: absolute; left: -999px; top: 0; background: var(--accent); color: #fff; padding: 0.4rem 0.7rem; border-radius: 0 0 var(--radius-sm) 0; z-index: 2000; }
.pacer-skip:focus { left: 0; }
.pacer-top-link { font-size: 0.8rem; color: var(--muted); }
.pacer-top-link:hover { color: var(--accent); }

@media print {
  [data-testid="stSidebar"], [data-baseweb="tab-list"], .stButton, .pacer-skip { display: none !important; }
  .stApp { background: #fff; color: #000; }
  .pacer-hero, .pacer-card, .pacer-stat { background: #fff !important; color: #000 !important; box-shadow: none !important; border: 1px solid #ccc !important; }
  .block-container { max-width: 100%; }
}

@media (max-width: 640px) {
  .pacer-hero { padding: 1.5rem 1.3rem; } .pacer-hero h1 { font-size: 1.6rem; }
  .block-container { padding-left: 16px; padding-right: 16px; }
}
"""


def theme_css(theme: str) -> str:
    """Return a full ``<style>`` block for the given theme."""
    p = palette(theme)
    root = f"""
:root {{
  --bg: {p['bg']}; --surface: {p['surface']}; --surface-2: {p['surface_2']};
  --panel: {p['panel']}; --panel-border: {p['panel_border']};
  --border: {p['border']}; --text: {p['text']}; --muted: {p['muted']};
  --accent: {p['accent']}; --danger: {p['danger']}; --caution: {p['caution']}; --ok: {p['ok']};
  --accent-soft: {p['accent_soft']}; --danger-soft: {p['danger_soft']};
  --grid: {p['grid']}; --outage: {p['outage_band']};
  --gradient: {p['gradient']}; --gradient-soft: {p['gradient_soft']};
  --shadow: {p['shadow']}; --shadow-hover: {p['shadow_hover']}; --shadow-sm: {p['shadow_sm']};
  --shadow-inset: {p['shadow_inset']}; --shadow-inset-sm: {p['shadow_inset_sm']};
  color-scheme: {'dark' if theme == 'dark' else 'light'};
}}
"""
    return f"<style>{_FONT_IMPORT}\n{root}\n{_RULES}</style>"
