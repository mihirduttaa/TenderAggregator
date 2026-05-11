"""Database utilities for PostgreSQL + pgvector."""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = (
    f"postgresql+psycopg2://"
    f"{os.getenv('DB_USER', '')}:{os.getenv('DB_PASSWORD', '')}@"
    f"{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', 5432)}/"
    f"{os.getenv('DB_NAME', 'tenderaggregator')}"
)

engine = create_engine(DATABASE_URL, poolclass=NullPool, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Load model once at module level — no API key needed
print("Loading embedding model...")
from sentence_transformers import SentenceTransformer
_model = SentenceTransformer("all-MiniLM-L6-v2")
print("Embedding model ready.")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def vector_search(db: Session, query: str, limit: int = 50) -> list[dict]:
    try:
        embedding = _model.encode(query).tolist()
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        sql = f"""
            SELECT
                id, tender_id, title, reference_no, department,
                work_category, estimated_value, published_date,
                submission_deadline, opening_date, tender_url,
                location, emd_amount, product_category,
                1 - (embedding <=> '{embedding_str}'::vector) AS similarity
            FROM tenders
            WHERE embedding IS NOT NULL
              AND LENGTH(title) > 15
              AND title ~ '[a-zA-Z]'
            ORDER BY embedding <=> '{embedding_str}'::vector
            LIMIT {limit}
        """

        result = db.execute(text(sql))
        return [dict(row._mapping) for row in result.fetchall()]

    except Exception as e:
        print(f"Vector search error: {e}")
        return []
    try:
        embedding = _model.encode(query).tolist()
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        sql = f"""
            SELECT
                id, tender_id, title, reference_no, department,
                work_category, estimated_value, published_date,
                closing_date, opening_date, tender_url,
                location, emd_amount, product_category,
                1 - (embedding <=> '{embedding_str}'::vector) AS similarity
            FROM tenders
            WHERE embedding IS NOT NULL
              AND LENGTH(title) > 15
              AND title ~ '[a-zA-Z]'
            ORDER BY embedding <=> '{embedding_str}'::vector
            LIMIT {limit}
        """

        result = db.execute(text(sql))
        return [dict(row._mapping) for row in result.fetchall()]

    except Exception as e:
        print(f"Vector search error: {e}")
        return []
    """Semantic search using pgvector + local sentence-transformers."""
    try:
        embedding = _model.encode(query).tolist()
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        result = db.execute(
            text("""
                SELECT
                    id, tender_id, title, reference_no, department,
                    work_category, estimated_value, published_date,
                    closing_date, opening_date, tender_url,
                    location, emd_amount, product_category,
                    1 - (embedding <=> :embedding::vector) AS similarity
                FROM tenders
                WHERE embedding IS NOT NULL
                  AND LENGTH(title) > 15
                  AND title ~ '[a-zA-Z]'
                ORDER BY embedding <=> :embedding::vector
                LIMIT :limit
            """),
            {"embedding": embedding_str, "limit": limit}
        )

        return [dict(row._mapping) for row in result.fetchall()]

    except Exception as e:
        print(f"Vector search error: {e}")
        return []
    """Semantic search using pgvector + local sentence-transformers."""
    try:
        embedding = _model.encode(query).tolist()

        result = db.execute(
            text("""
                SELECT
                    id, tender_id, title, reference_no, department,
                    work_category, estimated_value, published_date,
                    closing_date, opening_date, tender_url,
                    location, emd_amount, product_category,
                    1 - (embedding <=> :embedding::vector) AS similarity
                FROM tenders
                WHERE embedding IS NOT NULL
                  AND LENGTH(title) > 15
                  AND title ~ '[a-zA-Z]'
                ORDER BY embedding <=> :embedding::vector
                LIMIT :limit
            """),
            {"embedding": str(embedding), "limit": limit}
        )

        return [dict(row._mapping) for row in result.fetchall()]

    except Exception as e:
        print(f"Vector search error: {e}")
        return []