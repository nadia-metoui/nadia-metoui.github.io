#!/usr/bin/env python3
import yaml
import requests
import sys
import os

ORCID_ID   = "0000-0001-6690-2937"
ORCID_BASE = f"https://pub.orcid.org/v3.0/{ORCID_ID}"
HEADERS    = {"Accept": "application/json"}
DATA_FILE  = "_data/publications.yml"

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
    parts = full_name.strip().split()
    if len(parts) > 1:
        return parts[0][0] + ". " + " ".join(parts[1:])
    return full_name

def fetch_publications() -> list[dict]:
    print(f"Fetching works for ORCID {ORCID_ID}...")
    r = requests.get(f"{ORCID_BASE}/works", headers=HEADERS, timeout=15)
    r.raise_for_status()
    groups = r.json().get("group", [])
    
    publications = []
    for g in groups:
        summary  = g["work-summary"][0]
        put_code = summary["put-code"]
        work_type = summary.get("type", "")
        local_type = orcid_type_to_local(work_type)

        title = summary.get("title", {}).get("title", {}).get("value", "Untitled")
        year  = (summary.get("publication-date") or {}).get("year", {}).get("value", "") or ""
        venue = (summary.get("journal-title") or {}).get("value", "") or ""

        url = ""
        authors_str = ""
        try:
            dr = requests.get(f"{ORCID_BASE}/work/{put_code}", headers=HEADERS, timeout=10)
            if dr.ok:
                detail = dr.json()
                ext_ids = (detail.get("external-ids") or {}).get("external-id", [])
                doi = next((x for x in ext_ids if x["external-id-type"] == "doi"), None)
                if doi:
                    url = f"https://doi.org/{doi['external-id-value']}"
                
                contribs = (detail.get("contributors") or {}).get("contributor", [])
                names = [c.get("credit-name", {}).get("value", "") for c in contribs if c.get("credit-name")]
                authors_str = ", ".join(shorten_name(n) for n in names if n)
        except Exception as e:
            print(f"  Warning: could not fetch detail for {put_code}: {e}")

        publications.append({
            "type":    local_type,
            "badge":   badge_from_type(local_type, work_type),
            "title":   title,
            "url":     url,
            "authors": authors_str,
            "venue":   venue,
            "year":    year,
        })
    
    publications.sort(key=lambda p: int(p["year"]) if p["year"].isdigit() else 0, reverse=True)
    return publications

def save_to_yaml(pubs: list[dict]) -> None:
    # Ensure _data directory exists
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        yaml.dump(pubs, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"\n✅ Successfully updated {DATA_FILE}")

if __name__ == "__main__":
    try:
        pubs = fetch_publications()
        if pubs:
            save_to_yaml(pubs)
            print(f"Synced {len(pubs)} publications.")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)