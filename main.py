import asyncio
import logging
import json
from scraper.browser import scrape_all_tenders
from scraper.detail import parse_detail_page, TenderDetail
from dataclasses import asdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main():
    from playwright.async_api import async_playwright

    BASE_URL = "https://mptenders.gov.in/nicgep/app"
    HOME_URL = f"{BASE_URL}?service=restart"
    TENDERS_URL = f"{BASE_URL}?page=FrontEndLatestActiveTenders&service=page"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        all_tenders = []

        try:
            print("Step 1: Establishing session...")
            await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)

            print("Step 2: Going to Active Tenders page...")
            await page.goto(TENDERS_URL, wait_until="domcontentloaded", timeout=60000)

            print("\n" + "="*60)
            print("Solve the CAPTCHA, click Search,")
            print("wait for tenders to load, then press ENTER.")
            print("="*60)
            input("\nPress ENTER after tenders are visible...")

            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2)

            # ── Phase 1: Scrape all listing pages ──
            from scraper.browser import parse_table
            page_num = 1

            while True:
                html = await page.content()
                tenders = parse_table(html)
                all_tenders.extend(tenders)
                print(f"Page {page_num}: {len(tenders)} tenders | Total: {len(all_tenders)}")

                if not tenders:
                    break

                next_btn = await page.query_selector("a#loadNext")
                if not next_btn:
                    next_btn = await page.query_selector("a:text('Next >')")
                if not next_btn:
                    print("No Next button. Done paginating.")
                    break

                await next_btn.click()
                await page.wait_for_selector("table#table tr.even, table#table tr.odd", timeout=30000)
                await asyncio.sleep(1.5)
                page_num += 1

                if page_num > 100:
                    break

            # Save listing data first
            listing_output = [
                {
                    "title": t.title,
                    "reference_no": t.reference_no,
                    "tender_id": t.tender_id,
                    "department": t.department,
                    "published_date": t.published_date,
                    "closing_date": t.closing_date,
                    "opening_date": t.opening_date,
                    "estimated_value": t.estimated_value,
                    "tender_url": t.tender_url,
                }
                for t in all_tenders
            ]
            with open("tenders_raw.json", "w", encoding="utf-8") as f:
                json.dump(listing_output, f, ensure_ascii=False, indent=2)
            print(f"\nSaved {len(listing_output)} tenders to tenders_raw.json")

            # ── Phase 2: Visit each tender detail page ──
            print("\nStarting detail page scraping...")
            details_output = []

            for i, tender in enumerate(all_tenders):
                if not tender.tender_url:
                    continue
                try:
                    await page.goto(tender.tender_url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(1)
                    html = await page.content()
                    detail = parse_detail_page(html, tender.tender_id)
                    details_output.append(asdict(detail))
                    print(f"  [{i+1}/{len(all_tenders)}] {tender.tender_id} — EMD: {detail.emd_amount}, Location: {detail.location}")
                except Exception as e:
                    print(f"  [{i+1}] Error on {tender.tender_id}: {e}")
                    continue

            with open("tenders_detail.json", "w", encoding="utf-8") as f:
                json.dump(details_output, f, ensure_ascii=False, indent=2)
            print(f"\nSaved {len(details_output)} detail records to tenders_detail.json")

        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())