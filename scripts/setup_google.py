"""Create Kaplan's Google Sheet/folder and the first administrator.

Run locally once:
    python scripts/setup_google.py --client-secrets client_secret.json

The OAuth client must be a Google Desktop application. This script prints the
Render environment variables; it never writes or prints the admin password.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.constants import SHEET_HEADERS
from app.lessons import LESSONS
from app.security import iso, password_hash, validate_password_strength

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-secrets", required=True)
    parser.add_argument("--admin-email", default="aalyanriasatali@gmail.com")
    parser.add_argument("--admin-name", default="Kaplan Administrator")
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secrets, SCOPES)
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)

    # A spreadsheet's first tab cannot be hidden. Put visible tabs first and
    # add the private account/session tabs afterwards in the same request.
    hidden_tabs = {"Users", "Sessions"}
    ordered_sheet_names = [name for name in SHEET_HEADERS if name not in hidden_tabs]
    ordered_sheet_names.extend(name for name in SHEET_HEADERS if name in hidden_tabs)
    spreadsheet = sheets.spreadsheets().create(body={
        "properties": {"title": "Kaplan English Placement Test — Master"},
        "sheets": [{"properties": {"title": name,
                    "hidden": name in hidden_tabs}} for name in ordered_sheet_names],
    }).execute()
    spreadsheet_id = spreadsheet["spreadsheetId"]
    data = [{"range": f"'{name}'!A1", "values": [headers]}
            for name, headers in SHEET_HEADERS.items()]
    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "RAW", "data": data},
    ).execute()

    folder = drive.files().create(body={
        "name": "Kaplan English Placement Test", "mimeType": "application/vnd.google-apps.folder"
    }, fields="id").execute()
    drive.files().update(fileId=spreadsheet_id, addParents=folder["id"], fields="id,parents").execute()

    settings_rows = [
        ["school_name", "Kaplan", "string", "Name displayed in reports", created if 'created' in locals() else iso(), "setup"],
        ["language", "en-GB", "string", "British English checking", iso(), "setup"],
        ["writing_prompt", "Describe a memorable day in your life.", "string", "Writing task", iso(), "setup"],
        ["writing_min_words", "120", "number", "Recommended minimum", iso(), "setup"],
        ["writing_max_words", "180", "number", "Recommended maximum", iso(), "setup"],
        ["level_a2_cutoff", "10", "number", "A2 total-score threshold", iso(), "setup"],
        ["level_b1_cutoff", "14", "number", "B1 total-score threshold", iso(), "setup"],
        ["level_b2_cutoff", "18", "number", "B2 total-score threshold", iso(), "setup"],
        ["checker_version", "rules-1.0", "string", "Active deterministic checker", iso(), "setup"],
    ]
    sheets.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id, range="'Settings'!A:F", valueInputOption="RAW",
        body={"values": settings_rows},
    ).execute()
    lesson_rows = [[x["id"], x["category"], x["title"], x["rule"], x["examples"],
                    x["mistake"], index, "TRUE"] for index, x in enumerate(LESSONS, 1)]
    sheets.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id, range="'Lessons'!A:H", valueInputOption="RAW",
        body={"values": lesson_rows},
    ).execute()

    while True:
        password = getpass.getpass("Temporary password for the first administrator: ")
        confirmation = getpass.getpass("Confirm temporary password: ")
        if password != confirmation:
            print("Passwords do not match.")
            continue
        try:
            validate_password_strength(password)
            break
        except ValueError as exc:
            print(exc)
    encoded, salt = password_hash(password)
    created = iso()
    row = {
        "user_id": __import__("uuid").uuid4(), "email": args.admin_email.casefold(),
        "name": args.admin_name, "role": "admin", "password_hash": encoded,
        "password_salt": salt, "password_version": 1, "must_change_password": False,
        "status": "active", "attempts_allowed": 1, "attempts_used": 0,
        "failed_login_count": 0, "locked_until": "", "created_at": created,
        "created_by": "setup", "last_login_at": "", "updated_at": created,
    }
    headers = SHEET_HEADERS["Users"]
    sheets.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id, range="'Users'!A:Q", valueInputOption="RAW",
        body={"values": [[
            ("TRUE" if row.get(header) else "FALSE")
            if isinstance(row.get(header), bool) else str(row.get(header, ""))
            for header in headers
        ]]},
    ).execute()

    # google-auth-oauthlib exposes Desktop credentials as the inner client
    # mapping, while some releases retain the outer ``installed``/``web``
    # wrapper. Support both representations.
    client = flow.client_config
    if "installed" in client:
        client = client["installed"]
    elif "web" in client:
        client = client["web"]
    print("\nAdd these secret environment variables in Render:")
    print(f"GOOGLE_CLIENT_ID={client['client_id']}")
    print(f"GOOGLE_CLIENT_SECRET={client['client_secret']}")
    print(f"GOOGLE_REFRESH_TOKEN={credentials.refresh_token}")
    print(f"GOOGLE_SPREADSHEET_ID={spreadsheet_id}")
    print(f"GOOGLE_DRIVE_FOLDER_ID={folder['id']}")
    print("\nThe administrator password was hashed and was not printed or stored as plaintext.")


if __name__ == "__main__":
    main()
