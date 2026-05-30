import streamlit as st
import pandas as pd
from db import init_db, get_stats, get_leads_df, delete_lead


def render():
    init_db()  # ensure schema exists on every cold start

    st.markdown('<p class="section-header">Pipeline Overview</p>', unsafe_allow_html=True)

    stats = get_stats()
    if not stats:
        st.info("No leads yet. Head to 🔍 Discover to start.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Leads",   stats.get("total", 0))
    c2.metric("Pending",       stats.get("pending", 0))
    c3.metric("Enriched",      stats.get("enriched", 0))
    c4.metric("DM Ready",      stats.get("dm_ready", 0))
    c5.metric("DM Sent",       stats.get("sent", 0))

    st.markdown("---")
    st.markdown('<p class="section-header">All Leads</p>', unsafe_allow_html=True)

    col_f, col_s = st.columns([2, 1])
    with col_f:
        status_filter = st.selectbox(
            "Filter by status",
            ["All", "pending", "enriched", "dm_ready"],
            label_visibility="collapsed"
        )
    with col_s:
        search = st.text_input("Search name / company", placeholder="Search…",
                               label_visibility="collapsed")

    df = get_leads_df(status_filter)

    if df.empty:
        st.info("No leads match this filter.")
        return

    # apply search
    if search:
        mask = (
            df.get("name", pd.Series(dtype=str)).fillna("").str.contains(search, case=False) |
            df.get("company", pd.Series(dtype=str)).fillna("").str.contains(search, case=False) |
            df.get("linkedin_url", pd.Series(dtype=str)).fillna("").str.contains(search, case=False)
        )
        df = df[mask]

    display_cols = ["linkedin_url", "name", "title", "company",
                    "location", "enrich_status", "dm_sent", "discovered_at"]
    display_cols = [c for c in display_cols if c in df.columns]

    st.dataframe(
        df[display_cols].rename(columns={
            "linkedin_url":   "URL",
            "name":           "Name",
            "title":          "Title",
            "company":        "Company",
            "location":       "Location",
            "enrich_status":  "Status",
            "dm_sent":        "DM Sent",
            "discovered_at":  "Discovered"
        }),
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")
    st.markdown('<p class="section-header">Export / Delete</p>', unsafe_allow_html=True)

    ec, dc = st.columns(2)
    with ec:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Export CSV", csv, "baess_leads.csv", "text/csv")

    with dc:
        with st.expander("🗑 Delete a lead"):
            del_url = st.text_input("Paste exact LinkedIn URL to delete")
            if st.button("Delete"):
                match = df[df["linkedin_url"] == del_url.strip()]
                if not match.empty:
                    delete_lead(match.iloc[0]["id"])
                    st.success("Deleted.")
                    st.rerun()
                else:
                    st.error("URL not found in current view.")
