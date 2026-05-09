import asyncio
import logging
import json
from scraper.browser import parse_table

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
            # Step 1: Hit homepage to establish session
            print("Step 1: Establishing session via homepage...")
            await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
            print(f"Homepage loaded. Title: {await page.title()}")
            await asyncio.sleep(2)

            # Step 2: Navigate to active tenders (CAPTCHA will appear here)
            print("Step 2: Going to Active Tenders page...")
            await page.goto(TENDERS_URL, wait_until="domcontentloaded", timeout=60000)
            print(f"Tenders page loaded. URL: {page.url}")

            # Step 3: Wait for human to solve CAPTCHA
            print("\n" + "="*60)
            print("Solve the CAPTCHA in the browser window, then")
            print("click the Search button on the page.")
            print("After tenders load, come back here and press ENTER.")
            print("="*60)
            input("\nPress ENTER after tenders are visible on screen...")

            # Step 4: Save HTML to inspect structure
            await page.wait_for_load_state("domcontentloaded")
            html = await page.content()
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Saved debug_page.html — open this in your browser to inspect.")
            print(f"Current URL: {page.url}")

            tenders = parse_table(html)
            all_tenders.extend(tenders)
            print(f"Parsed {len(tenders)} tenders from the page")

            page_num = 1

            while True:
                if not tenders:
                    print("No tenders found on this page. Stopping.")
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
                    print("No Next button found. Reached last page.")
                    break

                await next_btn.click()
                await page.wait_for_selector("table#table tr.even, table#table tr.odd", timeout=30000)
                await asyncio.sleep(1.5)

                html = await page.content()
                tenders = parse_table(html)
                all_tenders.extend(tenders)
                print(f"Parsed {len(tenders)} tenders from page {page_num + 1} | Total: {len(all_tenders)}")

                page_num += 1

                if page_num > 600:
                    print("Safety limit reached. Stopping.")
                    break

            await asyncio.sleep(30)

        except Exception as e:
            print(f"ERROR: {e}")
            try:
                html = await page.content()
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print("Saved debug_page.html")
            except:
                pass
            await asyncio.sleep(20)

        finally:
            await browser.close()

    output = []
    for t in all_tenders:
        output.append({
            "title": t.title,
            "reference_no": t.reference_no,
            "tender_id": t.tender_id,
            "department": t.department,
            "published_date": t.published_date,
            "closing_date": t.closing_date,
            "opening_date": t.opening_date,
            "estimated_value": t.estimated_value,
            "tender_url": t.tender_url,
        })

    with open("tenders_raw.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(output)} tenders to tenders_raw.json")

if __name__ == "__main__":
    asyncio.run(main())