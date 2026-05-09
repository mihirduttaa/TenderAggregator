import asyncio
import logging
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, Browser
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

BASE_URL = "https://mptenders.gov.in/nicgep/app"
HOME_URL = f"{BASE_URL}?service=restart"
TENDERS_URL = f"{BASE_URL}?page=FrontEndLatestActiveTenders&service=page"


@dataclass
class TenderListing:
    title: str
    reference_no: str
    tender_id: str
    department: str
    published_date: Optional[str]
    closing_date: Optional[str]
    opening_date: Optional[str]
    estimated_value: Optional[float]
    tender_url: Optional[str]


def parse_amount(text: str) -> Optional[float]:
    if not text or text.strip() in ["-", ""]:
        return None
    cleaned = re.sub(r"[^\d.]", "", text)
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_table(html: str) -> list[TenderListing]:
    """Parse the tender table from page HTML."""
    soup = BeautifulSoup(html, "lxml")
    tenders = []

    table = soup.find("table", {"id": "table"})
    print(f"Table with id='table' found: {table is not None}")
    if not table:
        print("No table found, returning empty")
        return tenders

    rows = table.find_all("tr", class_=re.compile(r'\b(even|odd)\b'))
    print(f"Found {len(rows)} rows with even/odd class")
    if not rows:
        print("No rows found")
        return tenders

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 7:
            continue
        try:
            # Cell 4: Title link + [RefNo][TenderID] as plain text
            title_cell = cells[4]
            title_link = title_cell.find("a")
            title = title_link.get_text(strip=True) if title_link else ""
            if not title:
                continue

            tender_url = title_link["href"] if title_link else None
            if tender_url and not tender_url.startswith("http"):
                tender_url = f"https://mptenders.gov.in{tender_url}"

            # Format after link: " [720][2026_UAD_505556_1] "
            full_text = title_cell.get_text(strip=True)
            after_link = full_text.replace(title, "").strip()
            brackets = re.findall(r'\[([^\]]+)\]', after_link)
            reference_no = brackets[0] if len(brackets) > 0 else ""
            tender_id    = brackets[1] if len(brackets) > 1 else ""

            # Cell 5: Organisation Chain
            department = cells[5].get_text(separator=" | ", strip=True)

            # Cell 6: Tender Value in ₹
            estimated_value = parse_amount(cells[6].get_text(strip=True))

            tenders.append(TenderListing(
                title=title,
                reference_no=reference_no,
                tender_id=tender_id,
                department=department,
                published_date=cells[1].get_text(strip=True) or None,
                closing_date=cells[2].get_text(strip=True) or None,
                opening_date=cells[3].get_text(strip=True) or None,
                estimated_value=estimated_value,
                tender_url=tender_url,
            ))
        except Exception as e:
            logger.warning(f"Row parse error: {e}")
            continue

    return tenders


def get_next_page_url(soup: BeautifulSoup) -> Optional[str]:
    """Find the Next > pagination link."""
    for a in soup.find_all("a"):
        if a.get_text(strip=True) in ["Next >", "Next>", "next", "Next"]:
            href = a.get("href", "")
            if href and not href.startswith("http"):
                href = f"https://mptenders.gov.in{href}"
            return href or None
    return None


async def scrape_all_tenders(headless: bool = False) -> list[TenderListing]:
    all_tenders = []

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"
        )
        page: Page = await context.new_page()

        try:
            # Step 1: Establish session via homepage
            logger.info("Step 1: Establishing session via homepage...")
            await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
            logger.info(f"Homepage loaded: {await page.title()}")
            await asyncio.sleep(2)

            # Step 2: Navigate to active tenders page
            logger.info("Step 2: Navigating to Active Tenders page...")
            await page.goto(TENDERS_URL, wait_until="domcontentloaded", timeout=60000)
            logger.info(f"Tenders page loaded: {page.url}")

            # Step 3: Wait for human to solve CAPTCHA
            print("\n" + "="*60)
            print("Solve the CAPTCHA in the browser window,")
            print("then click the Search button.")
            print("Wait for tenders to appear on screen,")
            print("then come back here and press ENTER.")
            print("="*60)
            input("\nPress ENTER after tenders are visible...")

            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2)

            # Step 4: Paginate through all pages
            page_num = 1

            while True:
                try:
                    logger.info(f"Scraping page {page_num}...")

                    html = await page.content()
                    print(f"HTML length: {len(html)}")

                    # Save first page for debugging
                    if page_num == 1:
                        with open("debug_page.html", "w", encoding="utf-8") as f:
                            f.write(html)
                        logger.info("Saved debug_page.html")

                    tenders = parse_table(html)
                    print(f"Parsed {len(tenders)} tenders from page {page_num}")
                    all_tenders.extend(tenders)
                    logger.info(f"  Page {page_num}: {len(tenders)} tenders | Total: {len(all_tenders)}")

                    if not tenders:
                        logger.info("No tenders found on this page. Stopping.")
                        break

                    # Find Next button in live page
                    next_btn = await page.query_selector("a#loadNext")
                    if not next_btn:
                        next_btn = await page.query_selector("a[title='Load Next']")
                    if not next_btn:
                        next_btn = await page.query_selector("a:text('Next >')")
                    if not next_btn:
                        next_btn = await page.query_selector("a:text('Next>')")
                    if not next_btn:
                        logger.info("No Next button found. Reached last page.")
                        break

                    await next_btn.click()
                    await page.wait_for_selector("table#table tr.even, table#table tr.odd", timeout=30000)
                    await asyncio.sleep(1.5)

                    page_num += 1

                    if page_num > 600:
                        logger.warning("Safety limit reached. Stopping.")
                        break
                except Exception as e:
                    print(f"Error on page {page_num}: {e}")
                    break

            print(f"Total collected: {len(all_tenders)}")

        except Exception as e:
            logger.error(f"Scraper error: {e}")
            try:
                html = await page.content()
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(html)
                logger.info("Saved debug_page.html for inspection.")
            except:
                pass

        finally:
            await browser.close()

    logger.info(f"Scraping complete. Total tenders: {len(all_tenders)}")
    return all_tenders