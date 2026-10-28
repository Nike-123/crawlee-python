"""Crawl each firm's official website and extract individual professionals.

Design constraints from the task:
* Respect robots.txt (urllib.robotparser) -- never crawl disallowed paths.
* One record per individual professional; never invent emails or LinkedIn URLs.
* Associate an e-mail with a person only when the page supports it.
* General firm e-mails (info@, contact@, ...) are never assigned to an attorney.
* Conservative delays, timeouts, retries with exponential backoff.
* Every visited URL is logged with timestamp, HTTP status and error.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from config import (
    BACKOFF_FACTOR,
    DEFAULT_ROLE,
    EMAIL_STATUS_NOT_FOUND,
    EMAIL_STATUS_PUBLISHED,
    EXTRACTION_BLOCKED,
    EXTRACTION_NOT_FOUND,
    EXTRACTION_PARTIAL,
    EXTRACTION_SUCCESS,
    EXTRACTION_ROBOTS_BLOCKED,
    GENERIC_EMAIL_LOCALPARTS,
    MAX_PAGES_PER_FIRM,
    PAGE_KEYWORDS,
    PAGE_SKIP_KEYWORDS,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    ROLE_RULES,
    USER_AGENT,
)
from directory import US_STATES

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9._%+\-]+\.[A-Z]{2,}", re.I)
MAILTO_RE = re.compile(r"^mailto:([^?]+)", re.I)
PHONE_RE = re.compile(r"\+?\d[\d\-.\s()]{7,}\d")
LINKEDIN_RE = re.compile(r"https?://(www\.)?linkedin\.com/in/[A-Za-z0-9._\-]+/?")

HEADING_TAGS = re.compile(r"^h[1-6]$", re.I)

ROLE_STOPWORDS = {
    "home", "about", "attorneys", "lawyers", "counsel", "team", "professionals",
    "people", "staff", "contact", "practices", "practice", "services", "news",
    "blog", "resources", "search", "login", "menu", "close", "toggle",
}


class RateLimitedSession:
    """requests session with per-domain delay, retries and visit logging."""

    def __init__(self, delay: float = REQUEST_DELAY, timeout: int = REQUEST_TIMEOUT,
                 log_cb=None):
        self.delay = delay
        self.timeout = timeout
        self.log_cb = log_cb or (lambda *a, **k: None)
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
        )
        self._last_request = 0.0
        self._robot_cache: dict[str, RobotFileParser | None] = {}

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def robots_allows(self, url: str) -> bool | None:
        """True = allowed, False = disallowed, None = robots.txt unreachable."""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robot_cache:
            rp = RobotFileParser()
            try:
                rp.set_url(base + "/robots.txt")
                rp.read()
                self._robot_cache[base] = rp
            except Exception:
                self._robot_cache[base] = None
        rp = self._robot_cache[base]
        if rp is None:
            return None
        try:
            return rp.can_fetch(USER_AGENT, url)
        except Exception:
            return None

    def get(self, url: str, stage: str = "firm", referrer: str = ""):
        """GET a URL; return (response_or_none, status_code, error).

        Every attempt is recorded through log_cb.
        """
        self._throttle()
        last_error = ""
        for attempt in range(1, 4):
            try:
                self._last_request = time.monotonic()
                resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                self.log_cb(
                    stage=stage,
                    url=resp.url,
                    status_code=resp.status_code,
                    method="GET",
                    error="",
                    referrer=referrer,
                )
                if resp.status_code < 400 or resp.status_code in (401, 403):
                    return resp, resp.status_code, ""
                last_error = f"HTTP {resp.status_code}"
            except requests.RequestException as exc:
                last_error = str(exc)
                self.log_cb(
                    stage=stage,
                    url=url,
                    status_code=None,
                    method="GET",
                    error=last_error,
                    referrer=referrer,
                )
            if attempt < 3:
                time.sleep(BACKOFF_FACTOR ** attempt)
        self.log_cb(
            stage=stage,
            url=url,
            status_code=None,
            method="GET",
            error=last_error,
            referrer=referrer,
        )
        return None, None, last_error


def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    url, _ = urldefrag(url)
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
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


def same_domain(url_a: str, url_b: str) -> bool:
    return urlparse(normalize_url(url_a)).netloc == urlparse(normalize_url(url_b)).netloc


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text or "")).strip()


def looks_like_person_name(text: str) -> bool:
    """Heuristic: 2-5 title-cased words, no digits, not a navigation label."""
    text = clean_text(text)
    if not text or len(text) < 3 or len(text) > 80:
        return False
    if any(ch.isdigit() for ch in text):
        return False
    words = text.split()
    if len(words) < 2 or len(words) > 5:
        return False
    if any(w.lower() in ROLE_STOPWORDS for w in words):
        return False
    # Every word should start with a capital letter (allow 'Mc', 'Van', etc.)
    if not all(w[0].isalpha() and w[0].isupper() for w in words):
        return False
    return True


def classify_role(title: str) -> str:
    title_l = (title or "").lower()
    for role, keywords in ROLE_RULES:
        if all(kw in title_l for kw in keywords):
            return role
    # Generic attorney/lawyer without IP keywords still counts as legal professional.
    if any(k in title_l for k in ["attorney", "lawyer", "counsel", "agent"]):
        return DEFAULT_ROLE
    return DEFAULT_ROLE


def extract_practice_areas(title: str, page_text: str) -> str:
    found = []
    for area in ["patent", "trademark", "copyright", "intellectual property", "ip "]:
        if area in (title or "").lower() or area in page_text.lower():
            label = "IP" if area.strip() == "ip" else area.title()
            if label not in found:
                found.append(label)
    return "; ".join(found)


def extract_emails(text: str) -> list[str]:
    return [m.group(0).lower() for m in EMAIL_RE.finditer(text or "")]


def is_general_email(email: str) -> bool:
    local = email.split("@")[0].lower()
    return local in GENERIC_EMAIL_LOCALPARTS


def extract_phones(text: str) -> list[str]:
    phones = [m.group(0) for m in PHONE_RE.finditer(text or "")]
    # Normalise spaces/dashes lightly and de-duplicate preserving order.
    seen, out = set(), []
    for p in phones:
        norm = re.sub(r"\s+", " ", p).strip()
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out[:5]


def extract_linkedins(text_or_html: str) -> list[str]:
    return list(dict.fromkeys(LINKEDIN_RE.findall(text_or_html or "")))


def split_name(full: str) -> tuple[str, str]:
    parts = full.split()
    if not parts:
        return "", ""
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    return first, last


def _block_text(element) -> str:
    return clean_text(element.get_text(" ", strip=True))


def extract_people_from_page(soup: BeautifulSoup, page_url: str, firm: dict) -> list[dict]:
    """Extract person records from a single page.

    A person record is built around a heading that looks like a person's name;
    everything up to the next heading is treated as that person's block so that
    e-mails, phones and LinkedIn URLs are attributed only when they appear
    inside the same block.
    """
    professionals: list[dict] = []
    now = datetime.now(timezone.utc).date().isoformat()

    # Collect headings in document order.
    headings = [h for h in soup.find_all(HEADING_TAGS)]
    name_headings = [h for h in headings if looks_like_person_name(_block_text(h))]

    # Also consider elements whose classes suggest a person card even if the
    # name is not in a heading (e.g. a div.card > h3.name handled above;
    # here we catch <span class="name"> inside non-heading tags).
    if not name_headings:
        for elem in soup.find_all(["div", "li", "section", "article"]):
            txt = _block_text(elem)
            if looks_like_person_name(txt) and len(txt.split()) <= 5:
                name_headings.append(elem)

    if name_headings:
        for idx, heading in enumerate(name_headings):
            name = clean_text(_block_text(heading))
            # Block = heading text + following siblings until next heading,
            # bounded so we do not swallow the whole page.
            block_parts = [name]
            node = heading.find_next_sibling()
            depth = 0
            while node is not None and depth < 12:
                if node.name and HEADING_TAGS.match(node.name):
                    break
                block_parts.append(_block_text(node))
                node = node.find_next_sibling()
                depth += 1
            block = " ".join(block_parts)

            title = ""
            # Title guess: shortest meaningful line right after the name.
            for line in [clean_text(x) for x in block.split("|") if x.strip()]:
                if line == name:
                    continue
                if 2 <= len(line) <= 90 and not any(
                    s in line.lower() for s in ["@", "http", "linkedin"]
                ):
                    title = line
                    break

            emails = extract_emails(block)
            personal_email = next((e for e in emails if not is_general_email(e)), "")
            if not personal_email and emails:
                personal_email = ""  # general only -> not assigned to a person

            phones = extract_phones(block)
            linkedins = extract_linkedins(block)

            role = classify_role(title)
            practice = extract_practice_areas(title, block)
            linkedin = linkedins[0] if linkedins else ""

            prof = {
                "firm_name": firm["firm_name"],
                "first_name": "",
                "last_name": "",
                "full_name": name,
                "job_title": title,
                "email": personal_email.lower() if personal_email else "",
                "email_verification_status": (
                    EMAIL_STATUS_PUBLISHED if personal_email else EMAIL_STATUS_NOT_FOUND
                ),
                "email_source_url": page_url if personal_email else "",
                "attorney_or_agent_type": role,
                "patent_trademark_practice_area": practice,
                "official_firm_website": firm["website_url"],
                "individual_profile_url": page_url,
                "linkedin_url": linkedin,
                "linkedin_source_url": page_url if linkedin else "",
                "city": firm.get("city", ""),
                "state": firm.get("state", ""),
                "country": firm.get("country", ""),
                "public_business_phone": phones[0] if phones else "",
                "phone_source_url": page_url if phones else "",
                "source_url_for_name": page_url,
                "source_url_for_email": page_url if personal_email else "",
                "source_url_for_linkedin": page_url if linkedin else "",
                "date_collected": now,
                "extraction_status": (
                    EXTRACTION_SUCCESS if name else EXTRACTION_NOT_FOUND
                ),
                "notes": "",
            }
            prof["first_name"], prof["last_name"] = split_name(name)
            professionals.append(prof)

    else:
        # Fallback: page-level scan for name-title pairs in plain text.
        text = soup.get_text(" ", strip=True)
        for m in re.finditer(
            r"([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,3})\s*[,\-]\s*"
            r"([A-Z][A-Za-z&\- ]{2,70}?)(?:\s*(?:\||\u2022|\d|$))",
            text,
        ):
            name = clean_text(m.group(1))
            title = clean_text(m.group(2))
            if not looks_like_person_name(name):
                continue
            emails = extract_emails(text)
            personal_email = next((e for e in emails if not is_general_email(e)), "")
            linkedins = extract_linkedins(text)
            prof = {
                "firm_name": firm["firm_name"],
                "first_name": "",
                "last_name": "",
                "full_name": name,
                "job_title": title,
                "email": personal_email.lower() if personal_email else "",
                "email_verification_status": (
                    EMAIL_STATUS_PUBLISHED if personal_email else EMAIL_STATUS_NOT_FOUND
                ),
                "email_source_url": page_url if personal_email else "",
                "attorney_or_agent_type": classify_role(title),
                "patent_trademark_practice_area": extract_practice_areas(title, text),
                "official_firm_website": firm["website_url"],
                "individual_profile_url": page_url,
                "linkedin_url": linkedins[0] if linkedins else "",
                "linkedin_source_url": page_url if linkedins else "",
                "city": firm.get("city", ""),
                "state": firm.get("state", ""),
                "country": firm.get("country", ""),
                "public_business_phone": "",
                "phone_source_url": page_url if extract_phones(text) else "",
                "source_url_for_name": page_url,
                "source_url_for_email": page_url if personal_email else "",
                "source_url_for_linkedin": page_url if linkedins else "",
                "date_collected": now,
                "extraction_status": EXTRACTION_PARTIAL,
                "notes": "Extracted from page text (no structured name heading).",
            }
            prof["first_name"], prof["last_name"] = split_name(name)
            professionals.append(prof)

    return professionals


def discover_pages(session: RateLimitedSession, firm: dict, log_cb) -> list[str]:
    """Return candidate attorney/team pages for a firm (homepage first)."""
    homepage = firm["website_url"]
    if not homepage:
        return []

    if not session.robots_allows(homepage):
        log_cb(stage="firm", url=homepage, status_code=None, method="GET",
               error="disallowed by robots.txt", referrer="")
        return []

    resp, status, error = session.get(homepage, stage="homepage")
    if resp is None:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    base = resp.url
    candidates: dict[str, int] = {}  # url -> score

    def consider(url: str, text: str, boost: int = 0) -> None:
        url = normalize_url(url)
        if not url or not same_domain(base, url):
            return
        low = (text + " " + urlparse(url).path).lower()
        if any(k in low for k in PAGE_SKIP_KEYWORDS):
            return
        score = sum(1 for k in PAGE_KEYWORDS if k in low) + boost
        if score > 0:
            candidates[url] = max(candidates.get(url, 0), score)

    for a in soup.find_all("a", href=True):
        consider(urljoin(base, a["href"]), a.get_text(" ", strip=True))

    # Sitemap discovery.
    sm_resp, _, _ = session.get(base.rstrip("/") + "/sitemap.xml", stage="sitemap")
    if sm_resp is not None and sm_resp.status_code == 200:
        for m in re.finditer(r"<loc>(.*?)</loc>", sm_resp.text, re.I | re.S):
            consider(m.group(1), "")

    # Sort: highest score first, then shortest URL (homepage-like first).
    ordered = sorted(candidates, key=lambda u: (-candidates[u], len(u)))
    # Always include homepage itself at the front.
    ordered = [normalize_url(base)] + [u for u in ordered if u != normalize_url(base)]
    return ordered[: MAX_PAGES_PER_FIRM + 1]


def crawl_firm(session: RateLimitedSession, firm: dict, log_cb) -> dict:
    """Crawl one firm website. Returns a result dict with professionals."""
    result = {
        "firm": firm,
        "professionals": [],
        "status": EXTRACTION_NOT_FOUND,
        "pages_visited": 0,
        "pages_errors": 0,
        "blocked_reason": "",
    }

    homepage = firm.get("website_url", "")
    if not homepage:
        result["status"] = EXTRACTION_NOT_FOUND
        result["blocked_reason"] = "no website URL in directory"
        return result

    robots = session.robots_allows(homepage)
    if robots is False:
        result["status"] = EXTRACTION_ROBOTS_BLOCKED
        result["blocked_reason"] = "robots.txt disallows homepage"
        return result
    if robots is None:
        result["status"] = EXTRACTION_BLOCKED
        result["blocked_reason"] = "robots.txt unreachable; crawl skipped conservatively"
        return result

    pages = discover_pages(session, firm, log_cb)
    if not pages:
        result["status"] = EXTRACTION_BLOCKED
        result["blocked_reason"] = "homepage could not be fetched"
        return result

    seen_names: dict[tuple, dict] = {}  # dedupe key -> professional

    for page_url in pages:
        page_robots = session.robots_allows(page_url)
        if page_robots is False:
            log_cb(stage="attorney_page", url=page_url, status_code=None,
                   method="GET", error="disallowed by robots.txt", referrer=homepage)
            result["pages_errors"] += 1
            continue
        resp, status, error = session.get(page_url, stage="attorney_page",
                                          referrer=homepage)
        if resp is None:
            result["pages_errors"] += 1
            continue
        result["pages_visited"] += 1

        soup = BeautifulSoup(resp.text, "lxml")
        people = extract_people_from_page(soup, page_url, firm)
        page_text = clean_text(soup.get_text(" ", strip=True))

        # Page-level general e-mails / phones (not person-attributed) are kept
        # as notes on the firm; individuals were already created above.
        _ = extract_emails(page_text)
        _ = extract_phones(page_text)

        for prof in people:
            key = (
                prof["full_name"].lower(),
                prof["firm_name"].lower(),
                prof["email"],
                prof["individual_profile_url"],
            )
            if key in seen_names:
                existing = seen_names[key]
                # Merge: fill empty fields from the newer record.
                for fld in ("job_title", "email", "linkedin_url",
                            "public_business_phone", "patent_trademark_practice_area"):
                    if not existing.get(fld) and prof.get(fld):
                        existing[fld] = prof[fld]
                        if fld == "email":
                            existing["email_source_url"] = prof["email_source_url"]
                        if fld == "linkedin_url":
                            existing["linkedin_source_url"] = prof["linkedin_source_url"]
                continue
            seen_names[key] = prof
            result["professionals"].append(prof)

    if result["professionals"]:
        result["status"] = EXTRACTION_SUCCESS
    elif result["pages_errors"] == len(pages) and pages:
        result["status"] = EXTRACTION_BLOCKED
    else:
        result["status"] = EXTRACTION_NOT_FOUND
    return result
