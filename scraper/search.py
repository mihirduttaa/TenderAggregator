import psycopg2
from sentence_transformers import SentenceTransformer

DB_CONFIG = {
    "dbname": "tenderaggregator",
    "user": "",
    "password": "",
    "host": "localhost",
    "port": 5432,
}

MODEL_NAME = "all-MiniLM-L6-v2"

print("Loading model...")
model = SentenceTransformer(MODEL_NAME)
print("Model ready.\n")


def semantic_search(query: str, top_k: int = 10, filters: dict = {}):
    query_embedding = model.encode(query).tolist()

    conn = psycopg2.connect(**DB_CONFIG)

    conditions = [
        "embedding IS NOT NULL",
        "LENGTH(title) > 10",
        "title ~ '[a-zA-Z]'",
    ]
    filter_params = []

    if filters.get("work_category"):
        conditions.append("work_category = %s")
        filter_params.append(filters["work_category"])

    if filters.get("location"):
        conditions.append("location ILIKE %s")
        filter_params.append(f"%{filters['location']}%")

    if filters.get("max_emd"):
        conditions.append("emd_amount <= %s")
        filter_params.append(filters["max_emd"])

    where_clause = " AND ".join(conditions)

    sql = f"""
        SELECT
            tender_id,
            title,
            work_category,
            department,
            location,
            estimated_value,
            emd_amount,
            submission_deadline,
            1 - (embedding <=> %s::vector) AS similarity
        FROM tenders
        WHERE {where_clause}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """

    # Order: first embedding (for SELECT), then filters, then embedding again (for ORDER BY), then limit
    final_params = [query_embedding] + filter_params + [query_embedding, top_k]

    with conn.cursor() as cur:
        cur.execute(sql, final_params)
        results = cur.fetchall()
        columns = [desc[0] for desc in cur.description]

    conn.close()
    return [dict(zip(columns, row)) for row in results]


if __name__ == "__main__":
    queries = [
        ("road construction Bhopal",    {}),
        ("water pipeline repair",        {}),
        ("school building construction", {}),
        ("medical equipment hospital",   {}),
        ("civil work only",              {"work_category": "Civil Works"}),
        ("construction under 50000 EMD", {"max_emd": 50000}),
    ]

    for query, filters in queries:
        print(f"Query: '{query}' | Filters: {filters}")
        results = semantic_search(query, top_k=3, filters=filters)
        if not results:
            print("  No results found.")
        for r in results:
            print(f"  [{r['work_category']}] {r['title'][:70]}")
            print(f"    Score: {r['similarity']:.3f} | EMD: {r['emd_amount']} | Location: {r['location']}")
        print()