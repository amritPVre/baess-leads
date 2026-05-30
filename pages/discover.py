import streamlit as st
import re
import time
import random
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


def extract_linkedin_urls(results: list) -> list:
    """Extract and clean LinkedIn profile/company URLs from ddgs results."""
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


def ddg_search(query: str, max_results: int = 10) -> list:
    """Search via duckduckgo_search library — handles bot detection properly."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return extract_linkedin_urls(results)
    except Exception as e:
        raise Exception(f"DDG search error: {e}")


def render():
    st.markdown('<p class="section-header">🔍 Lead Discovery</p>', unsafe_allow_html=True)
    st.caption("Uses DuckDuckGo to find LinkedIn URLs matching your ICP — no API key, no quota limits.")

    tab1, tab2 = st.tabs(["🎯 ICP Template Builder", "✏️ Custom Query"])

    queries = []
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

        est_low  = len(queries) * 3
        est_high = len(queries) * 6
        st.info(f"🕐 Estimated time: ~{est_low}–{est_high}s (includes polite delays between queries)")

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

    if st.button("🚀 Run Discovery", use_container_width=True):
        if not queries:
            st.warning("No queries to run.")
            return

        total_found = []
        total_new   = []
        progress    = st.progress(0)
        status_box  = st.empty()

        for qi, query in enumerate(queries):
            progress.progress(qi / len(queries))
            status_box.info(f"Searching {qi+1}/{len(queries)} — `{query[:90]}`")

            try:
                urls     = ddg_search(query, max_results=max_results)
                total_found.extend(urls)

                new_urls = [u for u in urls if u not in existing_urls]
                total_new.extend(new_urls)

                if new_urls:
                    insert_leads(new_urls, query_source=query)
                    existing_urls.update(new_urls)

                # Polite delay between queries
                if qi < len(queries) - 1:
                    time.sleep(random.uniform(2.0, 4.0))

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
