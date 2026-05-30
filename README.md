# BAESS Leads — LinkedIn Lead Generation App

A Streamlit app for solar EPC lead generation with 3 modules:
- **Discover** — Google CSE dorking to find LinkedIn URLs (zero LinkedIn risk)
- **Enrich** — Visit each profile via Selenium and extract details
- **DM Generator** — Claude AI generates personalised outreach per profile

All data stored in Neon PostgreSQL.

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure secrets
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your actual keys
```

Required keys:
| Key | Where to get it |
|---|---|
| `GOOGLE_API_KEY` | console.cloud.google.com → Custom Search API |
| `GOOGLE_CSE_ID` | programmablesearchengine.google.com |
| `NEON_DATABASE_URL` | neon.tech → Project → Connection Details |
| `ANTHROPIC_API_KEY` | console.anthropic.com |

### 3. Chrome / ChromeDriver (for Enrich module)
The Selenium enrichment module requires Chrome + ChromeDriver.

**On Ubuntu/Debian:**
```bash
sudo apt-get install -y chromium-browser chromium-chromedriver
```

**On macOS:**
```bash
brew install --cask chromedriver
```

**On Windows:**
Download from https://chromedriver.chromium.org/downloads matching your Chrome version.

### 4. Run
```bash
streamlit run app.py
```

---

## Module Guide

### 🔍 Discover
- Select role category + geographies → app builds optimised `site:linkedin.com` queries
- Or enter custom queries manually
- Each run deduplicates against existing DB — only new URLs are saved
- Uses 100 free Google CSE queries/day

### 👤 Enrich
- Shows pending leads one at a time
- Auto mode: Selenium opens profile in headless Chrome, reads visible fields
- Manual mode: paste details yourself (safer, no Selenium needed)
- **Always use a secondary LinkedIn account** for Selenium — never your main profile
- Credentials are session-only, never stored in DB

### ✉️ DM Generator
- Loads enriched leads
- One click → Claude generates a personalised DM as Amrit Mandal / BAESS.APP
- Edit before saving if needed
- Save to DB + mark as sent when done

---

## Database Schema
Single `leads` table in Neon tracks the full pipeline:
```
discovered → pending → enriched → dm_ready → sent
```

---

## .gitignore
Add this to your `.gitignore`:
```
.streamlit/secrets.toml
__pycache__/
*.pyc
```
