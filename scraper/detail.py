import re
import logging
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TenderDetail:
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
    nit_documents: list[str] = field(default_factory=list)
    work_documents: list[str] = field(default_factory=list)
    inviting_authority_name: Optional[str] = None
    inviting_authority_address: Optional[str] = None


def parse_amount(text: str) -> Optional[float]:
    if not text or text.strip() in ["-", "NA", "Nil", ""]:
        return None
    cleaned = re.sub(r"[^\d.]", "", text)
    try:
        return float(cleaned)
    except ValueError:
        return None


def get_field_value(soup: BeautifulSoup, caption_text: str) -> Optional[str]:
    """
    Find a <td class='td_caption'> containing caption_text,
    return the text of the next <td class='td_field'>.
    """
    for td in soup.find_all("td", class_="td_caption"):
        if caption_text.lower() in td.get_text(strip=True).lower():
            next_td = td.find_next_sibling("td", class_="td_field")
            if next_td:
                return next_td.get_text(strip=True)
            # Sometimes td_field is not a sibling but next td
            parent = td.parent
            if parent:
                cells = parent.find_all("td")
                for i, cell in enumerate(cells):
                    if caption_text.lower() in cell.get_text(strip=True).lower():
                        if i + 1 < len(cells):
                            return cells[i + 1].get_text(strip=True)
    return None


def parse_detail_page(html: str, tender_id: str) -> TenderDetail:
    soup = BeautifulSoup(html, "lxml")
    detail = TenderDetail(tender_id=tender_id)

    # ── Basic Details ──
    detail.organisation_chain = get_field_value(soup, "Organisation Chain")
    detail.reference_no       = get_field_value(soup, "Tender Reference Number")
    detail.tender_type        = get_field_value(soup, "Tender Type")
    detail.form_of_contract   = get_field_value(soup, "Form Of Contract")
    detail.tender_category    = get_field_value(soup, "Tender Category")

    # ── Work Item Details ──
    detail.work_description = get_field_value(soup, "Work Description")
    detail.product_category = get_field_value(soup, "Product Category")
    detail.sub_category     = get_field_value(soup, "Sub category")
    detail.location         = get_field_value(soup, "Location")
    if detail.location and detail.location in ["Goods", "Works", "Services", "NA"]:
        detail.location = None
    detail.pincode          = get_field_value(soup, "Pincode")
    detail.period_of_work   = get_field_value(soup, "Period Of Work")
    detail.bid_validity_days = get_field_value(soup, "Bid Validity")

    # ── Fee Details ──
    tender_fee_text = get_field_value(soup, "Tender Fee in")
    detail.tender_fee = parse_amount(tender_fee_text)

    emd_text = get_field_value(soup, "EMD Amount in")
    detail.emd_amount = parse_amount(emd_text)
    detail.emd_exemption = get_field_value(soup, "EMD Exemption Allowed")

    # ── Critical Dates ──
    detail.published_date      = get_field_value(soup, "Published Date")
    detail.bid_opening_date    = get_field_value(soup, "Bid Opening Date")
    detail.doc_download_start  = get_field_value(soup, "Document Download / Sale Start Date")
    detail.doc_download_end    = get_field_value(soup, "Document Download / Sale End Date")
    detail.bid_submission_start = get_field_value(soup, "Bid Submission Start Date")
    detail.bid_submission_end   = get_field_value(soup, "Bid Submission End Date")

    # ── NIT / Tender Documents ──
    # Find the NIT Document table
    nit_links = []
    for a in soup.find_all("a", id=re.compile(r"^docDownoad")):
        filename = a.get_text(strip=True)
        if filename:
            nit_links.append(filename)
    detail.nit_documents = nit_links

    # Work item documents (BOQ, tender documents)
    work_docs = []
    work_table = soup.find("table", {"id": "workItemDocumenttable"})
    if work_table:
        for row in work_table.find_all("tr", class_=["even", "odd"]):
            cells = row.find_all("td")
            if len(cells) >= 3:
                doc_type = cells[1].get_text(strip=True)
                doc_name_cell = cells[2]
                doc_name = doc_name_cell.get_text(strip=True).split("\n")[0].strip()
                if doc_name:
                    work_docs.append(f"{doc_type}: {doc_name}")
    detail.work_documents = work_docs

    # ── Tender Inviting Authority ──
    detail.inviting_authority_name    = get_field_value(soup, "Name")
    detail.inviting_authority_address = get_field_value(soup, "Address")

    return detail