import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")
TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
TABLE_NAME = "Clips"
API_ROOT = "https://api.airtable.com/v0"

CLIPS_TABLE_FIELDS = [
    {"name": "Video ID", "type": "singleLineText"},
    {"name": "Clip ID", "type": "singleLineText"},
    {"name": "Clip Filename", "type": "singleLineText"},
    {"name": "Hook Title", "type": "singleLineText"},
    {"name": "Category", "type": "singleLineText"},
    {"name": "Virality Score", "type": "number", "options": {"precision": 1}},
    {"name": "Clip Video", "type": "multipleAttachments"},
    {"name": "Clip URL", "type": "url"},
    {
        "name": "Status",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Scheduled"},
                {"name": "Posted"},
                {"name": "Failed"},
            ]
        },
    },
    {"name": "Post to TikTok", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
    {"name": "Post to Instagram Reels", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
    {"name": "Post to YouTube Shorts", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
    {"name": "Buffer Post ID - TikTok", "type": "singleLineText"},
    {"name": "Buffer Post ID - Instagram", "type": "singleLineText"},
    {"name": "Buffer Post ID - YouTube", "type": "singleLineText"},
    {"name": "Sync Error", "type": "multilineText"},
]


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }


def _table_url(table: str = TABLE_NAME) -> str:
    return f"{API_ROOT}/{BASE_ID}/{table}"


def ensure_clips_table() -> str:
    """Return the Clips table's id, creating the table if it doesn't exist yet."""
    resp = requests.get(f"{API_ROOT}/meta/bases/{BASE_ID}/tables", headers=_headers(), timeout=30)
    resp.raise_for_status()
    for table in resp.json().get("tables", []):
        if table["name"] == TABLE_NAME:
            return table["id"]

    create_resp = requests.post(
        f"{API_ROOT}/meta/bases/{BASE_ID}/tables",
        headers=_headers(),
        json={"name": TABLE_NAME, "fields": CLIPS_TABLE_FIELDS},
        timeout=30,
    )
    if create_resp.status_code == 403:
        raise RuntimeError(
            "Airtable rejected table creation (403) - the AIRTABLE_TOKEN likely lacks "
            "schema.bases:write scope. Create the 'Clips' table manually in Airtable "
            "using the schema in scripts/airtable_client.py's CLIPS_TABLE_FIELDS, then retry."
        )
    create_resp.raise_for_status()
    return create_resp.json()["id"]


def create_record(fields: dict) -> dict:
    resp = requests.post(_table_url(), headers=_headers(), json={"fields": fields}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def list_records(filter_by_formula: str | None = None) -> list[dict]:
    records: list[dict] = []
    params = {}
    if filter_by_formula:
        params["filterByFormula"] = filter_by_formula

    while True:
        resp = requests.get(_table_url(), headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
        params["offset"] = offset

    return records


def update_record(record_id: str, fields: dict) -> dict:
    resp = requests.patch(
        f"{_table_url()}/{record_id}", headers=_headers(), json={"fields": fields}, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--ensure-table", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.ensure_table:
        print(ensure_clips_table())
    if args.list:
        print(json.dumps(list_records(), indent=2))
