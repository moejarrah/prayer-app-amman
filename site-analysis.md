# Awqaf Prayer Times Site Analysis

## URL
`https://www.awqaf.gov.jo/ar/Pages/PrayerTime`

## Technology
- ASP.NET WebForms with UpdatePanel (`MainContent_UpdatePanel1`)
- **No API, no JSON, no query parameters** — pure server-side rendering
- TSPD/Akamai bot protection — requires session cookies
- English version (`/en/Pages/PrayerTime`) returns HTTP 500

## How Pagination Works

The GridView (`MainContent_gvWebparts`) is inside an UpdatePanel. Navigation uses ASP.NET postback:

```
POST https://www.awqaf.gov.jo/ar/Pages/PrayerTime
Content-Type: application/x-www-form-urlencoded

__EVENTTARGET=ctl00$MainContent$gvWebparts
__EVENTARGUMENT=Page$N           (N=page number, or "First"/"Last")
__VIEWSTATE=<long base64 string>
__VIEWSTATEGENERATOR=CDE16AB2
__EVENTVALIDATION=<base64 string>
```

**Critical**: You must GET the page first for fresh VIEWSTATE/EVENTVALIDATION tokens. Each POST response returns new tokens. VIEWSTATE is ~112KB compressed.

## Table Structure

```html
<table id="MainContent_gvWebparts" class="borderTable">
  <tr class="headrgv">
    <th>التاريخ</th><th>الفجر</th><th>الشروق</th><th>الظهر</th>
    <th>العصر</th><th>المغرب</th><th>العشاء</th>
  </tr>
  <tr>
    <td><span id="MainContent_gvWebparts_lbldate_0">31/05/2026</span></td>
    <td><span id="MainContent_gvWebparts_Labpayr1_0">03:53</span></td>
    <td><span id="MainContent_gvWebparts_Labpayr2_0">05:24</span></td>
    <td><span id="MainContent_gvWebparts_Labpayr3_0">12:34</span></td>
    <td><span id="MainContent_gvWebparts_Labpayr4_0">04:15</span></td>
    <td><span id="MainContent_gvWebparts_Labpayr5_0">07:44</span></td>
    <td><span id="MainContent_gvWebparts_Labpayr6_0">09:15</span></td>
  </tr>
  <!-- 10 rows per page -->
</table>
```

**Span ID patterns**:
| Column | ID Pattern |
|--------|-----------|
| Date | `MainContent_gvWebparts_lbldate_{N}` |
| Fajr | `MainContent_gvWebparts_Labpayr1_{N}` |
| Shuruq | `MainContent_gvWebparts_Labpayr2_{N}` |
| Dhuhr | `MainContent_gvWebparts_Labpayr3_{N}` |
| Asr | `MainContent_gvWebparts_Labpayr4_{N}` |
| Maghrib | `MainContent_gvWebparts_Labpayr5_{N}` |
| Isha | `MainContent_gvWebparts_Labpayr6_{N}` |

## Pagination Details

| Property | Value |
|----------|-------|
| Rows per page | 10 |
| Default range | Today → Dec 31 (end of current year) |
| Total pages (for 2026) | 22 (215 days from May 31) |
| Date format | DD/MM/YYYY |

**Pager row example**: `[1] 2 3 4 5 6 ... Last`

## City Dropdown

| Value | City |
|-------|------|
| 1 | عمان، البلقاء، الزرقاء، مادبا |
| 2 | اربد |
| 3 | الكرك |
| 4 | الطفيلة |
| 5 | معان |
| 6 | العقبة |
| 7 | الأغوار الشمالية |
| 8 | جرش وعجلون |
| 9 | المفرق |
| 11 | ذيبان |
| 12 | الأزرق |
| 13 | الأغوار الوسطى |
| 14 | الشوبك والبتراء |
| 15 | الظليل والهاشمية |
| 19 | الرويشد |
| 33 | القدس |

## Date Search

The page has date pickers (`txtFromDate`, `txtToDate`) with format `yyyy/MM/dd`. Default date fields are empty (server defaults to today→end-of-data).

To search a specific range, POST with:
```
ctl00$MainContent$txtFromDate=2026/01/01
ctl00$MainContent$txtToDate=2026/12/31
ctl00$MainContent$btn_search=ابحث
```

## Site Reliability Issues

- **Very slow initial connection** — first GET can take 30-60 seconds or timeout
- **TSPD bot protection** — sometimes captchas, sometimes just slow
- **Inconsistent response times** — once session established, POSTs are fast (3-5s)
- **Session fragility** — if too many requests too fast, session gets killed
- **Minimum 2s delay between requests** recommended

## Scraper Strategy

1. GET initial page (retry up to 5 times with increasing delays)
2. Extract VIEWSTATE/EVENTVALIDATION
3. POST for each subsequent page
4. If POST fails, clear cookies and re-GET for fresh session
5. Stop after 3 consecutive empty pages
6. Output: `prayer-times.json` with ~215 entries (today through Dec 31)

## Regex for Extraction

```python
# Dates
re.findall(r'gvWebparts_lbldate_(\d+)">([^<]+)', html)

# Prayer times (pnum = 1-6)
re.findall(rf'gvWebparts_Labpayr{pnum}_(\d+)">([^<]+)', html)

# Page numbers in pagination
re.findall(r"Page\$(\d+)", html)
```

## Data Format (output JSON)

```json
{
  "city": "Amman",
  "city_id": 1,
  "method": "awqaf_jordan_official",
  "source": "https://www.awqaf.gov.jo/ar/Pages/PrayerTime",
  "scraped_at": "2026-05-31T23:50:26",
  "count": 215,
  "prayers": [
    {
      "date": "2026-05-31",
      "fajr": "03:53",
      "shuruq": "05:24",
      "dhuhr": "12:34",
      "asr": "04:15",
      "maghrib": "07:44",
      "isha": "09:15"
    }
  ]
}
```
