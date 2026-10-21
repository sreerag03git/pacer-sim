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
:root { --radius: 20px; --radius-sm: 13px; --radius-pill: 999px; }

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

/* Metric -> soft raised tile */
[data-testid="stMetric"] {
  background: var(--surface); border-radius: var(--radius); padding: 0.85rem 1rem;
  box-shadow: var(--shadow);
}
[data-testid="stMetricValue"] {
  font-family: 'Space Grotesk', sans-serif; font-size: 1.7rem; font-weight: 600; color: var(--text);
}

/* Sidebar -- same tone as the canvas; no divider line */
[data-testid="stSidebar"] { background: var(--bg); border-right: none; }
[data-testid="stSidebar"] > div { box-shadow: var(--shadow-inset-sm); }
[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
[data-testid="stSidebar"] h3 { font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.09em;
  color: var(--muted); font-family: 'Inter', sans-serif; font-weight: 600; }

/* Sidebar nav: a soft recessed menu; the active item is pressed in */
[data-testid="stSidebar"] div[role="radiogroup"] { gap: 0.3rem; }
[data-testid="stSidebar"] div[role="radiogroup"] > label {
  display: flex; align-items: center; width: 100%;
  padding: 0.55rem 0.8rem; margin: 0; border-radius: var(--radius-sm);
  cursor: pointer; transition: all 0.16s ease; border: none;
  color: var(--muted); font-weight: 500; font-size: 0.92rem; background: var(--bg);
}
[data-testid="stSidebar"] div[role="radiogroup"] > label:hover { color: var(--text); box-shadow: var(--shadow-sm); }
[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display: none; }  /* hide radio dot */
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
  color: var(--accent); font-weight: 600; box-shadow: var(--shadow-inset);
}

/* Buttons -- soft raised; depress on click */
.stButton > button, .stDownloadButton > button {
  border: none; background: var(--surface); color: var(--text);
  border-radius: var(--radius-sm); font-weight: 600; font-size: 0.9rem;
  transition: all 0.14s ease; box-shadow: var(--shadow-sm);
}
.stButton > button:hover, .stDownloadButton > button:hover { color: var(--accent); box-shadow: var(--shadow); }
.stButton > button:active, .stDownloadButton > button:active { box-shadow: var(--shadow-inset-sm); color: var(--accent); }
.stButton > button[kind="primary"] {
  background-image: var(--gradient); color: #fff; box-shadow: var(--shadow);
}
.stButton > button[kind="primary"]:hover { filter: brightness(1.05); color: #fff; box-shadow: var(--shadow-hover); }
.stButton > button[kind="primary"]:active { box-shadow: var(--shadow-inset); filter: brightness(0.98); }

/* Inputs -- recessed */
.stTextInput input, .stNumberInput input, [data-baseweb="input"], [data-baseweb="select"] > div,
.stTextArea textarea {
  background: var(--bg) !important; color: var(--text); border: none !important; border-radius: var(--radius-sm);
  box-shadow: var(--shadow-inset-sm);
}
[data-baseweb="input"], [data-baseweb="select"] > div { border-radius: var(--radius-sm); }
.stNumberInput button { background: var(--surface); border: none; color: var(--muted); box-shadow: var(--shadow-sm); }
.stNumberInput button:hover { color: var(--accent); }
[data-baseweb="slider"] div[role="slider"] { background: var(--accent); box-shadow: var(--shadow-sm); }
[data-testid="stSlider"] [data-baseweb="slider"] > div > div > div { background: var(--accent); }

/* Tabs -- the active tab lifts out as a soft pill */
[data-baseweb="tab-list"] { border-bottom: none; gap: 0.35rem; flex-wrap: wrap; padding: 0.3rem 0; }
[data-baseweb="tab"] {
  color: var(--muted); font-weight: 600; font-size: 0.9rem; padding: 0.45rem 0.9rem;
  border-radius: var(--radius-pill); background: var(--bg); transition: all 0.16s ease;
}
[data-baseweb="tab"]:hover { color: var(--text); box-shadow: var(--shadow-sm); }
[data-baseweb="tab"][aria-selected="true"] { color: var(--accent); box-shadow: var(--shadow); }
[data-baseweb="tab-highlight"] { background: transparent; height: 0; }
[data-baseweb="tab-border"] { background: transparent; height: 0; }

/* Expander -- soft raised panel */
[data-testid="stExpander"] { border: none; border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow); overflow: hidden; }
[data-testid="stExpander"] summary { color: var(--text); font-weight: 600; }
[data-testid="stExpander"] summary:hover { color: var(--accent); }

/* DataFrame / table -- recessed well */
[data-testid="stDataFrame"] { border: none; border-radius: var(--radius-sm); overflow: hidden; box-shadow: var(--shadow-inset-sm); }
[data-testid="stTable"] table { border-color: var(--border); }
[data-testid="stTable"] thead th { background: var(--surface-2); color: var(--muted); font-family: 'Inter', sans-serif; font-weight: 600; }

/* Progress -- recessed track, gradient fill */
[data-testid="stProgress"] > div { background: var(--bg); border-radius: var(--radius-pill); box-shadow: var(--shadow-inset-sm); }
[data-testid="stProgress"] div[role="progressbar"] > div { background-image: var(--gradient); border-radius: var(--radius-pill); }

