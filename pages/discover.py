import streamlit as st
import re
import time
import random
import requests
from db import insert_leads, get_leads_df

ROLE_TEMPLATES = {
    "C-Suite / Directors": [
        'site:linkedin.com/in "solar" ("Director" OR "VP" OR "Head") "{geo}"',
        'site:linkedin.com/in "renewable energy" ("CTO" OR "CEO" OR "COO") "{geo}"',
        'site:linkedin.com/in "solar EPC" ("Managing Director" OR "Director") "{geo}"',
    ],
    "Project / Engineering Managers": [
        'site:linkedin.com/in "solar" ("Project Manager" OR "Engineering Manager") "{geo}"',
        'site:linkedin.com/in "PV" ("Senior Engineer" OR "Lead Engineer") "{geo}"',
        'site:linkedin.com/in "solar energy" ("Projects Head" OR "Technical Head") "{geo}"',
    ],
    "Procurement / Commercial": [
        'site:linkedin.com/in "solar" ("Procurement" OR "Commercial Manager") "{geo}"',
        'site:linkedin.com/in "renewable" ("Business Development" OR "Sales Director") "{geo}"',
    ],
    "C&I / BESS Focus": [
        'site:linkedin.com/in "C&I solar" "{geo}"',
        'site:linkedin.com/in "BESS" ("solar" OR "storage") "{geo}"',
        'site:linkedin.com/in "battery storage" "solar" "{geo}"',
    ],
}

GEO_OPTIONS = [
    "India", "UAE", "Oman", "Saudi Arabia", "Qatar", "Kuwait",
    "Singapore", "Malaysia", "Australia", "Indonesia", "Thailand",
    "Philippines", "Bangladesh", "Sri Lanka", "Kenya", "Nigeria",
    "South Africa", "Egypt", "Jordan", "Pakistan",
]

LINKEDIN_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/(in|company)/([A-Za-z0-9\-_%]+)/?$"
)


# ── Search backends ────────────────────────────────────────────────────────────

def extract_linkedin_urls_from_list(results: list) -> list:
    """Extract clean LinkedIn URLs from a list of result dicts."""
    urls = []
    seen = set()
    for r in results:
        for field in ["href", "url", "link"]:
            raw = r.get(field, "")
            if not raw:
                continue
            clean = raw.split("?")[0].rstrip("/")
            if LINKEDIN_RE.match(clean) and clean not in seen:
                seen.add(clean)
                urls.append(clean)
    return urls


def search_ddg(query: str, max_results: int = 10) -> list:
    """DuckDuckGo via ddgs library — free, no key needed."""
    from ddgs import DDGS
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    return extract_linkedin_urls_from_list(results)


