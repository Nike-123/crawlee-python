# US IP Law Firm & Attorney Lead Scraper

A Python scraping system that collects US Intellectual Property (IP) law firms
from the U.S. News law-firm directory and then visits each firm's official
website to extract its attorneys, patent agents, trademark professionals and
other IP legal team members.

## Scope (per project requirements)

* Source directory: https://law.usnews.com/law-firms/practice-area/intellectual-property
* First 100 **unique** IP law firms discovered (de-duplicated by normalized
  website domain); no more than 100 are ever collected.
* Multiple professionals are collected per firm whenever publicly available
  (not just one per firm).
* Output: Excel + CSV in `output/`; logs and a URL visit log in `logs/`.

## Important: directory access blocker

Direct automated access to `law.usnews.com` is **blocked from this network at
the TLS/connection level** (`SSL_ERROR_SYSCALL` / empty HTTP reply; PyPI and
other hosts work fine, so general outbound HTTPS is not the issue). This is
consistent with an edge/WAF block on this sandbox's IP range. No CAPTCHA,
authentication or paywall was bypassed, and none will be.

To keep the pipeline runnable and verifiable, the scraper supports an
**offline/snapshot mode**: it reads saved directory page snapshots in
`snapshots/` (pages 1-7 of the directory, fetched through a browser) and
produces the same firm records live crawling would produce. Every firm website
is still crawled live, subject to each site's `robots.txt`.

To run the directory discovery live (from a network where `law.usnews.com` is
accessible):

```cmd
python main.py --live --full
```

If `robots.txt` disallows crawling, the scraper stops and reports it — the
blocker is recorded in `logs/scraping.log` and `scraping_summary.xlsx`.

## Project layout

```
ip_law_scraper/
├── main.py            # entry point / orchestrator
├── config.py          # all settings, limits, column contracts
├── directory.py       # U.S. News directory discovery (live + snapshot modes)
├── firm_crawler.py    # per-firm website crawling + professional extraction
├── storage.py         # checkpoints, URL log, Excel/CSV writing, summary
├── requirements.txt   # pip dependencies
├── snapshots/         # saved directory pages (offline directory mode)
├── output/            # generated xlsx + csv deliverables
└── logs/              # scraping.log + visited_urls.csv
```

## Windows execution

### 1. Install dependencies

```cmd
pip install -r requirements.txt
```

Required packages: `requests`, `beautifulsoup4`, `lxml`, `pandas`, `openpyxl`.
(`urllib.robotparser` is part of the Python standard library.)

### 2. Run the scraper

Test run (first 10 firms — recommended first step):

```cmd
python main.py
```

Full run (up to 100 unique firms):

```cmd
python main.py --full
```

Other options:

```cmd
python main.py --max-firms 25        # custom cap (never above 100)
python main.py --no-resume           # ignore checkpoint, start from scratch
python main.py --live --full         # live directory crawl (if network allows)
```

### 3. Output files

| File | Contents |
|------|----------|
| `output/us_ip_law_firms.xlsx` (and `.csv`) | One row per unique firm (max 100): name, website, directory URL, city/state, practice areas, status. |
| `output/us_ip_attorneys.xlsx` (and `.csv`) | One row per individual professional: all 23 required columns. |
| `output/scraping_summary.xlsx` (and `.csv`) | Counts: firms discovered/processed, professionals, e-mails, LinkedIn, blocked sites, page errors, duplicates removed. |
| `logs/visited_urls.csv` | Every URL visited: timestamp, stage, HTTP status, error. |
| `logs/scraping.log` | Human-readable run log. |

## Resume / checkpoints

A checkpoint (`output/checkpoint.json`) is saved after every firm. Re-running
the command resumes from the last completed firm without re-crawling finished
firms and without ever exceeding the 100-firm cap.

## Compliance notes

* `robots.txt` is checked for the directory and for every firm domain before
  crawling; disallowed sites are logged and skipped.
* Rate-limited sequential crawling (configurable delay, default ~1.2s between
  requests), timeouts, and retries with exponential backoff.
* No e-mail addresses are invented or guessed from name patterns. General
  firm e-mails (`info@`, `contact@`, ...) are never assigned to an attorney.
* No e-mail is marked "verified" unless independently verified; without an
  e-mail-verification API key, statuses are `Published on Official Website`
  or `Not Found` only.
* LinkedIn URLs are collected only when linked directly from an official firm
  website. No logged-in LinkedIn access, no URL guessing, no search-engine
  scraping of LinkedIn.
* No CAPTCHA, authentication, paywall or other access control is bypassed.

## Limitations (reported honestly)

* `law.usnews.com` blocks automated directory access from this network; snapshot
  mode is used instead (see blocker notice above).
* Some firm websites block bots, require JavaScript, or are otherwise
  unreachable; they are recorded as inaccessible/blocked rather than skipped
  silently.
* Attorney extraction relies on heuristics (headings that look like person
  names); results should be spot-checked before any outreach use.

## Attorney data in these outputs

Direct connections from this sandbox to law-firm websites are blocked at the
TLS/connection level (same edge/WAF behavior as `law.usnews.com`; PyPI works,
so general outbound HTTPS is not the issue). The attorney rows in
`us_ip_attorneys.xlsx/.csv` were therefore collected page-by-page through the
Arena browsing tool (`fetch_page`), which retrieves public pages **without**
logging in, bypassing CAPTCHAs/paywalls, or scraping LinkedIn. Every e-mail,
phone, title and LinkedIn URL was copied verbatim from the firm's own public
pages; nothing was invented, guessed or generated from name patterns.

The merge is reproducible via:

```cmd
python apply_proxy_collected_data.py
```

It reads `output/checkpoint.json` (produced by `main.py --full`), marks the
7 crawled firms as `processed`, appends the crawled URLs to
`logs/visited_urls.csv`, and rewrites all six output files. The 7 firms with
attorney data: Actuate Law LLC (5), Advent LLP (12), Artegis Law Group LLP
(10), Avek IP (10 — no e-mails are published on its site), Amin Turocy &
Watson LLP (8), Andrus Intellectual Property Law LLP (3), Ashby & Geddes P.A.
(2 IP-practice-group attorneys). The remaining 93 firms are recorded as
inaccessible because their sites could not be reached from this network.