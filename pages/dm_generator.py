import streamlit as st
import requests
from db import get_leads_df, update_lead_dm, mark_dm_sent


SYSTEM_PROMPT = """You are Amrit Mandal, founder of BAESS.APP — an AI-powered SaaS platform that automates 
BOQ generation, financial modeling, SLD/GA drawing production, and full proposal workflows for solar EPC companies.

You have 13+ years of solar PV and BESS engineering experience across India, GCC, and APAC markets.

Write a short, personalised LinkedIn DM to the lead provided. Rules:
- Max 5 sentences. Conversational, not salesy.
- Reference their specific role, company, or geography naturally.
- Connect their work to a specific pain point BAESS.APP solves (BOQ errors, slow proposals, manual SLD drawing).
- End with a soft, low-friction CTA (e.g. "worth a quick chat?" or "happy to show you a demo if useful").
- Never use generic openers like "Hope this message finds you well."
- Sound like a peer engineer reaching out, not a sales rep.
- Return ONLY the DM text, no subject line, no preamble."""


def generate_dm(profile: dict) -> str:
    """Call Claude API to generate a personalised DM for this profile."""
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except KeyError:
        raise Exception("Missing ANTHROPIC_API_KEY in secrets.toml")

    user_prompt = f"""Generate a LinkedIn DM for this lead:

Name: {profile.get('name', 'Unknown')}
Title: {profile.get('title', 'Unknown')}
Company: {profile.get('company', 'Unknown')}
Location: {profile.get('location', 'Unknown')}
About: {profile.get('about', 'Not available')}

Write the DM now:"""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        json={
            "model":      "claude-sonnet-4-20250514",
            "max_tokens": 300,
            "system":     SYSTEM_PROMPT,
            "messages":   [{"role": "user", "content": user_prompt}],
        },
        timeout=30,
    )

    if resp.status_code != 200:
        raise Exception(f"Claude API error {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    return data["content"][0]["text"].strip()


# ── Page ───────────────────────────────────────────────────────────────────────
def render():
    st.markdown('<p class="section-header">✉️ DM Generator</p>', unsafe_allow_html=True)
    st.caption("Generate a hyper-personalised outreach DM for each enriched lead using Claude AI.")

    # ── Load enriched leads ────────────────────────────────────────────────────
    df = get_leads_df(status_filter="enriched")

    if df.empty:
        st.info("No enriched leads yet. Run 👤 Enrich on your pending leads first.")
        return

    # ── Lead selector ──────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Select Lead</p>', unsafe_allow_html=True)

    display = df[["name", "title", "company", "location", "linkedin_url"]].copy()
    display.index = range(len(display))
    st.dataframe(display, use_container_width=True, hide_index=True)

    idx = st.number_input(
        f"Select row (0 – {len(df)-1})",
        min_value=0, max_value=len(df)-1, value=0, step=1
    )
    selected  = df.iloc[idx]
    lead_id   = selected["id"]
    lead_url  = selected["linkedin_url"]

    # Profile summary card
    st.markdown("---")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(f"**Name:** {selected.get('name') or '—'}")
        st.markdown(f"**Title:** {selected.get('title') or '—'}")
        st.markdown(f"**Company:** {selected.get('company') or '—'}")
        st.markdown(f"**Location:** {selected.get('location') or '—'}")
        st.markdown(f"[Open Profile ↗]({lead_url})")
    with c2:
        about = selected.get("about") or ""
        if about:
            st.markdown("**About:**")
            st.caption(about[:400] + ("…" if len(about) > 400 else ""))
        else:
            st.caption("No About section available for this profile.")

    st.markdown("---")

    # ── Generate DM ────────────────────────────────────────────────────────────
    existing_dm = selected.get("dm_message") or ""

    if existing_dm:
        st.markdown('<p class="section-header">Saved DM</p>', unsafe_allow_html=True)
        st.info(existing_dm)
        st.caption("A DM already exists for this lead. You can regenerate or edit below.")

    col_gen, col_regen = st.columns(2)
    with col_gen:
        gen_btn = st.button(
            "✨ Generate DM" if not existing_dm else "🔄 Regenerate DM",
            use_container_width=True
        )
    with col_regen:
        edit_mode = st.checkbox("✏️ Edit before saving")

    if gen_btn:
        with st.spinner("Generating personalised DM…"):
            try:
                dm_text = generate_dm(selected.to_dict())
                st.session_state[f"dm_{lead_id}"] = dm_text
            except Exception as e:
                st.error(f"Generation failed: {e}")
                return

    # Show editable or read-only DM
    dm_text = st.session_state.get(f"dm_{lead_id}", existing_dm)

    if dm_text:
        st.markdown('<p class="section-header">DM Preview</p>', unsafe_allow_html=True)

        if edit_mode:
            dm_text = st.text_area("Edit DM", value=dm_text, height=180,
                                   label_visibility="collapsed")
            st.session_state[f"dm_{lead_id}"] = dm_text
        else:
            st.success(dm_text)

        # ── Save / Mark sent ───────────────────────────────────────────────────
        st.markdown("---")
        sc1, sc2, sc3 = st.columns(3)

        with sc1:
            if st.button("💾 Save DM to DB", use_container_width=True):
                update_lead_dm(lead_id, dm_text)
                st.success("Saved!")
                st.rerun()

        with sc2:
            st.code(dm_text, language=None)   # easy copy

        with sc3:
            if st.button("✅ Mark as Sent", use_container_width=True):
                if not existing_dm:
                    update_lead_dm(lead_id, dm_text)
                mark_dm_sent(lead_id)
                st.success("Marked as sent!")
                st.rerun()

    # ── Bulk DM status overview ────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("📋 All DM-ready leads"):
        dm_df = get_leads_df(status_filter="dm_ready")
        if not dm_df.empty:
            st.dataframe(
                dm_df[["name", "title", "company", "dm_sent", "dm_generated_at"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.caption("No DM-ready leads yet.")
