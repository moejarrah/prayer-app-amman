#!/usr/bin/env python3
"""
Scraper for https://www.awqaf.gov.jo/ar/Pages/PrayerTime

Iterates through all paginated pages, extracts prayer times for Amman
(city_id=1), and saves to prayer-times.json.

The site uses ASP.NET WebForms with __VIEWSTATE/__EVENTVALIDATION tokens.
Each page shows 10 rows. Covers ~1 year of data.

Usage:  python3 scrape.py
Output: prayer-times.json
"""

import requests
import re
import json
import time
import sys
from datetime import datetime

BASE = "https://www.awqaf.gov.jo/ar/Pages/PrayerTime"
OUTPUT = "prayer-times.json"
MIN_DELAY = 2.0
MAX_RETRIES = 5
TIMEOUT = 60
MAX_EMPTY_PAGES = 3  # consecutive empty pages before giving up

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def get_with_retry(url, timeout=TIMEOUT):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=timeout)
            if resp.status_code == 200 and len(resp.text) > 5000:
                return resp
            log(f"  GET attempt {attempt}: status={resp.status_code} len={len(resp.text)}")
        except requests.Timeout:
            log(f"  GET attempt {attempt}: timeout ({timeout}s)")
        except requests.ConnectionError as e:
            log(f"  GET attempt {attempt}: connection error - {e}")
        except Exception as e:
            log(f"  GET attempt {attempt}: {type(e).__name__} - {e}")

        if attempt < MAX_RETRIES:
            wait = 4 * attempt
            log(f"  waiting {wait}s...")
            time.sleep(wait)
    return None


def post_with_retry(data, timeout=TIMEOUT):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.post(BASE, data=data, timeout=timeout)
            if resp.status_code == 200 and len(resp.text) > 5000:
                return resp
            log(f"  POST attempt {attempt}: status={resp.status_code} len={len(resp.text)}")
        except requests.Timeout:
            log(f"  POST attempt {attempt}: timeout ({timeout}s)")
        except requests.ConnectionError as e:
            log(f"  POST attempt {attempt}: connection error - {e}")
        except Exception as e:
            log(f"  POST attempt {attempt}: {type(e).__name__} - {e}")

        if attempt < MAX_RETRIES:
            wait = 4 * attempt
            log(f"  waiting {wait}s...")
            time.sleep(wait)
    return None


def get_form_tokens(html_text):
    """Extract VIEWSTATE and EVENTVALIDATION from HTML."""
    vs = re.search(r'id="__VIEWSTATE"\s+value="([^"]+)"', html_text)
    ev = re.search(r'id="__EVENTVALIDATION"\s+value="([^"]+)"', html_text)
    if not vs:
        raise ValueError("VIEWSTATE not found")
    return vs.group(1), (ev.group(1) if ev else "")


def extract_times(html):
    """Extract prayer time rows from a page of HTML.
    Site dates are DD/MM/YYYY format. Times are in 12h format.
    PM times (dhuhr, asr, maghrib, isha) get +12 for 24h conversion."""
    rows = []

    dates = re.findall(r'gvWebparts_lbldate_(\d+)">([^<]+)', html)
    if not dates:
        return rows

    def to_24h(time_str, is_pm):
        """Convert 12h time to 24h. PM prayers get +12 unless already 12:xx."""
        parts = time_str.strip().split(':')
        if len(parts) != 2:
            return time_str
        h = int(parts[0])
        m = parts[1]
        if is_pm and h < 12:
            h += 12
        return f"{h}:{m}"

    for idx_str, date_str in dates:
        idx = int(idx_str)

        p = {}
        for pnum in range(1, 7):
            m = re.search(rf'gvWebparts_Labpayr{pnum}_{idx}">([^<]+)', html)
            p[f"p{pnum}"] = m.group(1).strip() if m else "??:??"

        # Convert DD/MM/YYYY -> YYYY-MM-DD
        parts = date_str.strip().split("/")
        if len(parts) == 3:
            date_iso = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
        else:
            date_iso = date_str.strip()

        rows.append({
            "date": date_iso,
            "fajr":    to_24h(p["p1"], False),
            "shuruq":  to_24h(p["p2"], False),
            "dhuhr":   to_24h(p["p3"], True),
            "asr":     to_24h(p["p4"], True),
            "maghrib": to_24h(p["p5"], True),
            "isha":    to_24h(p["p6"], True),
        })

    return rows


