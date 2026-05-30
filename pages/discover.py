import streamlit as st
import requests
import re
from db import insert_leads, get_leads_df

# ── Pre-built ICP query templates for solar EPC ────────────────────────────────
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


def google_cse_search(api_key: str, cse_id: str, query: str, start: int = 1) -> list[str]:
    """Call Google Custom Search API, return list of LinkedIn profile URLs."""
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key":   api_key,
        "cx":    cse_id,
        "q":     query,
        "start": start,
        "num":   10,
    }
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code != 200:
        raise Exception(f"Google API error {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    items = data.get("items", [])
    urls = []
    for item in items:
        link = item.get("link", "")
        # only keep actual profile/company URLs, not feed/posts/etc
        if re.match(r"https?://(www\.)?linkedin\.com/(in|company)/[^/?#]+/?$", link):
            urls.append(link)
    return urls


def render():
    st.markdown('<p class="section-header">🔍 Lead Discovery</p>', unsafe_allow_html=True)
    st.caption("Uses Google Custom Search to find LinkedIn URLs matching your ICP — zero LinkedIn account risk.")

    # ── API keys from secrets ──────────────────────────────────────────────────
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
        cse_id  = st.secrets["GOOGLE_CSE_ID"]
    except KeyError:
        st.error("Missing GOOGLE_API_KEY or GOOGLE_CSE_ID in .streamlit/secrets.toml")
        return

    # ── Query builder ──────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Build Your Search</p>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🎯 ICP Template Builder", "✏️ Custom Query"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            role_cat = st.selectbox("Role Category", list(ROLE_TEMPLATES.keys()))
        with col2:
            geos = st.multiselect("Geographies", GEO_OPTIONS,
                                  default=["India", "UAE"])

        pages = st.slider("Pages per query (10 results each)", 1, 5, 2)

        # Build query list
        queries = []
        templates = ROLE_TEMPLATES[role_cat]
        for geo in geos:
            for tmpl in templates:
                queries.append(tmpl.replace("{geo}", geo))

        with st.expander(f"Preview {len(queries)} queries to run"):
            for q in queries:
                st.code(q, language="text")

    with tab2:
        custom_q = st.text_area(
            "Enter queries (one per line)",
            placeholder='site:linkedin.com/in "solar" "Project Manager" "India"',
            height=120
        )
        pages_c = st.slider("Pages per query", 1, 5, 2, key="pages_c")
        if custom_q.strip():
            queries = [l.strip() for l in custom_q.strip().splitlines() if l.strip()]
            pages   = pages_c

    st.markdown("---")

    # ── Existing URLs for dedup ────────────────────────────────────────────────
    existing_df  = get_leads_df()
    existing_urls = set(existing_df["linkedin_url"].tolist()) if not existing_df.empty else set()
    st.caption(f"📦 {len(existing_urls)} URLs already in database — duplicates will be skipped automatically.")

    # ── Run ────────────────────────────────────────────────────────────────────
    if st.button("🚀 Run Discovery", use_container_width=True):
        if not queries:
            st.warning("No queries to run.")
            return

        total_found   = []
        total_new     = []
        progress      = st.progress(0)
        status_box    = st.empty()
        results_box   = st.empty()

        total_ops = len(queries) * pages

        for qi, query in enumerate(queries):
            for page in range(pages):
                op_num = qi * pages + page
                progress.progress(op_num / total_ops)
                status_box.info(f"Query {qi+1}/{len(queries)}, page {page+1} — `{query[:80]}…`")

                try:
                    urls = google_cse_search(api_key, cse_id, query, start=page*10+1)
                    total_found.extend(urls)

                    new_urls = [u for u in urls if u not in existing_urls]
                    total_new.extend(new_urls)

                    if new_urls:
                        result = insert_leads(new_urls, query_source=query)
                        existing_urls.update(new_urls)

                except Exception as e:
                    st.warning(f"Query failed: {e}")
                    continue

        progress.progress(1.0)
        status_box.empty()

        # ── Summary ────────────────────────────────────────────────────────────
        st.success(f"✅ Done — {len(set(total_new))} new leads added from {len(set(total_found))} URLs found.")

        if total_new:
            st.markdown('<p class="section-header">New URLs discovered this run</p>',
                        unsafe_allow_html=True)
            for u in sorted(set(total_new)):
                st.markdown(f"- [{u}]({u})")
