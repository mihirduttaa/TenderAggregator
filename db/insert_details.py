import json
import logging
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "dbname": "tenderaggregator",
    "user": "",
    "password": "",
    "host": "localhost",
    "port": 5432,
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def parse_datetime(text: str):
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


def insert_details(conn, details: list[dict]):
    updated = 0
    skipped = 0

    with conn.cursor() as cur:
        for d in details:
            tender_id = d.get("tender_id", "").strip()
            if not tender_id:
                skipped += 1
                continue

            cur.execute("""
                UPDATE tenders SET
                    tender_type           = %s,
                    form_of_contract      = %s,
                    tender_category       = %s,
                    product_category      = %s,
                    sub_category          = %s,
                    work_description      = %s,
                    location              = %s,
                    pincode               = %s,
                    period_of_work        = %s,
                    bid_validity_days     = %s,
                    tender_fee            = %s,
                    emd_amount            = %s,
                    bid_submission_start  = %s,
                    bid_submission_end    = %s,
                    doc_download_start    = %s,
                    doc_download_end      = %s,
                    nit_documents         = %s,
                    work_documents        = %s,
                    inviting_authority    = %s,
                    updated_at            = NOW()
                WHERE tender_id = %s
            """, (
                d.get("tender_type"),
                d.get("form_of_contract"),
                d.get("tender_category"),
                d.get("product_category"),
                d.get("sub_category"),
                d.get("work_description"),
                d.get("location"),
                d.get("pincode"),
                d.get("period_of_work"),
                d.get("bid_validity_days"),
                d.get("tender_fee"),
                d.get("emd_amount"),
                parse_datetime(d.get("bid_submission_start")),
                parse_datetime(d.get("bid_submission_end")),
                parse_datetime(d.get("doc_download_start")),
                parse_datetime(d.get("doc_download_end")),
                json.dumps(d.get("nit_documents", [])),
                json.dumps(d.get("work_documents", [])),
                json.dumps({
                    "name": d.get("inviting_authority_name"),
                    "address": d.get("inviting_authority_address"),
                }),
                tender_id,
            ))
            updated += 1

    conn.commit()
    logger.info(f"Updated: {updated} | Skipped (no tender_id): {skipped}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    with open("tenders_detail.json", "r", encoding="utf-8") as f:
        details = json.load(f)

    logger.info(f"Loaded {len(details)} detail records.")
    conn = get_connection()
    insert_details(conn, details)
    conn.close()
    logger.info("Done.")