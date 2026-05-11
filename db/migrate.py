"""
Migration script to load tender data from JSON files into PostgreSQL with pgvector embeddings.
Usage: python db/migrate.py
Generates embeddings using OpenAI API (requires OPENAI_API_KEY environment variable).
"""

import json
import os
import logging
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from pathlib import Path

import dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

dotenv.load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "tenderaggregator"),
    "user": os.getenv("DB_USER", ""),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
}

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = ROOT / "tenders_raw.json"
DETAIL_DATA_PATH = ROOT / "tenders_detail.json"


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def run_schema(conn):
    """Apply database schema."""
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    with open(schema_path, "r") as f:
        schema = f.read()
    with conn.cursor() as cur:
        cur.execute(schema)
    conn.commit()
    logger.info("Schema applied.")


def generate_embedding(text: str) -> list | None:
    """Generate embedding using OpenAI API."""
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set. Skipping embeddings.")
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000],  # Truncate to 8000 chars to avoid token limits
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None


def parse_datetime(text: str):
    """Parse portal date strings."""
    if not text or text.strip() in ["-", "NA", ""]:
        return None
    formats = [
        "%d-%b-%Y %I:%M %p",
        "%d-%b-%Y %I:%M:%S %p",
        "%d-%b-%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def load_json(path: Path) -> list:
    """Load JSON data file."""
    if not path.exists():
        logger.warning(f"File not found: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def insert_tenders(conn, raw_tenders: list[dict], detail_map: dict):
    """Bulk insert/upsert tenders with embeddings."""
    rows = []
    
    for t in raw_tenders:
        tender_id = t.get("tender_id") or ""
        if not tender_id:
            continue

        # Generate embedding from title + work_description
        text_for_embedding = f"{t.get('title', '')} {t.get('work_description', '')}".strip()
        embedding = generate_embedding(text_for_embedding) if text_for_embedding else None

        detail = detail_map.get(tender_id, {})

        rows.append((
            tender_id,
            t.get("title") or "",
            t.get("reference_no") or None,
            t.get("department") or None,
            None,  # work_category — LLM tagged later
            t.get("estimated_value") or None,
            detail.get("emd_amount") or None,
            None,  # document_url
            parse_datetime(t.get("published_date")),
            parse_datetime(t.get("closing_date")),
            parse_datetime(t.get("opening_date")),
            t.get("tender_url") or None,
            "active",
            "mptenders",
            json.dumps(t),
            embedding,  # pgvector embedding
            detail.get("tender_type") or None,
            detail.get("form_of_contract") or None,
            detail.get("tender_category") or None,
            detail.get("product_category") or None,
            detail.get("sub_category") or None,
            detail.get("work_description") or None,
            detail.get("location") or None,
            detail.get("pincode") or None,
            detail.get("period_of_work") or None,
            detail.get("bid_validity_days") or None,
            detail.get("tender_fee") or None,
            parse_datetime(detail.get("bid_submission_start")),
            parse_datetime(detail.get("bid_submission_end")),
            parse_datetime(detail.get("doc_download_start")),
            parse_datetime(detail.get("doc_download_end")),
            json.dumps(detail.get("nit_documents", [])),
            json.dumps(detail.get("work_documents", [])),
            json.dumps({
                "name": detail.get("inviting_authority_name"),
                "address": detail.get("inviting_authority_address"),
            }) if detail.get("inviting_authority_name") else None,
        ))

    sql = """
        INSERT INTO tenders (
            tender_id, title, reference_no, department,
            work_category, estimated_value, emd_amount, document_url,
            published_date, submission_deadline, opening_date,
            tender_url, status, source_portal, raw_data, embedding,
            tender_type, form_of_contract, tender_category, product_category, sub_category,
            work_description, location, pincode, period_of_work, bid_validity_days, tender_fee,
            bid_submission_start, bid_submission_end, doc_download_start, doc_download_end,
            nit_documents, work_documents, inviting_authority
        ) VALUES %s
        ON CONFLICT (tender_id) DO UPDATE SET
            title               = EXCLUDED.title,
            department          = EXCLUDED.department,
            estimated_value     = EXCLUDED.estimated_value,
            emd_amount          = EXCLUDED.emd_amount,
            submission_deadline = EXCLUDED.submission_deadline,
            opening_date        = EXCLUDED.opening_date,
            embedding           = EXCLUDED.embedding,
            work_description    = EXCLUDED.work_description,
            location            = EXCLUDED.location,
            tender_type         = EXCLUDED.tender_type,
            updated_at          = NOW()
    """

    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=100)
    conn.commit()
    logger.info(f"Inserted/updated {len(rows)} tenders.")


def main():
    logger.info("Starting migration...")
    
    # Load data
    logger.info("Loading raw tenders...")
    raw_tenders = load_json(RAW_DATA_PATH)
    
    logger.info("Loading tender details...")
    detail_records = load_json(DETAIL_DATA_PATH)
    detail_map = {d.get("tender_id"): d for d in detail_records if d.get("tender_id")}
    
    logger.info(f"Loaded {len(raw_tenders)} raw tenders and {len(detail_map)} detail records.")
    
    # Connect and migrate
    try:
        conn = get_connection()
        logger.info("Connected to PostgreSQL.")
        
        run_schema(conn)
        insert_tenders(conn, raw_tenders, detail_map)
        
        conn.close()
        logger.info("✅ Migration complete!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    main()