def get_last_page_num(html):
    """Find the highest page number from pagination, including '... Last' link.
    ASP.NET renders Last as: javascript:__doPostBack('ctl00$MainContent$gvWebparts','Page$Last')
    We need to discover the actual last page number. Try to find it from
    the '...' link or just iterate until empty."""
    pages = re.findall(r"Page\$(\d+)", html)
    if "Last" in html or "الأخيرة" in html:
        # We can't know the exact number from the word "Last"
        # Just return a high bound and let iteration handle it
        if pages:
            return max(int(p) for p in pages) + 50  # estimate
        return 200  # high estimate
    if pages:
        return max(int(p) for p in pages)
    return 1


def scrape():
    log("Scraping awqaf.gov.jo prayer times for Amman")
    log("=" * 50)

    all_rows = []
    seen_dates = set()

    # Step 1: GET initial page
    log("GET initial page...")
    resp = get_with_retry(BASE)
    if not resp:
        log("FATAL: Could not load page after retries")
        sys.exit(1)

    rows = extract_times(resp.text)
    for r in rows:
        if r["date"] not in seen_dates:
            seen_dates.add(r["date"])
            all_rows.append(r)
    log(f"Page 1: {len(rows)} rows loaded")

    total_pages = get_last_page_num(resp.text)
    log(f"Estimated total pages: {total_pages}")

    vs, ev = get_form_tokens(resp.text)

    # Step 2: Paginate forward
    empty_streak = 0
    for page_num in range(2, total_pages + 1):
        if empty_streak >= MAX_EMPTY_PAGES:
            log(f"  {MAX_EMPTY_PAGES} empty pages in a row. Done.")
            break

        log(f"Page {page_num}/{total_pages}...")

        data = {
            "__EVENTTARGET": "ctl00$MainContent$gvWebparts",
            "__EVENTARGUMENT": f"Page${page_num}",
            "__VIEWSTATE": vs,
            "__VIEWSTATEGENERATOR": "CDE16AB2",
            "__EVENTVALIDATION": ev,
            "ctl00$MainContent$DropCompany": "1",
        }

        resp = post_with_retry(data)
        if not resp:
            log(f"  FAILED. Attempting session refresh...")
            session.cookies.clear()
            time.sleep(5)
            refresh = get_with_retry(BASE)
            if refresh:
                vs, ev = get_form_tokens(refresh.text)
                resp = post_with_retry(data)
            if not resp:
                log(f"  Giving up on page {page_num}.")
                empty_streak += 1
                continue

        try:
            vs, ev = get_form_tokens(resp.text)
        except ValueError:
            log(f"  WARNING: no tokens in response, reusing old")

        rows = extract_times(resp.text)
        new_count = 0
        for r in rows:
            if r["date"] not in seen_dates:
                seen_dates.add(r["date"])
                all_rows.append(r)
                new_count += 1

        log(f"  got {len(rows)} rows, {new_count} new. Total: {len(all_rows)}")

        if len(rows) == 0:
            empty_streak += 1
        else:
            empty_streak = 0

        time.sleep(MIN_DELAY)

    # Step 3: Sort and save
    all_rows.sort(key=lambda r: r["date"])

    output = {
        "city": "Amman",
        "city_id": 1,
        "method": "awqaf_jordan_official",
        "source": BASE,
        "scraped_at": datetime.now().isoformat(),
        "count": len(all_rows),
        "prayers": all_rows,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log("=" * 50)
    log(f"DONE. {len(all_rows)} entries -> {OUTPUT}")
    if all_rows:
        log(f"Range: {all_rows[0]['date']} to {all_rows[-1]['date']}")


if __name__ == "__main__":
    scrape()
