import json
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = ROOT / "tenders_raw.json"
DETAIL_DATA_PATH = ROOT / "tenders_detail.json"


class TenderSummary(BaseModel):
    title: str
    reference_no: str
    tender_id: str
    department: str
    published_date: Optional[str] = None
    closing_date: Optional[str] = None
    opening_date: Optional[str] = None
    estimated_value: Optional[float] = None
    tender_url: Optional[str] = None


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
    published_date: Optional[str] = None
    bid_opening_date: Optional[str] = None
    doc_download_start: Optional[str] = None
    doc_download_end: Optional[str] = None
    bid_submission_start: Optional[str] = None
    bid_submission_end: Optional[str] = None
    nit_documents: List[str] = Field(default_factory=list)
    work_documents: List[str] = Field(default_factory=list)
    inviting_authority_name: Optional[str] = None
    inviting_authority_address: Optional[str] = None


class TenderRecord(TenderSummary):
    details: Optional[TenderDetail] = None


app = FastAPI(
    title="Tender Aggregator API",
    description="REST API exposing tender listings and detail records from local data files.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@app.on_event("startup")
def startup_event():
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


@app.get("/", summary="API root")
def root():
    return {
        "service": "Tender Aggregator API",
        "endpoints": [
            "/tenders",
            "/tenders/{tender_id}",
            "/health",
        ],
    }


@app.get("/health", summary="Health check")
def health():
    return {"status": "ok"}


@app.get("/tenders", response_model=List[TenderRecord], summary="List tender summaries")
def list_tenders(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Search by title, reference number, tender ID, or department."),
    department: Optional[str] = Query(None, description="Filter by department text."),
    tender_id: Optional[str] = Query(None, description="Return only the tender with this tender_id."),
) -> List[TenderRecord]:
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
def get_tender(tender_id: str) -> TenderRecord:
    record = app.state.tender_map.get(tender_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Tender not found: {tender_id}")
    return record
