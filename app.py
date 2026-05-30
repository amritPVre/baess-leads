import streamlit as st

st.set_page_config(
    page_title="BAESS Leads",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Global styles ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Mono', monospace;
    background: #0a0a0f;
    color: #e2e8f0;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0f0f1a !important;
    border-right: 1px solid #1e293b;
}
section[data-testid="stSidebar"] .stMarkdown h1 {
    font-family: 'Syne', sans-serif;
    font-size: 1.4rem;
    background: linear-gradient(135deg, #38bdf8, #818cf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
}

/* Metrics */
[data-testid="metric-container"] {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 16px;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #0ea5e9, #6366f1);
    color: white;
    border: none;
    border-radius: 6px;
    font-family: 'DM Mono', monospace;
    font-weight: 500;
    letter-spacing: 0.3px;
    transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.85; }

/* DataFrames */
[data-testid="stDataFrame"] { border: 1px solid #1e293b; border-radius: 8px; }

/* Inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    background: #111827 !important;
    border: 1px solid #1e293b !important;
    color: #e2e8f0 !important;
    font-family: 'DM Mono', monospace !important;
    border-radius: 6px !important;
}

/* Section headers */
.section-header {
    font-family: 'Syne', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: #38bdf8;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
    text-transform: uppercase;
}

/* Status badges */
.badge-pending  { background:#1e293b; color:#94a3b8; padding:2px 8px; border-radius:4px; font-size:0.75rem; }
.badge-enriched { background:#064e3b; color:#6ee7b7; padding:2px 8px; border-radius:4px; font-size:0.75rem; }
.badge-dm_ready { background:#1e1b4b; color:#a5b4fc; padding:2px 8px; border-radius:4px; font-size:0.75rem; }
.badge-sent     { background:#1c1917; color:#fdba74; padding:2px 8px; border-radius:4px; font-size:0.75rem; }

div[data-testid="stDecoration"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar nav ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# ⚡ BAESS Leads")
    st.markdown("---")
    page = st.radio(
        "Navigation",
        ["📊 Dashboard", "🔍 Discover", "👤 Enrich", "✉️ DM Generator"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.caption("v1.0 · Powered by BAESS.APP")

# ── Route ──────────────────────────────────────────────────────────────────────
if page == "📊 Dashboard":
    from pages import dashboard; dashboard.render()
elif page == "🔍 Discover":
    from pages import discover; discover.render()
elif page == "👤 Enrich":
    from pages import enrich; enrich.render()
elif page == "✉️ DM Generator":
    from pages import dm_generator; dm_generator.render()