def search_serpapi(query: str, api_key: str, max_results: int = 10) -> list:
    """
    SerpAPI Google Search — 100 free searches/month, deep LinkedIn index.
    Returns list of LinkedIn profile/company URLs.
    """
    urls = []
    seen = set()
    pages = max(1, max_results // 10)

    for page in range(pages):
        params = {
            "engine":  "google",
            "q":       query,
            "api_key": api_key,
            "num":     10,
            "start":   page * 10,
        }
        resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
        if resp.status_code != 200:
            raise Exception(f"SerpAPI error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()

        # Check for API-level errors
        if "error" in data:
            raise Exception(f"SerpAPI: {data['error']}")

        organic = data.get("organic_results", [])
        for item in organic:
            raw = item.get("link", "")
            clean = raw.split("?")[0].rstrip("/")
            if LINKEDIN_RE.match(clean) and clean not in seen:
                seen.add(clean)
                urls.append(clean)

        # Polite delay between pages
        if page < pages - 1:
            time.sleep(1.5)

    return urls


def run_search(engine: str, query: str, max_results: int, serpapi_key: str = "") -> list:
    """Router — calls the right backend based on selected engine."""
    if engine == "SerpAPI (Google)":
        if not serpapi_key:
            raise Exception("SerpAPI key not set. Add SERPAPI_KEY to Streamlit secrets.")
        return search_serpapi(query, serpapi_key, max_results)
    else:
        return search_ddg(query, max_results)


# ── Page ───────────────────────────────────────────────────────────────────────

def render():
    st.markdown('<p class="section-header">🔍 Lead Discovery</p>', unsafe_allow_html=True)

    # ── Engine selector ────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Search Engine</p>', unsafe_allow_html=True)

    ec1, ec2 = st.columns([2, 3])
    with ec1:
        engine = st.radio(
            "Search engine",
            ["DuckDuckGo (free)", "SerpAPI (Google)"],
            label_visibility="collapsed",
            horizontal=True,
        )

    with ec2:
        if engine == "DuckDuckGo (free)":
            st.success("✅ No API key needed — ready to use")
        else:
            # Check if key exists in secrets
            serp_key = st.secrets.get("SERPAPI_KEY", "")
            if serp_key:
                st.success("✅ SerpAPI key found in secrets")
            else:
                serp_key = st.text_input(
                    "SerpAPI Key",
                    type="password",
                    placeholder="Paste your SerpAPI key (serpapi.com → free tier: 100/month)",
                    label_visibility="collapsed",
                )
                st.caption("Get free key at [serpapi.com](https://serpapi.com) · 100 searches/month free")

    # Comparison callout
    with st.expander("📊 DDG vs SerpAPI — which should I use?"):
        st.markdown("""
| | DuckDuckGo | SerpAPI |
|---|---|---|
| Cost | Free, unlimited | 100/month free, $50/month for 5000 |
| LinkedIn index depth | ~30–40% of Google | Full Google index |
| Results per query | 5–15 typically | 10–40 typically |
| Speed | Slower (needs delays) | Fast |
| Reliability on cloud | Throttled sometimes | Consistent |
| **Verdict** | Good for testing | Better for production |
        """)

    st.markdown("---")

    # ── Query builder ──────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Build Your Search</p>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🎯 ICP Template Builder", "✏️ Custom Query"])

    queries     = []
    max_results = 10

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            role_cat = st.selectbox("Role Category", list(ROLE_TEMPLATES.keys()))
        with col2:
            geos = st.multiselect("Geographies", GEO_OPTIONS, default=["India", "UAE"])

        max_results = st.slider("Results per query", 5, 30, 10, step=5)

        templates = ROLE_TEMPLATES[role_cat]
        for geo in geos:
            for tmpl in templates:
                queries.append(tmpl.replace("{geo}", geo))

        with st.expander(f"Preview {len(queries)} queries to run"):
            for q in queries:
                st.code(q, language="text")

        if engine == "DuckDuckGo (free)":
            est_low  = len(queries) * 3
            est_high = len(queries) * 6
            st.info(f"🕐 Estimated time: ~{est_low}–{est_high}s (DDG needs polite delays)")
        else:
            st.info(f"🕐 Estimated time: ~{len(queries) * 2}–{len(queries) * 4}s")

    with tab2:
        custom_q = st.text_area(
            "Enter queries (one per line)",
            placeholder='site:linkedin.com/in "solar" "Project Manager" "India"',
            height=120,
            label_visibility="collapsed",
        )
        max_results_c = st.slider("Results per query", 5, 30, 10, step=5, key="max_c")
        if custom_q.strip():
            queries     = [l.strip() for l in custom_q.strip().splitlines() if l.strip()]
            max_results = max_results_c

    st.markdown("---")

    existing_df   = get_leads_df()
    existing_urls = set(existing_df["linkedin_url"].tolist()) if not existing_df.empty else set()
    st.caption(f"📦 {len(existing_urls)} URLs already in DB — duplicates skipped automatically.")

    # ── Run ────────────────────────────────────────────────────────────────────
    if st.button("🚀 Run Discovery", use_container_width=True):
        if not queries:
            st.warning("No queries to run.")
            return

        # Validate SerpAPI key if selected
        active_serp_key = ""
        if engine == "SerpAPI (Google)":
            active_serp_key = st.secrets.get("SERPAPI_KEY", "") or serp_key
            if not active_serp_key:
                st.error("SerpAPI key is required. Enter it above or add SERPAPI_KEY to Streamlit secrets.")
                return

        total_found = []
        total_new   = []
        progress    = st.progress(0)
        status_box  = st.empty()

        for qi, query in enumerate(queries):
            progress.progress(qi / len(queries))
            status_box.info(f"[{engine}] Query {qi+1}/{len(queries)} — `{query[:85]}`")

            try:
                urls     = run_search(engine, query, max_results, active_serp_key)
                total_found.extend(urls)

                new_urls = [u for u in urls if u not in existing_urls]
                total_new.extend(new_urls)

                if new_urls:
                    insert_leads(new_urls, query_source=f"[{engine}] {query}")
                    existing_urls.update(new_urls)

                # Delay between queries
                if qi < len(queries) - 1:
                    delay = random.uniform(2.0, 4.0) if engine == "DuckDuckGo (free)" else 1.0
                    time.sleep(delay)

            except Exception as e:
                st.warning(f"Query {qi+1} failed: {e}")
                continue

        progress.progress(1.0)
        status_box.empty()

        unique_new = sorted(set(total_new))
        st.success(f"✅ Done — {len(unique_new)} new leads added from {len(set(total_found))} URLs found.")

        if unique_new:
            st.markdown('<p class="section-header">New URLs this run</p>', unsafe_allow_html=True)
            for u in unique_new:
                st.markdown(f"- [{u}]({u})")
