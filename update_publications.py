#!/usr/bin/env python3
"""
update_publications.py
──────────────────────
Fetches all publications from Nadia Metoui's ORCID public profile
and updates the FALLBACK_PUBS list in index.html.

Usage:
  python update_publications.py

Requirements:
  pip install requests

Run this script whenever you want to sync your ORCID publications
into the website's fallback list (e.g. after adding a new paper to ORCID).
The website already auto-fetches from ORCID on page load — this script
updates the hardcoded fallback so the site still works offline or if
ORCID is temporarily unavailable.
"""

import json
import re
import sys
import requests

ORCID_ID   = "0000-0001-6690-2937"
ORCID_BASE = f"https://pub.orcid.org/v3.0/{ORCID_ID}"
HEADERS    = {"Accept": "application/json"}
INDEX_FILE = "index.html"


# ── Helpers ──────────────────────────────────────────────────────────────────

def orcid_type_to_local(work_type: str) -> str:
    journals = {"journal-article", "book-chapter", "book", "report"}
    talks    = {"conference-abstract", "lecture-speech", "other"}
    if work_type in journals: return "journal"
    if work_type in talks:    return "talk"
    return "conference"

def badge_from_type(local_type: str, work_type: str) -> str:
    if local_type == "journal":    return "Journal"
    if local_type == "talk":       return "Abstract" if work_type == "conference-abstract" else "Talk"
    return "Conference"

def shorten_name(full_name: str) -> str:
    """'Nadia Metoui' → 'N. Metoui'"""
    parts = full_name.strip().split()
    if len(parts) > 1:
        return parts[0][0] + ". " + " ".join(parts[1:])
    return full_name


# ── Fetch from ORCID ─────────────────────────────────────────────────────────

def fetch_publications() -> list[dict]:
    print(f"Fetching works for ORCID {ORCID_ID}…")
    r = requests.get(f"{ORCID_BASE}/works", headers=HEADERS, timeout=15)
    r.raise_for_status()
    groups = r.json().get("group", [])
    print(f"  Found {len(groups)} work group(s)")

    publications = []
    for g in groups:
        summary  = g["work-summary"][0]
        put_code = summary["put-code"]
        work_type = summary.get("type", "")
        local_type = orcid_type_to_local(work_type)

        title  = summary.get("title", {}).get("title", {}).get("value", "Untitled")
        year   = (summary.get("publication-date") or {}).get("year", {}).get("value", "") or ""
        venue  = (summary.get("journal-title") or {}).get("value", "") or ""

        # Fetch full record for DOI / URL and contributor list
        url        = ""
        authors_str = ""
        try:
            dr = requests.get(f"{ORCID_BASE}/work/{put_code}", headers=HEADERS, timeout=10)
            if dr.ok:
                detail = dr.json()
                ext_ids = (detail.get("external-ids") or {}).get("external-id", [])
                doi = next((x for x in ext_ids if x["external-id-type"] == "doi"), None)
                if doi:
                    url = f"https://doi.org/{doi['external-id-value']}"
                else:
                    uri = next((x for x in ext_ids if x["external-id-type"] == "uri"), None)
                    if uri:
                        url = uri["external-id-value"]

                contribs = (detail.get("contributors") or {}).get("contributor", [])
                names = [c.get("credit-name", {}).get("value", "") for c in contribs if c.get("credit-name")]
                authors_str = ", ".join(shorten_name(n) for n in names if n)
        except Exception as e:
            print(f"  Warning: could not fetch detail for put-code {put_code}: {e}")

        publications.append({
            "type":    local_type,
            "badge":   badge_from_type(local_type, work_type),
            "title":   title,
            "url":     url,
            "authors": authors_str,
            "venue":   venue,
            "year":    year,
        })
        print(f"  ✓ [{local_type}] {title[:70]}{'…' if len(title) > 70 else ''} ({year})")

    # Sort newest first
    publications.sort(key=lambda p: int(p["year"]) if p["year"].isdigit() else 0, reverse=True)
    return publications


# ── Update index.html ─────────────────────────────────────────────────────────

def js_string(s: str) -> str:
    """Escape a Python string for a JS single-quoted string."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")

def pubs_to_js(pubs: list[dict]) -> str:
    lines = ["  const FALLBACK_PUBS = ["]
    for p in pubs:
        lines.append("    {")
        lines.append(f"      type:    '{js_string(p['type'])}',")
        lines.append(f"      badge:   '{js_string(p['badge'])}',")
        lines.append(f"      title:   '{js_string(p['title'])}',")
        lines.append(f"      url:     '{js_string(p['url'])}',")
        lines.append(f"      authors: '{js_string(p['authors'])}',")
        lines.append(f"      venue:   '{js_string(p['venue'])}',")
        lines.append(f"      year:    '{js_string(p['year'])}'")
        lines.append("    },")
    lines.append("  ];")
    return "\n".join(lines)

def update_index(pubs: list[dict]) -> None:
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    # Replace the FALLBACK_PUBS block between markers
    pattern = r"(  const FALLBACK_PUBS = \[).*?(\];)"
    replacement = pubs_to_js(pubs)

    new_html, count = re.subn(pattern, replacement, html, count=1, flags=re.DOTALL)
    if count == 0:
        print("⚠️  Could not find FALLBACK_PUBS in index.html — no changes written.")
        return

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(new_html)
    print(f"\n✅ Updated {INDEX_FILE} with {len(pubs)} publications from ORCID.")


# ── Export JSON (bonus) ───────────────────────────────────────────────────────

def export_json(pubs: list[dict]) -> None:
    out = "publications.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(pubs, f, indent=2, ensure_ascii=False)
    print(f"📄 Also saved {out} for reference.")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        pubs = fetch_publications()
        if not pubs:
            print("No publications returned — keeping existing fallback list.")
            sys.exit(0)
        update_index(pubs)
        export_json(pubs)
        print(f"\nDone! {len(pubs)} publication(s) synced.")
        print("Tip: commit both index.html and publications.json to GitHub.")
    except requests.RequestException as e:
        print(f"\n❌ Network error: {e}")
        print("Check your internet connection and try again.")
        sys.exit(1)
    except FileNotFoundError:
        print(f"\n❌ Could not find {INDEX_FILE}.")
        print("Run this script from the same folder as your index.html.")
        sys.exit(1)
