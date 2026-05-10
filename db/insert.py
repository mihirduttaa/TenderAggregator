import json
import logging
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import re

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "dbname": "tenderaggregator",
    "user": "",        # leave empty — uses your Mac username by default
    "password": "",
    "host": "localhost",
    "port": 5432,
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def run_schema(conn):
    """Create tables if they don't exist."""
    with open("db/schema.sql", "r") as f:
        schema = f.read()
    with conn.cursor() as cur:
        cur.execute(schema)
    conn.commit()
    logger.info("Schema applied.")


def parse_datetime(text: str):
    """Parse portal date strings like '07-May-2026 12:10 PM'"""
    if not text:
        return None
    formats = [
        "%d-%b-%Y %I:%M %p",   # 07-May-2026 12:10 PM
        "%d-%b-%Y",             # 07-May-2026
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    logger.warning(f"Could not parse date: {text}")
    return None


def insert_tenders(conn, tenders: list[dict]):
    """Bulk insert tenders, skip duplicates."""
    rows = []
    for t in tenders:
        rows.append((
            t.get("tender_id") or None,
            t.get("title") or "",
            t.get("reference_no") or None,
            t.get("department") or None,
            None,                               # work_category — AI tagged later
            t.get("estimated_value") or None,
            None,                               # emd_amount — detail page later
            None,                               # document_url — detail page later
            parse_datetime(t.get("published_date")),
            parse_datetime(t.get("closing_date")),
            parse_datetime(t.get("opening_date")),
            t.get("tender_url") or None,
            "active",
            "mptenders",
            json.dumps(t),                      # raw_data — full record as backup
        ))

    sql = """
        INSERT INTO tenders (
            tender_id, title, reference_no, department,
            work_category, estimated_value, emd_amount, document_url,
            published_date, submission_deadline, opening_date,
            tender_url, status, source_portal, raw_data
        ) VALUES %s
        ON CONFLICT (tender_id) DO UPDATE SET
            title               = EXCLUDED.title,
            department          = EXCLUDED.department,
            estimated_value     = EXCLUDED.estimated_value,
            submission_deadline = EXCLUDED.submission_deadline,
            opening_date        = EXCLUDED.opening_date,
            updated_at          = NOW()
    """

    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()
    logger.info(f"Inserted/updated {len(rows)} tenders.")


def load_from_json(path: str = "tenders_raw.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    logger.info("Loading tenders from tenders_raw.json...")
    tenders = load_from_json()
    logger.info(f"Loaded {len(tenders)} tenders.")

    conn = get_connection()
    run_schema(conn)
    insert_tenders(conn, tenders)
    conn.close()

    logger.info("Done. All tenders inserted into PostgreSQL.")