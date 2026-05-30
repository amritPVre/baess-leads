import streamlit as st
import time
import random
from db import get_leads_df, update_lead_enrichment

# ── Selenium scraper ───────────────────────────────────────────────────────────
def scrape_profile(url: str, li_email: str, li_password: str) -> dict:
    """
    Opens LinkedIn profile URL in a real browser session.
    Reads publicly visible text fields only.
    Returns dict of profile fields.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        raise ImportError("selenium not installed. Run: pip install selenium")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")
    # Randomise user-agent to reduce bot signals
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
    ]
    options.add_argument(f"user-agent={random.choice(user_agents)}")

    driver = webdriver.Chrome(options=options)
    wait   = WebDriverWait(driver, 15)
    data   = {}

    try:
        # ── Login ──────────────────────────────────────────────────────────────
        driver.get("https://www.linkedin.com/login")
        wait.until(EC.presence_of_element_located((By.ID, "username")))
        driver.find_element(By.ID, "username").send_keys(li_email)
        driver.find_element(By.ID, "password").send_keys(li_password)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # Wait for feed to confirm login
        wait.until(EC.url_contains("feed"))
        time.sleep(random.uniform(2, 4))

        # ── Visit profile ──────────────────────────────────────────────────────
        driver.get(url)
        time.sleep(random.uniform(3, 6))   # human-like delay

        def safe_text(selector, by=By.CSS_SELECTOR, default=""):
            try:
                return driver.find_element(by, selector).text.strip()
            except Exception:
                return default

        # Name
        data["name"] = safe_text("h1.text-heading-xlarge")

        # Title (headline)
        data["title"] = safe_text("div.text-body-medium.break-words")

        # Location
        data["location"] = safe_text("span.text-body-small.inline.t-black--light.break-words")

        # Company (from experience section top entry)
        try:
            exp_items = driver.find_elements(
                By.CSS_SELECTOR, "li.artdeco-list__item.pvs-list__item--line-separated"
            )
            for item in exp_items[:3]:
                text = item.text.strip()
                if text:
                    # First experience entry typically has company name on 2nd line
                    lines = [l.strip() for l in text.splitlines() if l.strip()]
                    if len(lines) >= 2:
                        data["company"] = lines[1]
                        break
        except Exception:
            data["company"] = ""

        # About section
        try:
            about_el = driver.find_element(
                By.CSS_SELECTOR, "div[data-generated-suggestion-target] span[aria-hidden='true']"
            )
            data["about"] = about_el.text.strip()[:1000]
        except Exception:
            data["about"] = ""

    finally:
        driver.quit()

    return data


# ── Page ───────────────────────────────────────────────────────────────────────
def render():
    st.markdown('<p class="section-header">👤 Profile Enrichment</p>', unsafe_allow_html=True)
    st.caption("Visit each lead's LinkedIn profile and extract key details one by one.")

    # ── LinkedIn credentials (session only, never stored) ──────────────────────
    with st.expander("🔐 LinkedIn Credentials (not saved to DB)", expanded=True):
        st.warning("Use a secondary LinkedIn account, not your main profile.")
        col1, col2 = st.columns(2)
        with col1:
            li_email = st.text_input("LinkedIn Email", type="default",
                                     placeholder="scraper@email.com")
        with col2:
            li_password = st.text_input("LinkedIn Password", type="password")

    st.markdown("---")

    # ── Pick a lead to enrich ──────────────────────────────────────────────────
    st.markdown('<p class="section-header">Select Lead</p>', unsafe_allow_html=True)

    df = get_leads_df(status_filter="pending")

    if df.empty:
        st.info("No pending leads. Run 🔍 Discover first, or all leads are already enriched.")
        return

    # Show pending leads table
    display = df[["linkedin_url", "query_source", "discovered_at"]].copy()
    display.index = range(len(display))
    st.dataframe(display, use_container_width=True, hide_index=True)

    # Select by index
    idx = st.number_input(
        f"Select row to enrich (0 – {len(df)-1})",
        min_value=0, max_value=len(df)-1, value=0, step=1
    )
    selected = df.iloc[idx]
    target_url = selected["linkedin_url"]
    lead_id    = selected["id"]

    st.markdown(f"**Selected:** [{target_url}]({target_url})")

    # ── Manual override option ─────────────────────────────────────────────────
    st.markdown("---")
    mode = st.radio(
        "Enrichment mode",
        ["🤖 Auto (Selenium)", "✍️ Manual entry"],
        horizontal=True
    )

    if mode == "✍️ Manual entry":
        st.caption("Paste details from the profile yourself.")
        with st.form("manual_enrich"):
            name     = st.text_input("Full Name")
            title    = st.text_input("Headline / Title")
            company  = st.text_input("Current Company")
            location = st.text_input("Location")
            about    = st.text_area("About / Summary", height=150)
            submitted = st.form_submit_button("💾 Save to DB")

        if submitted:
            update_lead_enrichment(lead_id, {
                "name": name, "title": title,
                "company": company, "location": location, "about": about
            })
            st.success(f"✅ Enriched: {name} @ {company}")
            st.rerun()

    else:  # Auto Selenium
        if not li_email or not li_password:
            st.warning("Enter LinkedIn credentials above to use auto mode.")
            return

        if st.button("🚀 Scrape this profile", use_container_width=True):
            with st.spinner(f"Opening {target_url} …"):
                try:
                    data = scrape_profile(target_url, li_email, li_password)
                    update_lead_enrichment(lead_id, data)

                    st.success("✅ Profile enriched!")
                    st.markdown(f"""
                    | Field | Value |
                    |---|---|
                    | Name | {data.get('name','—')} |
                    | Title | {data.get('title','—')} |
                    | Company | {data.get('company','—')} |
                    | Location | {data.get('location','—')} |
                    """)
                    if data.get("about"):
                        with st.expander("About"):
                            st.write(data["about"])

                    time.sleep(1)
                    st.rerun()

                except ImportError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Scrape failed: {e}")
                    st.caption("LinkedIn may have challenged the login. Try manual entry for this profile.")
