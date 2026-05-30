"""
db.py — Neon PostgreSQL connection + schema bootstrap
All modules import from here: get_conn(), get_df(), upsert_lead(), etc.
"""

import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
from datetime import datetime, timezone
import uuid


# ── Connection ─────────────────────────────────────────────────────────────────
@st.cache_resource
def get_conn():
    return psycopg2.connect(
        st.secrets["NEON_DATABASE_URL"],
        sslmode="require",
        cursor_factory=psycopg2.extras.RealDictCursor
    )


def run(sql: str, params=None, fetch=False):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            if fetch:
                return cur.fetchall()
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e


# ── Bootstrap schema ───────────────────────────────────────────────────────────
def init_db():
    run("""
    CREATE TABLE IF NOT EXISTS leads (
        id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
        linkedin_url    TEXT UNIQUE NOT NULL,
        query_source    TEXT,
        discovered_at   TIMESTAMPTZ DEFAULT NOW(),

        -- Module 2: enrichment
        name            TEXT,
        title           TEXT,
        company         TEXT,
        location        TEXT,
        about           TEXT,
        enriched_at     TIMESTAMPTZ,
        enrich_status   TEXT DEFAULT 'pending',   -- pending | enriched | failed

        -- Module 3: DM
        dm_message      TEXT,
        dm_generated_at TIMESTAMPTZ,
        dm_sent         BOOLEAN DEFAULT FALSE,
        dm_sent_at      TIMESTAMPTZ,

        -- Meta
        notes           TEXT,
        tags            TEXT[]
    );
    """)


# ── Helpers ────────────────────────────────────────────────────────────────────
def insert_leads(urls: list[str], query_source: str) -> dict:
    """Bulk-insert new URLs, skip duplicates. Returns counts."""
    inserted = 0
    skipped = 0
    for url in urls:
        try:
            run("""
                INSERT INTO leads (id, linkedin_url, query_source, discovered_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (linkedin_url) DO NOTHING
            """, (str(uuid.uuid4()), url.strip(), query_source, datetime.now(timezone.utc)))
            inserted += 1
        except Exception:
            skipped += 1
    return {"inserted": inserted, "skipped": skipped}


def get_leads_df(status_filter: str = None) -> pd.DataFrame:
    """Fetch all leads as DataFrame, optionally filtered by enrich_status."""
    if status_filter and status_filter != "All":
        rows = run(
            "SELECT * FROM leads WHERE enrich_status = %s ORDER BY discovered_at DESC",
            (status_filter,), fetch=True
        )
    else:
        rows = run("SELECT * FROM leads ORDER BY discovered_at DESC", fetch=True)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def update_lead_enrichment(lead_id: str, data: dict):
    run("""
        UPDATE leads SET
            name          = %s,
            title         = %s,
            company       = %s,
            location      = %s,
            about         = %s,
            enriched_at   = %s,
            enrich_status = 'enriched'
        WHERE id = %s
    """, (
        data.get("name"), data.get("title"), data.get("company"),
        data.get("location"), data.get("about"),
        datetime.now(timezone.utc), lead_id
    ))


def update_lead_dm(lead_id: str, dm_text: str):
    run("""
        UPDATE leads SET
            dm_message      = %s,
            dm_generated_at = %s,
            enrich_status   = 'dm_ready'
        WHERE id = %s
    """, (dm_text, datetime.now(timezone.utc), lead_id))


def mark_dm_sent(lead_id: str):
    run("""
        UPDATE leads SET dm_sent = TRUE, dm_sent_at = %s WHERE id = %s
    """, (datetime.now(timezone.utc), lead_id))


def delete_lead(lead_id: str):
    run("DELETE FROM leads WHERE id = %s", (lead_id,))


def get_stats() -> dict:
    rows = run("""
        SELECT
            COUNT(*)                                        AS total,
            COUNT(*) FILTER (WHERE enrich_status='pending')    AS pending,
            COUNT(*) FILTER (WHERE enrich_status='enriched')   AS enriched,
            COUNT(*) FILTER (WHERE enrich_status='dm_ready')   AS dm_ready,
            COUNT(*) FILTER (WHERE dm_sent = TRUE)             AS sent
        FROM leads
    """, fetch=True)
    return dict(rows[0]) if rows else {}
