import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from db.db import SessionLocal, vector_search

ROOT = Path(__file__).resolve().parent.parent

# Try to use PostgreSQL; fall back to JSON if unavailable
USE_POSTGRES = os.getenv("USE_POSTGRES", "true").lower() == "true"
RAW_DATA_PATH = ROOT / "tenders_raw.json"
DETAIL_DATA_PATH = ROOT / "tenders_detail.json"


class TenderSummary(BaseModel):
    id: Optional[int] = None
    title: str
    reference_no: Optional[str] = None
    tender_id: Optional[str] = None
    department: Optional[str] = None
    published_date: Optional[datetime] = None
    submission_deadline: Optional[datetime] = None
    opening_date: Optional[datetime] = None
    estimated_value: Optional[float] = None
    tender_url: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TenderDetail(BaseModel):
    tender_id: str
    organisation_chain: Optional[str] = None
    reference_no: Optional[str] = None
    tender_type: Optional[str] = None
    form_of_contract: Optional[str] = None
    tender_category: Optional[str] = None
    product_category: Optional[str] = None
    sub_category: Optional[str] = None
    work_description: Optional[str] = None
    location: Optional[str] = None
    pincode: Optional[str] = None
    period_of_work: Optional[str] = None
    bid_validity_days: Optional[str] = None
    tender_fee: Optional[float] = None
    emd_amount: Optional[float] = None
    emd_exemption: Optional[str] = None
    published_date: Optional[datetime] = None
    bid_opening_date: Optional[datetime] = None
    doc_download_start: Optional[datetime] = None
    doc_download_end: Optional[datetime] = None
    bid_submission_start: Optional[datetime] = None
    bid_submission_end: Optional[datetime] = None
    nit_documents: List[str] = Field(default_factory=list)
    work_documents: List[str] = Field(default_factory=list)
    inviting_authority_name: Optional[str] = None
    inviting_authority_address: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TenderRecord(TenderSummary):
    details: Optional[TenderDetail] = None