/* Code blocks -- recessed */
pre, code, .stCode { background: var(--bg) !important; color: var(--text) !important; border: none; border-radius: var(--radius-sm); box-shadow: var(--shadow-inset-sm); }

/* Alerts -- soft raised */
[data-testid="stAlert"] { border-radius: var(--radius-sm); border: none; box-shadow: var(--shadow-sm); }

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

/* Sticky header -- an opaque band that stays flush with the flat canvas */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"]:first-child .pacer-header-marker) {
  position: sticky; top: 0; z-index: 1000;
  background: var(--bg);
  padding: 0.6rem 0.9rem 0.7rem; margin-bottom: 0.8rem; border-radius: 0 0 var(--radius) var(--radius);
  box-shadow: var(--shadow-sm);
}
.pacer-title { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 1.22rem; color: var(--text); line-height: 1.05; letter-spacing: -0.02em; }
.pacer-title .dot { color: var(--accent); }
.pacer-subtitle { color: var(--muted); font-size: 0.78rem; }
.pacer-build { font-family: 'JetBrains Mono', monospace; color: var(--muted); font-size: 0.74rem; text-align: right; line-height: 1.5; }
.pacer-build b { color: var(--text); font-weight: 600; }

/* Hero -- a soft raised panel; depth from shadow, no gloss */
.pacer-hero { position: relative; border-radius: var(--radius); overflow: hidden; padding: 2.1rem 2.1rem; margin: 0.3rem 0 1.2rem 0;
  background: var(--surface); color: var(--text); box-shadow: var(--shadow); }
.pacer-hero .eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 0.74rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--accent); font-weight: 600; }
.pacer-hero h1 { color: var(--text); font-size: 2.05rem; font-weight: 700; margin: 0.4rem 0 0.3rem 0; line-height: 1.08; }
.pacer-hero p { color: var(--muted); font-size: 1.0rem; max-width: 760px; margin: 0; line-height: 1.55; }
.pacer-hero .tags { margin-top: 1.1rem; display: flex; gap: 0.6rem; flex-wrap: wrap; }
.pacer-hero .tag { font-family: 'JetBrains Mono', monospace; font-size: 0.74rem; padding: 0.3rem 0.7rem; border-radius: var(--radius-pill);
  background: var(--bg); color: var(--muted); box-shadow: var(--shadow-sm); }

/* Section kicker + lead */
.pacer-kicker { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 0.15rem; }
.pacer-lead { color: var(--muted); font-size: 0.98rem; line-height: 1.55; margin: 0.2rem 0 0.9rem 0; }

/* Stat tile -- soft raised */
.pacer-stat { border: none; border-radius: var(--radius); background: var(--surface);
  padding: 1rem 1.05rem; height: 100%; box-shadow: var(--shadow); transition: all 0.18s ease; }
.pacer-stat:hover { transform: translateY(-3px); box-shadow: var(--shadow-hover); }
.pacer-stat .n { font-family: 'Space Grotesk', sans-serif; font-variant-numeric: tabular-nums;
  font-size: 1.7rem; font-weight: 700; color: var(--text); line-height: 1.1; letter-spacing: -0.02em; }
.pacer-stat .l { color: var(--muted); font-size: 0.8rem; margin-top: 0.35rem; line-height: 1.35; }
.pacer-stat.ok .n { color: var(--ok); }
.pacer-stat.danger .n { color: var(--danger); }
.pacer-stat.caution .n { color: var(--caution); }

/* Content card -- soft raised */
.pacer-card { border: none; border-radius: var(--radius); background: var(--surface);
  padding: 1.1rem 1.15rem; height: 100%; box-shadow: var(--shadow); transition: all 0.18s ease; }
.pacer-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-hover); }
.pacer-card h4 { margin: 0 0 0.5rem 0; font-size: 0.98rem; }
.pacer-card ul { margin: 0.2rem 0 0 1.05rem; padding: 0; }
.pacer-card li { color: var(--muted); font-size: 0.86rem; margin: 0.25rem 0; line-height: 1.45; }
.pacer-card.accent h4 { color: var(--accent); }
.pacer-card.ok h4 { color: var(--ok); }
.pacer-card.caution h4 { color: var(--caution); }
.pacer-card.danger h4 { color: var(--danger); }

/* Chips -- soft raised pills */
.pacer-chip { display: inline-block; padding: 0.18rem 0.65rem; border-radius: var(--radius-pill); font-size: 0.72rem;
  font-family: 'JetBrains Mono', monospace; border: none; color: var(--muted); background: var(--bg); box-shadow: var(--shadow-sm); }
.pacer-chip.ok { color: var(--ok); }
.pacer-chip.danger { color: var(--danger); }
.pacer-chip.caution { color: var(--caution); }
.pacer-chip.accent { color: var(--accent); }

.pacer-foot { color: var(--muted); font-size: 0.76rem; margin-top: 2.2rem; padding-top: 0.9rem;
  font-family: 'JetBrains Mono', monospace; box-shadow: inset 0 1px 0 var(--border); }

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
