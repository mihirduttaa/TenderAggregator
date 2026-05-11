import logging
import psycopg2
import numpy as np
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "dbname": "tenderaggregator",
    "user": "",
    "password": "",
    "host": "localhost",
    "port": 5432,
}

# Runs locally, no API needed, 384-dimensional embeddings
MODEL_NAME = "all-MiniLM-L6-v2"


def build_text(row: dict) -> str:
    """Combine fields into one searchable string."""
    parts = [
        row.get("title") or "",
        row.get("work_description") or "",
        row.get("product_category") or "",
        row.get("work_category") or "",
        row.get("department") or "",
        row.get("location") or "",
    ]
    return " ".join(p for p in parts if p).strip()


def generate_embeddings():
    print("Loading model (first run downloads ~90MB)...")
    model = SentenceTransformer(MODEL_NAME)
    print("Model loaded.")

    conn = psycopg2.connect(**DB_CONFIG)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title, work_description, product_category,
                   work_category, department, location
            FROM tenders
            WHERE embedding IS NULL
            ORDER BY id
        """)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]

    print(f"Found {len(rows)} tenders to embed.")

    if not rows:
        print("All tenders already embedded.")
        conn.close()
        return

    # Convert to list of dicts
    records = [dict(zip(columns, row)) for row in rows]

    # Build text for each tender
    texts = [build_text(r) for r in records]
    ids = [r["id"] for r in records]

    # Generate embeddings in batches
    BATCH_SIZE = 64
    all_embeddings = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i+BATCH_SIZE]
        embeddings = model.encode(batch, show_progress_bar=False)
        all_embeddings.extend(embeddings)
        print(f"  Embedded {min(i+BATCH_SIZE, len(texts))}/{len(texts)}")

    # Insert into DB
    print("Saving embeddings to database...")
    with conn.cursor() as cur:
        for tid, embedding in zip(ids, all_embeddings):
            cur.execute(
                "UPDATE tenders SET embedding = %s WHERE id = %s",
                (embedding.tolist(), tid)
            )
    conn.commit()
    conn.close()
    print(f"Done. Embedded {len(all_embeddings)} tenders.")


if __name__ == "__main__":
    generate_embeddings()