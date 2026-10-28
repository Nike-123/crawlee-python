"""US IP law firm & attorney lead scraper.

Pipeline:
  1. Discover up to 100 unique IP law firms from the U.S. News directory
     (live or, when the directory blocks automated access, from snapshots).
  2. Crawl each firm's official website (robots.txt-checked, rate-limited).
  3. Extract individual professionals with e-mails, phones and LinkedIn URLs.
  4. Write Excel + CSV outputs and a scraping summary after every batch.
  5. Checkpoint after every batch so interrupted runs resume safely.

Windows usage:
    pip install -r requirements.txt
    python main.py              # test run (first 10 firms)
    python main.py --full       # full run (up to 100 firms)
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running both as `python main.py` (from the project folder) and as a
# module from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (  # noqa: E402
    ATTORNEYS_XLSX, CHECKPOINT_FILE, FIRMS_XLSX, MAX_FIRMS, SUMMARY_XLSX,
    TEST_FIRMS,
)
from directory import discover_firms, normalize_website, US_STATE_NAMES, STATE_ABBREV, US_STATES  # noqa: E402
from firm_crawler import RateLimitedSession, crawl_firm  # noqa: E402
import storage  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("ip_law_scraper")


def firm_status_label(status: str) -> str:
    return status


def run(max_firms: int = MAX_FIRMS, snapshot_dir=None, live: bool = False,
        resume: bool = True) -> dict:
    storage.init_visited_log()

    # ------------------------------------------------------------------
    # Stage 1: directory discovery (unless already checkpointed complete)
    # ------------------------------------------------------------------
    checkpoint = storage.load_checkpoint() if resume else None
    if checkpoint and checkpoint.get("directory_complete"):
        firms = checkpoint["firms"]
        directory_stats = checkpoint.get("directory_stats", {})
        log.info(
            "Resuming: %d firms already discovered (checkpoint).", len(firms)
        )
    else:
        log.info("Discovering firms from %s ...", snapshot_dir or "live directory")
        firms, directory_stats = discover_firms(
            snapshot_dir=snapshot_dir, max_firms=max_firms, live=live
        )
        log.info(
            "Directory discovery done: %d raw entries, %d unique firms, "
            "%d duplicates removed, mode=%s, blocked=%s",
            directory_stats.get("firms_raw", 0),
            len([f for f in firms if f.get("status") == "discovered"]),
            directory_stats.get("duplicates_removed", 0),
            directory_stats.get("mode", ""),
            directory_stats.get("blocked", False),
        )
        if directory_stats.get("blocked"):
            log.warning(
                "DIRECTORY BLOCKER: %s", directory_stats.get("blocker", "")
            )
        for f in firms:
            f["status"] = f.get("status") or "discovered"
            f.setdefault("pages_visited", 0)
            f.setdefault("pages_errors", 0)
            f.setdefault("blocked_reason", "")
        checkpoint = storage.fresh_checkpoint(firms, directory_stats)
        storage.save_checkpoint(checkpoint)
        storage.save_outputs(
            [dict(f, status=f["status"]) for f in firms], [], [],
        )

    discovered_firms = [f for f in firms if f.get("status") == "discovered"]
    todo = [f for f in discovered_firms if f.get("processing_status") != "done"]
    log.info("Firms to crawl: %d (of %d discovered).", len(todo), len(discovered_firms))

    # ------------------------------------------------------------------
    # Stage 2: crawl each firm website
    # ------------------------------------------------------------------
    session = RateLimitedSession()
    attorney_rows: list[dict] = []
    professionals_counter = 1

    def log_cb(stage, url, status_code, method, error, referrer=""):
        storage.log_visit(stage, url, status_code, method, error, referrer)

    batch = 0
    for idx, firm in enumerate(todo, start=1):
        firm_name = firm["firm_name"]
        website = firm.get("website_url", "")
        log.info(
            "[%d/%d] %s -- %s", idx, len(todo), firm_name, website or "(no website)"
        )

        if not website:
            firm["status"] = "inaccessible"
            firm["blocked_reason"] = "no website URL"
            firm["processing_status"] = "done"
            checkpoint["firms"] = firms
            checkpoint["next_firm_index"] = idx
            storage.save_checkpoint(checkpoint)
            storage.save_outputs(
                [dict(f) for f in firms], attorney_rows, []
            )
            continue
        try:
            result = crawl_firm(session, firm, log_cb)
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Unexpected error crawling %s", firm_name)
            firm["status"] = "inaccessible"
            firm["blocked_reason"] = f"unexpected error: {exc}"
            firm["processing_status"] = "done"
            storage.save_checkpoint(checkpoint)
            continue

        firm["pages_visited"] = result["pages_visited"]
        firm["pages_errors"] = result["pages_errors"]

        if result["status"] == "Blocked by robots.txt":
            firm["status"] = "robots_blocked"
            firm["blocked_reason"] = result["blocked_reason"]
        elif result["status"] in ("Blocked / Inaccessible", "Not Found"):
            firm["status"] = "inaccessible"
            firm["blocked_reason"] = result["blocked_reason"] or "no professionals extracted"
        else:
            firm["status"] = "processed"

        firm["processing_status"] = "done"

        # Attach record ids and counters to professionals.
        for prof in result["professionals"]:
            professionals_counter += 1
            prof["record_id"] = f"A-{professionals_counter:05d}"
            attorney_rows.append(prof)

        checkpoint["firms"] = firms
        checkpoint["professionals"] = attorney_rows
        checkpoint["next_firm_index"] = idx

        # Incremental save after every firm (cheap, guarantees resume safety).
        storage.save_checkpoint(checkpoint)
        discovered_rows = [dict(f) for f in firms]
        storage.save_outputs(discovered_rows, attorney_rows, [])

        batch += 1
        if batch % 1 == 0:
            log.info(
                "Checkpoint saved after firm %d/%d (%d professionals so far).",
                idx, len(todo), len(attorney_rows),
            )

    # ------------------------------------------------------------------
    # Stage 3: finalize firms sheet + summary
    # ------------------------------------------------------------------
    firms_rows = []
    for f in firms:
        state_raw = f.get("state", "")
        country = ""
        if state_raw:
            abbr = STATE_ABBREV.get(state_raw.lower(), "")
            if len(state_raw) == 2 and state_raw.upper() in US_STATES:
                abbr = state_raw.upper()
            country = "USA" if abbr else "International"
        firms_rows.append({
            "Record ID": f.get("record_id", ""),
            "Firm Name": f.get("firm_name", ""),
            "Official Firm Website": f.get("website_url", ""),
            "Directory Profile URL": f.get("directory_profile_url", ""),
            "City": f.get("city", ""),
            "State": f.get("state", ""),
            "Country": country,
            "Intellectual Property Practice Area": f.get("practice_areas", ""),
            "Public Phone (from directory)": f.get("public_phone_directory", ""),
            "Source URL": f.get("source_url", ""),
            "Discovered Date": f.get("discovered_date", ""),
            "Status": f.get("status", ""),
            "Duplicate Of": f.get("duplicate_of", ""),
            "Notes": f.get("blocked_reason", ""),
        })

    unique_firms = len([f for f in firms if f.get("record_id")])
    summary_rows = storage.compute_summary(
        firms_rows, attorney_rows, directory_stats,
        storage.VISITED_URLS_FILE, unique_firms=unique_firms,
    )
    storage.save_outputs(firms_rows, attorney_rows, summary_rows)

    log.info("=" * 70)
    log.info("RUN COMPLETE")
    log.info("Firms discovered: %d", len(firms_rows))
    log.info("Firms processed: %d", len([f for f in firms_rows if f["Status"] == "processed"]))
    log.info("Professionals extracted: %d", len(attorney_rows))
    log.info("Output: %s", FIRMS_XLSX)
    log.info("Output: %s", ATTORNEYS_XLSX)
    log.info("Output: %s", SUMMARY_XLSX)
    log.info("Log: %s", storage.VISITED_URLS_FILE)
    if directory_stats.get("blocked"):
        log.warning("LIMITATION: directory access was blocked: %s",
                    directory_stats.get("blocker", ""))
    return {
        "firms": firms_rows,
        "attorneys": attorney_rows,
        "summary": summary_rows,
        "directory_stats": directory_stats,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="US IP law firm & attorney lead scraper"
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Full run: process up to 100 firms (default: test run of 10).",
    )
    parser.add_argument(
        "--max-firms", type=int, default=None,
        help="Override the maximum number of firms (default 10 in test, 100 in full).",
    )
    parser.add_argument(
        "--snapshot-dir", default=None,
        help="Directory with saved U.S. News page snapshots (offline mode).",
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Attempt live access to law.usnews.com (only if not blocked).",
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="Ignore any existing checkpoint and start from scratch.",
    )
    args = parser.parse_args()

    if args.max_firms is not None:
        max_firms = min(args.max_firms, MAX_FIRMS)
    elif args.full:
        max_firms = MAX_FIRMS
    else:
        max_firms = TEST_FIRMS

    snapshot_dir = args.snapshot_dir
    if snapshot_dir is None:
        default_snapshots = Path(__file__).resolve().parent / "snapshots"
        if default_snapshots.exists():
            snapshot_dir = str(default_snapshots)

    result = run(
        max_firms=max_firms,
        snapshot_dir=snapshot_dir,
        live=args.live,
        resume=not args.no_resume,
    )

    # Honest exit summary.
    blocked = result["directory_stats"].get("blocked", False)
    if blocked:
        print("\nNOTE: The U.S. News directory blocks automated access from this")
        print("network (TLS/connection level). The run used saved directory")
        print("snapshots instead. See README.md for details and the compliant")
        print("alternative to re-enable live directory crawling.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