app = FastAPI(
    title="Tender Aggregator API",
    description="REST API with semantic search & vector embeddings for tender data.",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# Fallback JSON data (for non-PostgreSQL mode)
app.state.raw_tenders = []
app.state.detail_map = {}
app.state.tender_map = {}
app.state.postgres_available = False


@app.on_event("startup")
def startup_event():
    global USE_POSTGRES
    
    # Try PostgreSQL connection
    if USE_POSTGRES:
        try:
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
            app.state.postgres_available = True
            print("✅ PostgreSQL available — using database backend")
        except Exception as e:
            print(f"⚠️ PostgreSQL not available: {e}")
            print("Falling back to JSON data...")
            app.state.postgres_available = False
            USE_POSTGRES = False
    
    # Load fallback JSON data
    if not app.state.postgres_available:
        try:
            raw_tenders = load_json(RAW_DATA_PATH)
            detail_records = load_json(DETAIL_DATA_PATH)
            
            detail_map: Dict[str, Dict] = {
                record.get("tender_id"): record for record in detail_records if record.get("tender_id")
            }
            
            tender_map: Dict[str, Dict] = {}
            for tender in raw_tenders:
                tender_id = tender.get("tender_id")
                tender_map[tender_id] = {
                    **tender,
                    "details": detail_map.get(tender_id),
                }
            
            app.state.raw_tenders = raw_tenders
            app.state.detail_map = detail_map
            app.state.tender_map = tender_map
        except Exception as e:
            print(f"⚠️ Could not load JSON data: {e}")


@app.get("/", summary="API root")
def root(request: Request):
    accept_header = request.headers.get("accept", "")
    if accept_header.split(",")[0].strip().startswith("text/html"):
        html = """
        <!DOCTYPE html>
        <html lang=\"en\">
        <head>
          <meta charset=\"UTF-8\" />
          <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
          <title>Tender Aggregator API</title>
          <style>
            body { font-family: system-ui, sans-serif; margin: 0; padding: 40px; background: #f4f7fb; color: #1f2937; }
            main { max-width: 720px; margin: auto; background: white; border-radius: 24px; padding: 32px; box-shadow: 0 18px 48px rgba(15,23,42,0.12); }
            h1 { margin-top: 0; font-size: clamp(2rem, 2.5vw, 2.8rem); }
            p { line-height: 1.7; color: #475569; }
            .badge { display: inline-block; padding: 4px 10px; border-radius: 8px; background: #d1fae5; color: #065f46; font-size: 0.85rem; margin-bottom: 16px; }
            .links { display: grid; gap: 12px; margin-top: 24px; }
            .links a { display: inline-block; padding: 14px 18px; border-radius: 14px; text-decoration: none; color: white; background: #2563eb; }
            .links a.secondary { background: #334155; }
            .endpoints { margin-top: 24px; padding: 18px; border-radius: 16px; background: #f8fafc; color: #334155; }
            .endpoints code { display: block; margin: 8px 0; padding: 10px 12px; background: #e2e8f0; border-radius: 10px; }
          </style>
        </head>
        <body>
          <main>
            <h1>Tender Aggregator API</h1>
            <span class=\"badge\">✨ v0.2.0 — PostgreSQL + Vector Search</span>
            <p>Welcome to the Tender Aggregator backend. Use the buttons below to open the frontend UI or explore the OpenAPI docs.</p>
            <div class=\"links\">
              <a href=\"/ui\">Open Frontend UI</a>
              <a class=\"secondary\" href=\"/docs\">Open API Docs</a>
            </div>
            <div class=\"endpoints\">
              <strong>Available endpoints</strong>
              <code>/tenders</code>
              <code>/tenders/search (semantic)</code>
              <code>/tenders/{tender_id}</code>
              <code>/health</code>
              <code>/ui</code>
            </div>
          </main>
        </body>
        </html>
        """
        return HTMLResponse(content=html)

    return {
        "service": "Tender Aggregator API",
        "version": "0.2.0",
        "backend": "postgresql" if app.state.postgres_available else "json",
        "endpoints": [
            "/tenders",
            "/tenders/search",
            "/tenders/{tender_id}",
            "/health",
            "/ui",
        ],
    }


@app.get("/ui", response_class=HTMLResponse, summary="Frontend UI")
def frontend_ui():
    ui_path = ROOT / "frontend" / "index.html"
    if not ui_path.exists():
        raise HTTPException(status_code=404, detail="Frontend UI not found.")
    return FileResponse(ui_path)


@app.get("/health", summary="Health check")
def health():
    return {
        "status": "ok",
        "backend": "postgresql" if app.state.postgres_available else "json",
    }


@app.get("/tenders/search", response_model=List[TenderRecord], summary="Semantic search")
def semantic_search(
    q: str = Query(..., description="Search query (e.g., 'road construction Bhopal')"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Semantic similarity search using pgvector embeddings.
    Returns tenders most similar to your search query.
    """
    if not app.state.postgres_available:
        raise HTTPException(status_code=503, detail="Vector search requires PostgreSQL backend.")
    
    results = vector_search(db, q, limit)
    return results


@app.get("/tenders", response_model=List[TenderRecord], summary="List tender summaries")
def list_tenders(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Search by title, reference number, tender ID, or department."),
    department: Optional[str] = Query(None, description="Filter by department text."),
    tender_id: Optional[str] = Query(None, description="Return only the tender with this tender_id."),
    db: Session = Depends(get_db),
) -> List[TenderRecord]:
    """List tenders with filtering and search."""
    
    # Use PostgreSQL if available
    if app.state.postgres_available:
        conditions = ["status = 'active'"]
        params = {}
        
        if tender_id:
            conditions.append("tender_id = :tender_id")
            params["tender_id"] = tender_id
        
        if search:
            conditions.append("(title ILIKE :search OR reference_no ILIKE :search OR tender_id ILIKE :search OR department ILIKE :search)")
            params["search"] = f"%{search}%"
        
        if department:
            conditions.append("department ILIKE :department")
            params["department"] = f"%{department}%"
        
        query = text(f"""
            SELECT 
                id, tender_id, title, reference_no, department,
                estimated_value, published_date, submission_deadline, opening_date,
                tender_url, tender_type, form_of_contract, tender_category,
                product_category, sub_category, work_description, location,
                pincode, period_of_work, bid_validity_days, tender_fee,
                emd_amount, bid_submission_start, bid_submission_end,
                doc_download_start, doc_download_end, nit_documents, work_documents,
                inviting_authority
            FROM tenders
            WHERE {' AND '.join(conditions)}
            ORDER BY submission_deadline DESC NULLS LAST
            LIMIT :limit OFFSET :offset
        """)
        
        params["limit"] = limit
        params["offset"] = offset
        
        result = db.execute(query, params)
        rows = result.fetchall()
        
        records = []
        for row in rows:
            if not row[1]:  # skip if tender_id is NULL
                continue
            records.append(
                TenderRecord(
                    id=row[0],
                    title=row[2],
                    reference_no=row[3],
                    tender_id=row[1],
                    department=row[4],
                    estimated_value=row[5],
                    published_date=row[6].isoformat() if row[6] else None,
                    submission_deadline=row[7].isoformat() if row[7] else None,
                    opening_date=row[8].isoformat() if row[8] else None,
                    tender_url=row[9],
                    details=TenderDetail(
                        tender_id=row[1],
                        tender_type=row[10],
                        form_of_contract=row[11],
                        tender_category=row[12],
                        product_category=row[13],
                        sub_category=row[14],
                        work_description=row[15],
                        location=row[16],
                        pincode=row[17],
                        period_of_work=row[18],
                        bid_validity_days=row[19],
                        tender_fee=row[20],
                        emd_amount=row[21],
                        bid_submission_start=row[22].isoformat() if row[22] else None,
                        bid_submission_end=row[23].isoformat() if row[23] else None,
                        doc_download_start=row[24].isoformat() if row[24] else None,
                        doc_download_end=row[25].isoformat() if row[25] else None,
                        nit_documents=row[26] if isinstance(row[26], list) else (json.loads(row[26]) if row[26] else []),
                        work_documents=row[27] if isinstance(row[27], list) else (json.loads(row[27]) if row[27] else []),
                        inviting_authority_name=row[28].get("name") if isinstance(row[28], dict) else (json.loads(row[28]).get("name") if row[28] else None),
                        inviting_authority_address=row[28].get("address") if isinstance(row[28], dict) else (json.loads(row[28]).get("address") if row[28] else None),
                    ) if any([row[10], row[15], row[16]]) else None,
                )
            )
        return records
    
    # Fallback to JSON
    tenders = app.state.raw_tenders
    
    if tender_id:
        record = app.state.tender_map.get(tender_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Tender not found: {tender_id}")
        return [record]
    
    if search:
        query = search.strip().lower()
        tenders = [
            tender for tender in tenders
            if query in (tender.get("title", "") or "").lower()
            or query in (tender.get("reference_no", "") or "").lower()
            or query in (tender.get("tender_id", "") or "").lower()
            or query in (tender.get("department", "") or "").lower()
        ]
    
    if department:
        department_query = department.strip().lower()
        tenders = [
            tender for tender in tenders
            if department_query in (tender.get("department", "") or "").lower()
        ]
    
    results = []
    for tender in tenders[offset : offset + limit]:
        tender_id = tender.get("tender_id")
        results.append(
            {
                **tender,
                "details": app.state.detail_map.get(tender_id),
            }
        )
    
    return results


@app.get(
    "/tenders/{tender_id}",
    response_model=TenderRecord,
    summary="Get tender detail by tender_id",
    responses={404: {"description": "Tender not found."}},
)
def get_tender(tender_id: str, db: Session = Depends(get_db)) -> TenderRecord:
    """Fetch detailed information for a specific tender."""
    
    if app.state.postgres_available:
        result = db.execute(
            text("""
                SELECT 
                    id, tender_id, title, reference_no, department,
                    estimated_value, published_date, submission_deadline, opening_date,
                    tender_url, tender_type, form_of_contract, tender_category,
                    product_category, sub_category, work_description, location,
                    pincode, period_of_work, bid_validity_days, tender_fee,
                    emd_amount, bid_submission_start, bid_submission_end,
                    doc_download_start, doc_download_end, nit_documents, work_documents,
                    inviting_authority
                FROM tenders
                WHERE tender_id = :tender_id AND status = 'active'
            """),
            {"tender_id": tender_id}
        )
        
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Tender not found: {tender_id}")
        
        return TenderRecord(
            id=row[0],
            title=row[2],
            reference_no=row[3],
            tender_id=row[1],
            department=row[4],
            estimated_value=row[5],
            published_date=row[6].isoformat() if row[6] else None,
            submission_deadline=row[7].isoformat() if row[7] else None,
            opening_date=row[8].isoformat() if row[8] else None,
            tender_url=row[9],
            details=TenderDetail(
                tender_id=row[1],
                tender_type=row[10],
                form_of_contract=row[11],
                tender_category=row[12],
                product_category=row[13],
                sub_category=row[14],
                work_description=row[15],
                location=row[16],
                pincode=row[17],
                period_of_work=row[18],
                bid_validity_days=row[19],
                tender_fee=row[20],
                emd_amount=row[21],
                bid_submission_start=row[22].isoformat() if row[22] else None,
                bid_submission_end=row[23].isoformat() if row[23] else None,
                doc_download_start=row[24].isoformat() if row[24] else None,
                doc_download_end=row[25].isoformat() if row[25] else None,
                nit_documents=json.loads(row[26]) if row[26] else [],
                work_documents=json.loads(row[27]) if row[27] else [],
                inviting_authority_name=json.loads(row[28]).get("name") if row[28] else None,
                inviting_authority_address=json.loads(row[28]).get("address") if row[28] else None,
            ) if any([row[10], row[15], row[16]]) else None,
        )
    
    # Fallback to JSON
    record = app.state.tender_map.get(tender_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Tender not found: {tender_id}")
    return record

@app.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    result = db.execute(text("""
        SELECT work_category, COUNT(*) as count
        FROM tenders
        WHERE work_category IS NOT NULL
        GROUP BY work_category
        ORDER BY count DESC
    """))
    return [{"work_category": row[0], "count": row[1]} for row in result.fetchall()]
