import streamlit as st
import requests
import re
import time
import random
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

HEADERS_POOL = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36"},
]

LINKEDIN_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/(in|company)/([A-Za-z0-9\-_%]+)/?$"
)


def ddg_search(query: str, max_results: int = 10) -> list:
    """
    Search DuckDuckGo HTML endpoint and extract LinkedIn profile URLs.
    No API key needed. Returns list of URLs.
    """
    urls = []
    seen = set()

    # DuckDuckGo HTML search — paginate via 's' offset param
    for offset in range(0, max_results, 10):
        try:
            params = {
                "q":  query,
                "b":  "" if offset == 0 else str(offset),
                "kl": "us-en",
            }
            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params=params,
                headers=random.choice(HEADERS_POOL),
                timeout=15,
            )

            if resp.status_code != 200:
                break

            # Extract all href= links from result snippets
            raw_links = re.findall(r'href="(https?://[^"]+)"', resp.text)

            for link in raw_links:
                # Clean tracking redirects — DDG wraps links sometimes
                if "duckduckgo.com" in link:
                    continue
                # Normalise — strip query params and trailing slash variations
                clean = link.split("?")[0].rstrip("/")
                if LINKEDIN_RE.match(clean) and clean not in seen:
                    seen.add(clean)
                    urls.append(clean)

            # Polite delay between pages
            time.sleep(random.uniform(2.0, 4.0))

        except requests.RequestException:
            break

    return urls[:max_results]


def render():
    st.markdown('<p class="section-header">🔍 Lead Discovery</p>', unsafe_allow_html=True)
    st.caption("Uses DuckDuckGo to find LinkedIn URLs matching your ICP — no API key, no quota limits.")

    # ── Query builder ──────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Build Your Search</p>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🎯 ICP Template Builder", "✏️ Custom Query"])

    queries = []
    pages   = 1

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            role_cat = st.selectbox("Role Category", list(ROLE_TEMPLATES.keys()))
        with col2:
            geos = st.multiselect("Geographies", GEO_OPTIONS, default=["India", "UAE"])

        pages = st.slider("Results per query (10 = 1 page)", 10, 50, 10, step=10)

        templates = ROLE_TEMPLATES[role_cat]
        for geo in geos:
            for tmpl in templates:
                queries.append(tmpl.replace("{geo}", geo))

        with st.expander(f"Preview {len(queries)} queries to run"):
            for q in queries:
                st.code(q, language="text")

        st.info(
            f"🕐 Estimated time: ~{len(queries) * int(pages/10) * 3}–{len(queries) * int(pages/10) * 5}s "
            f"(DDG needs polite delays to avoid blocks)"
        )

    with tab2:
        custom_q = st.text_area(
            "Enter queries (one per line)",
            placeholder='site:linkedin.com/in "solar" "Project Manager" "India"',
            height=120,
            label_visibility="collapsed",
        )
        pages_c = st.slider("Results per query", 10, 50, 10, step=10, key="pages_c")
        if custom_q.strip():
            queries = [l.strip() for l in custom_q.strip().splitlines() if l.strip()]
            pages   = pages_c

    st.markdown("---")

    # ── Dedup against existing DB ──────────────────────────────────────────────
    existing_df   = get_leads_df()
    existing_urls = set(existing_df["linkedin_url"].tolist()) if not existing_df.empty else set()
    st.caption(f"📦 {len(existing_urls)} URLs already in DB — duplicates skipped automatically.")

    # ── Run ────────────────────────────────────────────────────────────────────
    if st.button("🚀 Run Discovery", use_container_width=True):
        if not queries:
            st.warning("No queries to run.")
            return

        total_found = []
        total_new   = []
        progress    = st.progress(0)
        status_box  = st.empty()
        total_ops   = len(queries)

        for qi, query in enumerate(queries):
            progress.progress(qi / total_ops)
            status_box.info(f"Searching {qi+1}/{len(queries)} — `{query[:90]}…`")

            try:
                urls     = ddg_search(query, max_results=pages)
                total_found.extend(urls)

                new_urls = [u for u in urls if u not in existing_urls]
                total_new.extend(new_urls)

                if new_urls:
                    insert_leads(new_urls, query_source=query)
                    existing_urls.update(new_urls)

                # Extra pause between queries so DDG doesn't rate-limit
                if qi < total_ops - 1:
                    time.sleep(random.uniform(3.0, 6.0))

            except Exception as e:
                st.warning(f"Query failed: {e}")
                continue

        progress.progress(1.0)
        status_box.empty()

        # ── Summary ────────────────────────────────────────────────────────────
        unique_new = sorted(set(total_new))
        st.success(f"✅ Done — {len(unique_new)} new leads added from {len(set(total_found))} URLs found.")

        if unique_new:
            st.markdown('<p class="section-header">New URLs this run</p>', unsafe_allow_html=True)
            for u in unique_new:
                st.markdown(f"- [{u}]({u})")
