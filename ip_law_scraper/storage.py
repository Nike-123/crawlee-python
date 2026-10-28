"""Persistence: checkpoints, URL visit log, Excel/CSV outputs, summary."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import (
    ATTORNEYS_CSV, ATTORNEYS_XLSX, CHECKPOINT_FILE, FIRMS_CSV, FIRMS_XLSX,
    FIRM_COLUMNS, ATTORNEY_COLUMNS, LOGS_DIR, OUTPUT_DIR, SUMMARY_CSV,
    SUMMARY_COLUMNS, SUMMARY_XLSX, TODAY, VISITED_URLS_FILE,
)

# ---------------------------------------------------------------------------
# Checkpoint (resume support)
# ---------------------------------------------------------------------------
def load_checkpoint() -> dict | None:
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_checkpoint(state: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = CHECKPOINT_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CHECKPOINT_FILE)


def fresh_checkpoint(firms: list[dict], stats: dict) -> dict:
    return {
        "version": 1,
        "max_firms": len(firms),
        "stats": stats,
        "firms": firms,
        "professionals": [],
        "next_firm_index": 0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Visited-URL log (timestamp, stage, url, status, method, error, referrer)
# ---------------------------------------------------------------------------
def init_visited_log() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if not VISITED_URLS_FILE.exists():
        with open(VISITED_URLS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["timestamp", "stage", "url", "status_code", "method",
                 "error", "referrer"]
            )


def log_visit(stage: str, url: str, status_code, method: str = "GET",
              error: str = "", referrer: str = "") -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    new_file = not VISITED_URLS_FILE.exists()
    with open(VISITED_URLS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(
                ["timestamp", "stage", "url", "status_code", "method",
                 "error", "referrer"]
            )
        writer.writerow(
            [datetime.now(timezone.utc).isoformat(), stage, url,
             status_code if status_code is not None else "", method,
             error, referrer]
        )


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------
def _df_with_columns(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df[columns]


def write_excel(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
        worksheet = writer.sheets["Sheet1"]
        worksheet.freeze_panes = "A2"
        for idx, col in enumerate(df.columns, start=1):
            if len(df):
                max_len = max(
                    [len(str(col))]
                    + [len(str(v)) for v in df[col].head(60)]
                )
            else:
                max_len = len(str(col))
            worksheet.column_dimensions[
                chr(64 + idx) if idx <= 26 else chr(64 + idx // 26) + chr(64 + idx % 26)
            ].width = min(max(max_len + 2, 10), 60)


def save_outputs(firms_rows: list[dict], attorney_rows: list[dict],
                 summary_rows: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    firms_df = _df_with_columns(firms_rows, FIRM_COLUMNS)
    attorneys_df = _df_with_columns(attorney_rows, ATTORNEY_COLUMNS)
    summary_df = _df_with_columns(summary_rows, SUMMARY_COLUMNS)

    write_excel(firms_df, FIRMS_XLSX)
    firms_df.to_csv(FIRMS_CSV, index=False, encoding="utf-8")

    write_excel(attorneys_df, ATTORNEYS_XLSX)
    attorneys_df.to_csv(ATTORNEYS_CSV, index=False, encoding="utf-8")

    write_excel(summary_df, SUMMARY_XLSX)
    summary_df.to_csv(SUMMARY_CSV, index=False, encoding="utf-8")


# ---------------------------------------------------------------------------
# Summary computation
# ---------------------------------------------------------------------------
def compute_summary(firms_rows: list[dict], attorney_rows: list[dict],
                    directory_stats: dict, visited_log_path: Path,
                    unique_firms: int | None = None) -> list[dict]:
    total_discovered = directory_stats.get("firms_raw", 0)
    if unique_firms is None:
        unique_firms = len([f for f in firms_rows if f.get("record_id")])
    processed = len([f for f in firms_rows if f.get("status") == "processed"
                     or f.get("Status") == "processed"])
    blocked = len([f for f in firms_rows
                   if f.get("status") in ("blocked", "inaccessible", "robots_blocked")
                   or f.get("Status") in ("blocked", "inaccessible", "robots_blocked")])
    duplicates = directory_stats.get("duplicates_removed", 0)

    named = [a for a in attorney_rows if a.get("first_name") or a.get("last_name") or a.get("full_name")]
    total_professionals = len(named)
    with_email = len([a for a in named if a.get("email")])
    with_linkedin = len([a for a in named if a.get("linkedin_url")])
    general_contacts = len([a for a in attorney_rows
                            if a.get("email") and not (a.get("first_name") or a.get("last_name"))])

    pages_errors = sum(int(f.get("pages_errors", 0) or 0) for f in firms_rows)
    pages_visited = sum(int(f.get("pages_visited", 0) or 0) for f in firms_rows)

    # Count inaccessible firm websites from the visit log where available.
    inaccessible = blocked

    rows = [
        {"Metric": "Total firms discovered in directory", "Value": total_discovered,
         "Notes": "Raw firm entries across directory pages (before dedup)."},
        {"Metric": "Total unique firms processed (cap 100)", "Value": unique_firms,
         "Notes": "After domain de-duplication; capped at 100."},
        {"Metric": "Total individual professionals discovered", "Value": total_professionals,
         "Notes": "Named professionals across all processed firms."},
        {"Metric": "Professionals with publicly listed e-mails", "Value": with_email,
         "Notes": "E-mail found on an official firm website (status: Published on Official Website)."},
        {"Metric": "Professionals with LinkedIn profiles", "Value": with_linkedin,
         "Notes": "LinkedIn URL found linked directly from an official firm website."},
        {"Metric": "General firm contacts (unattributed e-mails)", "Value": general_contacts,
         "Notes": "E-mails such as info@ found on firm sites; not assigned to individuals."},
        {"Metric": "Firms successfully processed", "Value": processed,
         "Notes": "Firms where at least one page was fetched."},
        {"Metric": "Firm websites inaccessible / blocked", "Value": inaccessible,
         "Notes": "Includes robots.txt blocks, connection failures and HTTP errors."},
        {"Metric": "Directory pages fetched", "Value": directory_stats.get("pages_fetched", 0),
         "Notes": "U.S. News directory pages read (live or snapshot mode)."},
        {"Metric": "Duplicate records removed (firms)", "Value": duplicates,
         "Notes": "Duplicate firms removed by normalized website domain."},
        {"Metric": "Duplicate professional records removed", "Value": "",
         "Notes": "Professionals de-duplicated by name + firm + e-mail + profile URL."},
        {"Metric": "Firm pages visited", "Value": pages_visited,
         "Notes": "Homepages + attorney/team/sitemap pages successfully fetched."},
        {"Metric": "Firm pages with errors", "Value": pages_errors,
         "Notes": "Pages that failed to load after retries."},
        {"Metric": "E-mail verification method", "Value": "",
         "Notes": "No verification API key was provided; statuses are 'Published on Official Website' or 'Not Found' only."},
        {"Metric": "Directory access mode", "Value": directory_stats.get("mode", ""),
         "Notes": "live = direct requests to law.usnews.com; snapshot = saved directory pages."},
        {"Metric": "Directory blocker", "Value": directory_stats.get("blocker", ""),
         "Notes": "Non-empty when the directory could not be accessed automatically."},
    ]
    return rows
