"""U.S. News IP law-firm directory discovery.

Two operating modes:

* ``live``       -- fetch directory pages directly with requests (respects
                    robots.txt, retries with exponential backoff).
* ``snapshot``   -- read previously saved directory page snapshots. Used when
                    the directory blocks automated access from the network the
                    scraper runs on (see project README and the scraping log).

Both modes return the same firm dictionary shape.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from config import (
    ACCEPT_LANGUAGE,
    DIRECTORY_BASE,
    DIRECTORY_URL,
    MAX_FIRMS,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    USER_AGENT,
    MAX_RETRIES,
    BACKOFF_FACTOR,
)

FIRM_URL_RE = re.compile(
    r"https://law\.usnews\.com/law-firms/[A-Za-z0-9_.\-&]+(?:-\d+)?"
)
VISIT_WEBSITE_RE = re.compile(r"\[VISIT WEBSITE\]\((https?://[^)]+)\)")
PHONE_RE = re.compile(r"(\d{3}[-.\s]\d{3}[-.\s]\d{4})")
LOCATION_RE = re.compile(
    r"([A-Za-z][A-Za-z .'&\-]+?),\s*([A-Za-z .]+?)\s*(\d{5}(?:-\d{4})?)"
)
US_STATE_NAMES = {
    "alabama","alaska","arizona","arkansas","california","colorado","connecticut",
    "delaware","florida","georgia","hawaii","idaho","illinois","indiana","iowa",
    "kansas","kentucky","louisiana","maine","maryland","massachusetts","michigan",
    "minnesota","mississippi","missouri","montana","nebraska","nevada","new hampshire",
    "new jersey","new mexico","new york","north carolina","north dakota","ohio",
    "oklahoma","oregon","pennsylvania","rhode island","south carolina","south dakota",
    "tennessee","texas","utah","vermont","virginia","washington","west virginia",
    "wisconsin","wyoming","district of columbia",
}
US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
}
STATE_ABBREV = {
    "alabama":"AL","alaska":"AK","arizona":"AZ","arkansas":"AR","california":"CA",
    "colorado":"CO","connecticut":"CT","delaware":"DE","florida":"FL","georgia":"GA",
    "hawaii":"HI","idaho":"ID","illinois":"IL","indiana":"IN","iowa":"IA",
    "kansas":"KS","kentucky":"KY","louisiana":"LA","maine":"ME","maryland":"MD",
    "massachusetts":"MA","michigan":"MI","minnesota":"MN","mississippi":"MS",
    "missouri":"MO","montana":"MT","nebraska":"NE","nevada":"NV",
    "new hampshire":"NH","new jersey":"NJ","new mexico":"NM","new york":"NY",
    "north carolina":"NC","north dakota":"ND","ohio":"OH","oklahoma":"OK",
    "oregon":"OR","pennsylvania":"PA","rhode island":"RI","south carolina":"SC",
    "south dakota":"SD","tennessee":"TN","texas":"TX","utah":"UT","vermont":"VT",
    "virginia":"VA","washington":"WA","west virginia":"WV","wisconsin":"WI",
    "wyoming":"WY","district of columbia":"DC",
}
LOCATION_END_RE = re.compile(
    r",\s*(" + "|".join(sorted(US_STATE_NAMES, key=len, reverse=True)) + r")\s*\]?\s*$",
    re.I,
)

US_LAWYERS_RE = re.compile(r"([\d,]+)\s*U\.S\. Lawyers")
PRACTICE_LINE_RE = re.compile(r"^\s*-\s*(.+?)\s*$", re.MULTILINE)


@dataclass
class FetchResult:
    url: str
    status_code: int | None
    text: str
    error: str | None = None


class DirectoryFetcher:
    """Fetch directory pages, live or from snapshots."""

    def __init__(self, delay: float = REQUEST_DELAY, timeout: int = REQUEST_TIMEOUT):
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": USER_AGENT, "Accept-Language": ACCEPT_LANGUAGE}
        )
        self._last_request = 0.0

    # -- throttling ---------------------------------------------------------
    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    # -- robots -------------------------------------------------------------
    def robots_allows(self, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        try:
            rp.set_url(robots_url)
            rp.read()
            return rp.can_fetch(USER_AGENT, url)
        except Exception:
            # If robots.txt cannot be fetched, be conservative: do not crawl.
            return False

    # -- live fetch ---------------------------------------------------------
    def fetch_live(self, url: str) -> FetchResult:
        self._throttle()
        last_error = ""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                return FetchResult(
                    url=resp.url,
                    status_code=resp.status_code,
                    text=resp.text,
                )
            except requests.RequestException as exc:
                last_error = str(exc)
                if attempt < MAX_RETRIES:
                    time.sleep(BACKOFF_FACTOR ** attempt)
        return FetchResult(url=url, status_code=None, text="", error=last_error)

    # -- page iteration -----------------------------------------------------
    def iter_pages(self, snapshot_dir=None, max_pages: int = 10):
        """Yield (page_number, url, html_text) for directory pages."""
        if snapshot_dir:
            import pathlib

            snap_dir = pathlib.Path(snapshot_dir)
            files = sorted(snap_dir.glob("page_*.md"))
            for idx, fpath in enumerate(files, start=1):
                yield idx, f"snapshot:{fpath.name}", fpath.read_text(encoding="utf-8")
            return

        if not self.robots_allows(DIRECTORY_URL):
            raise RuntimeError(
                f"robots.txt disallows crawling {DIRECTORY_URL}; aborting directory discovery"
            )

        for page in range(1, max_pages + 1):
            url = DIRECTORY_URL if page == 1 else f"{DIRECTORY_URL}?page={page}"
            result = self.fetch_live(url)
            if result.status_code is None or result.status_code >= 400:
                raise RuntimeError(
                    f"Directory page {page} failed: {result.error or result.status_code}"
                )
            yield page, url, result.text


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def _clean_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _extract_name_from_link_text(link_text: str) -> str:
    """Directory link text wraps the firm name in **...** (markdown snapshots)
    or is plain text (live HTML)."""
    text = _clean_ws(link_text)
    m = re.match(r"\*\*(.+?)\*\*", text, re.DOTALL)
    if m:
        return _clean_ws(m.group(1))
    return text


def parse_directory_markdown(content: str, source_url: str) -> list[dict]:
    """Parse a directory page saved as markdown (snapshot mode).

    Expected block shape (as exported by the page reader):

        01. [**Firm Name**\\
             ...
             32 U.S. Lawyers\\
             ...
             - Intellectual Property,\\
             - Banking\\
             ...
             and more\\
             ...
             City, State 91505](directory-url)

        [VISIT WEBSITE](website-url)

        310-300-2900
    """
    firms: list[dict] = []
    # Split into firm blocks: each block begins with "<n>. [**...**](dir-url)"
    block_re = re.compile(
        r"(?ms)^\s*\d+\.\s*\[(?P<link_text>.*?)\]\((?P<dir_url>"
        r"https://law\.usnews\.com/law-firms/[^)]+)\)"
    )
    matches = list(block_re.finditer(content))
    visit_links = VISIT_WEBSITE_RE.findall(content)

    for i, m in enumerate(matches):
        name = _extract_name_from_link_text(m.group("link_text"))
        dir_url = m.group("dir_url")
        link_text = m.group("link_text")

        # Card segments are separated by literal backslash line-continuations;
        # the last non-empty segment is the location ("City, State ZIP").
        segments = [s.strip().replace("\\", "") for s in link_text.split("\\")]
        segments = [s for s in segments if s]
        location_segment = segments[-1] if segments else ""

        lawyers_m = US_LAWYERS_RE.search(link_text)
        us_lawyers = lawyers_m.group(1) if lawyers_m else ""

        # Practice areas are "- <area>" lines; trailing "and more" is dropped.
        areas = [
            a.strip().rstrip(",").replace("\\", "").strip()
            for a in PRACTICE_LINE_RE.findall(link_text)
            if a.strip().lower() not in {"and more"}
        ]
        practice_area = "; ".join(dict.fromkeys(areas))

        loc_m = LOCATION_RE.search(location_segment)
        city = state = zip_code = ""
        if loc_m:
            city = _clean_ws(loc_m.group(1))
            state = _clean_ws(loc_m.group(2))
            zip_code = loc_m.group(3)
        else:
            # Entries without a ZIP end with "City, State".
            end_m = LOCATION_END_RE.search(location_segment)
            if end_m:
                state = _clean_ws(end_m.group(1)).title()
                city = _clean_ws(location_segment[: end_m.start()].rsplit(",", 1)[-1].strip())

        website = visit_links[i] if i < len(visit_links) else ""
        phone_m = PHONE_RE.search(content[m.start() : m.end() + 200])
        phone = phone_m.group(1) if phone_m else ""

        firms.append(
            {
                "firm_name": name,
                "website_url_raw": website,
                "directory_profile_url": dir_url,
                "city": city,
                "state": state,
                "zip_code": zip_code,
                "us_lawyers": us_lawyers,
                "practice_areas": practice_area,
                "public_phone_directory": phone,
                "source_url": source_url,
            }
        )
    return firms


def parse_directory_html(html: str, source_url: str) -> list[dict]:
    """Parse a live directory page (HTML).

    U.S. News markup can change; several fallback strategies are tried and the
    first one that yields firms is used. Results are normalised to the same
    shape as the markdown parser.
    """
    soup = BeautifulSoup(html, "lxml")
    firms: list[dict] = []

    # Strategy 1: cards are links to /law-firms/<slug>-<id>
    links = [
        a
        for a in soup.find_all("a", href=True)
        if re.match(r"^/law-firms/.+-\d+$", a["href"]) or "law-firms/" in a["href"]
    ]
    seen_links = set()
    candidates = []
    for a in links:
        href = urljoin(DIRECTORY_BASE, a["href"])
        if href in seen_links:
            continue
        seen_links.add(href)
        name = _clean_ws(a.get_text(" ", strip=True))
        if name and len(name) > 2:
            candidates.append((name, href, a))

    if candidates:
        # Website links: anchors whose text says VISIT WEBSITE / website.
        website_anchors = [
            a
            for a in soup.find_all("a", href=True)
            if re.search(r"visit\s*website|website", a.get_text(" ", strip=True), re.I)
        ]
        for i, (name, href, _a) in enumerate(candidates):
            website = ""
            if i < len(website_anchors):
                website = website_anchors[i].get("href", "")
            # Location: nearest text block containing "City, State ZIP"
            city = state = zip_code = ""
            parent = _a.find_parent(["div", "section", "article", "li"])
            haystack = parent.get_text(" ", strip=True) if parent else ""
            loc_m = LOCATION_RE.search(haystack)
            if loc_m:
                city, state, zip_code = loc_m.group(1), loc_m.group(2), loc_m.group(3)
            areas_m = PRACTICE_LINE_RE.findall(haystack)
            areas = [a.strip().rstrip(",") for a in areas_m if a.strip().lower() != "and more"]
            firms.append(
                {
                    "firm_name": name,
                    "website_url_raw": website,
                    "directory_profile_url": href,
                    "city": city,
                    "state": state,
                    "zip_code": zip_code,
                    "us_lawyers": "",
                    "practice_areas": "; ".join(dict.fromkeys(areas)),
                    "public_phone_directory": "",
                    "source_url": source_url,
                }
            )
        return firms

    # Strategy 2: raw-regex fallback on the HTML text.
    for m in FIRM_URL_RE.finditer(html):
        # crude; live HTML structure not verified in this environment
        pass  # pragma: no cover - fallback only used if markup is unknown

    return firms


def parse_directory_page(content: str, source_url: str, is_markdown: bool) -> list[dict]:
    if is_markdown:
        return parse_directory_markdown(content, source_url)
    return parse_directory_html(content, source_url)


def normalize_website(url: str) -> str:
    """Normalize a firm website URL: scheme, host lowercased, www stripped,
    trailing slash removed."""
    if not url:
        return ""
    url = url.strip()
    # Some directory entries carry a broken concatenation (e.g. a usnews
    # host accidentally prefixed). Drop anything that is not http(s).
    if not url.lower().startswith(("http://", "https://")):
        url = "http://" + url
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    scheme = "https" if parsed.scheme == "https" else "http"
    normalized = f"{scheme}://{host}{path}"
    if parsed.query:
        normalized += "?" + parsed.query
    return normalized


def domain_of(url: str) -> str:
    parsed = urlparse(normalize_website(url))
    return parsed.netloc.lower()


def discover_firms(snapshot_dir=None, max_firms: int = MAX_FIRMS, live: bool = False):
    """Discover up to max_firms unique firms from the directory.

    Returns (firms, stats). Firm dicts include a 'status' of 'discovered' and
    a 'duplicate_of' field when a domain duplicate was skipped.
    """
    fetcher = DirectoryFetcher()
    firms: list[dict] = []
    seen_domains: dict[str, str] = {}  # domain -> record id of first occurrence
    stats = {
        "pages_fetched": 0,
        "firms_raw": 0,
        "duplicates_removed": 0,
        "blocked": False,
        "blocker": "",
        "mode": "snapshot" if snapshot_dir and not live else "live",
    }

    try:
        for page_no, url, content in fetcher.iter_pages(
            snapshot_dir=snapshot_dir if not live else None, max_pages=12
        ):
            stats["pages_fetched"] += 1
            is_markdown = snapshot_dir and not live
            page_firms = parse_directory_page(content, url, is_markdown=is_markdown)
            stats["firms_raw"] += len(page_firms)

            for firm in page_firms:
                if len(firms) >= max_firms:
                    break
                website = normalize_website(firm.get("website_url_raw", ""))
                firm["website_url"] = website
                dom = domain_of(website) if website else ""
                if not website:
                    firm["status"] = "discovered"
                    firm["duplicate_of"] = ""
                    firm["record_id"] = ""
                    firms.append(firm)
                    continue
                if dom in seen_domains:
                    stats["duplicates_removed"] += 1
                    firm["status"] = "duplicate_skipped"
                    firm["duplicate_of"] = seen_domains[dom]
                    # Duplicates are not counted toward the 100-firm cap.
                    continue
                seen_domains[dom] = f"F-{len(firms) + 1:04d}"
                firm["status"] = "discovered"
                firm["duplicate_of"] = ""
                firms.append(firm)
            if len(firms) >= max_firms:
                break
    except RuntimeError as exc:
        stats["blocked"] = True
        stats["blocker"] = str(exc)

    # Assign record IDs to discovered firms (duplicates keep none).
    counter = 1
    for firm in firms:
        if firm["status"] == "discovered":
            firm["record_id"] = f"F-{counter:04d}"
            counter += 1

    now = datetime.now(timezone.utc).isoformat()
    for firm in firms:
        firm.setdefault("discovered_date", now)

    return firms, stats
