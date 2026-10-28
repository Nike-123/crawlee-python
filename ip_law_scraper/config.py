"""Configuration for the US IP law firm / attorney lead scraper.

All settings are centralized here so the scraper can be tuned without
editing the pipeline logic. API keys must come from environment variables
-- never hardcode credentials.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Project layout
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
SNAPSHOT_DIR = BASE_DIR / "snapshots"

CHECKPOINT_FILE = OUTPUT_DIR / "checkpoint.json"
VISITED_URLS_FILE = LOGS_DIR / "visited_urls.csv"
SCRAPING_LOG_FILE = LOGS_DIR / "scraping.log"

FIRMS_XLSX = OUTPUT_DIR / "us_ip_law_firms.xlsx"
FIRMS_CSV = OUTPUT_DIR / "us_ip_law_firms.csv"
ATTORNEYS_XLSX = OUTPUT_DIR / "us_ip_attorneys.xlsx"
ATTORNEYS_CSV = OUTPUT_DIR / "us_ip_attorneys.csv"
SUMMARY_XLSX = OUTPUT_DIR / "scraping_summary.xlsx"
SUMMARY_CSV = OUTPUT_DIR / "scraping_summary.csv"

# ---------------------------------------------------------------------------
# Source directory (U.S. News - Intellectual Property law firms)
# ---------------------------------------------------------------------------
DIRECTORY_URL = (
    "https://law.usnews.com/law-firms/practice-area/intellectual-property"
)
DIRECTORY_BASE = "https://law.usnews.com"

# ---------------------------------------------------------------------------
# Scope limits
# ---------------------------------------------------------------------------
MAX_FIRMS = 100          # hard cap: never discover more than 100 unique firms
TEST_FIRMS = 10          # small test run size

# ---------------------------------------------------------------------------
# Network / politeness settings
# ---------------------------------------------------------------------------
USER_AGENT = (
    "IPLawLeadScraper/1.0 (compatible; law-firm public directory research; "
    "no automated account creation or bypass of access controls)"
)
ACCEPT_LANGUAGE = "en-US,en;q=0.9"
REQUEST_TIMEOUT = 25                      # seconds
MAX_RETRIES = 3                           # retries for temporary HTTP errors
BACKOFF_FACTOR = 2.0                      # exponential backoff multiplier
REQUEST_DELAY = 1.2                       # seconds between requests (conservative)
MAX_PAGES_PER_FIRM = 10                   # max pages crawled per firm website
BATCH_SIZE = 5                            # rewrite outputs after every N firms

# E-mail verification: only when an API key is provided AND its use is authorized.
EMAIL_VERIFICATION_API_KEY = os.getenv("EMAIL_VERIFICATION_API_KEY", "")

# ---------------------------------------------------------------------------
# E-mail verification statuses (task-specified vocabulary)
# ---------------------------------------------------------------------------
EMAIL_STATUS_PUBLISHED = "Published on Official Website"
EMAIL_STATUS_VERIFIED = "Independently Verified"
EMAIL_STATUS_UNVERIFIED = "Unverified"
EMAIL_STATUS_INVALID = "Invalid"
EMAIL_STATUS_NOT_FOUND = "Not Found"

# ---------------------------------------------------------------------------
# Extraction statuses
# ---------------------------------------------------------------------------
EXTRACTION_SUCCESS = "Success"
EXTRACTION_PARTIAL = "Partial"
EXTRACTION_NOT_FOUND = "Not Found"
EXTRACTION_BLOCKED = "Blocked / Inaccessible"
EXTRACTION_ROBOTS_BLOCKED = "Blocked by robots.txt"

# ---------------------------------------------------------------------------
# Role classification (priority order mirrors the task requirements)
# ---------------------------------------------------------------------------
ROLE_RULES = [
    ("Registered Patent Agent", ["patent agent"]),
    ("Patent Attorney", ["patent", "attorney"]),
    ("Patent Attorney", ["patent", "lawyer"]),
    ("Patent Attorney", ["patent", "counsel"]),
    ("Trademark Attorney", ["trademark"]),
    ("Intellectual Property Attorney", ["intellectual property"]),
    ("Intellectual Property Attorney", [" ip "]),
    ("Managing Partner", ["managing partner"]),
    ("Partner", ["partner"]),
    ("Founder / Owner", ["founder", "owner"]),
]
DEFAULT_ROLE = "Other Legal Professional"

# ---------------------------------------------------------------------------
# Page-discovery keywords (nav links, sitemap URLs, link text)
# ---------------------------------------------------------------------------
PAGE_KEYWORDS = [
    "attorney", "lawyer", "counsel", "team", "professional", "people",
    "staff", "patent", "trademark", "ip", "intellectual-property",
    "intellectual property", "contact", "about", "practice-area",
    "practice-areas", "our-team", "meet-the-team",
]

PAGE_SKIP_KEYWORDS = [
    "careers", "jobs", "apply", "login", "signin", "sign-up", "newsletter",
    "privacy", "terms", "sitemap", "search", "blog", "news", "events",
    "publications", "insights", "resources", "faq", "accessibility",
]

# ---------------------------------------------------------------------------
# Person-name heuristics
# ---------------------------------------------------------------------------
NAME_STOPWORDS = {
    "home", "about", "attorneys", "lawyers", "team", "professionals",
    "people", "staff", "contact", "practice", "practices", "services",
    "intellectual", "property", "patent", "patents", "trademark",
    "trademarks", "news", "blog", "resources", "search", "login",
}

GENERIC_EMAIL_LOCALPARTS = {
    "info", "contact", "hello", "admin", "support", "office", "mail",
    "webmaster", "general", "inquiries", "reception",
}

# ---------------------------------------------------------------------------
# Excel column contracts
# ---------------------------------------------------------------------------
FIRM_COLUMNS = [
    "Record ID",
    "Firm Name",
    "Official Firm Website",
    "Directory Profile URL",
    "City",
    "State",
    "Country",
    "Intellectual Property Practice Area",
    "Public Phone (from directory)",
    "Source URL",
    "Discovered Date",
    "Status",
    "Duplicate Of",
    "Notes",
]

ATTORNEY_COLUMNS = [
    "Record ID",
    "Firm Name",
    "First Name",
    "Last Name",
    "Full Name",
    "Job Title / Designation",
    "Professional Email Address",
    "Email Verification Status",
    "Attorney or Patent Agent Type",
    "Patent/Trademark Practice Area",
    "Official Firm Website",
    "Individual Professional Profile URL",
    "LinkedIn Profile URL",
    "City",
    "State",
    "Country",
    "Public Business Phone",
    "Source URL for Name",
    "Source URL for Email",
    "Source URL for LinkedIn",
    "Date Collected",
    "Extraction Status",
    "Notes",
]

SUMMARY_COLUMNS = [
    "Metric",
    "Value",
    "Notes",
]

TODAY = __import__("datetime").datetime.utcnow().date().isoformat()
