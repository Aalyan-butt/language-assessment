"""Safely reset an existing administrator password in Google Sheets.

The password is entered invisibly and is never printed or stored as plaintext.
Run from the project root:
    python scripts/reset_admin_password.py --email admin@example.com
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.security import iso, password_hash, validate_password_strength
from app.store import GoogleSheetStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    email = args.email.strip().casefold()

    store = GoogleSheetStore(get_settings())
    user = store.find("Users", "email", email)
    if not user:
        raise SystemExit("No account exists with that email address.")
    if user.get("role") != "admin":
        raise SystemExit("Password recovery with this command is restricted to administrators.")

    while True:
        password = getpass.getpass("New administrator password: ")
        confirmation = getpass.getpass("Confirm new administrator password: ")
        if password != confirmation:
            print("Passwords do not match. Try again.")
            continue
        try:
            validate_password_strength(password)
        except ValueError as exc:
            print(exc)
            continue
        break

    encoded, salt = password_hash(password)
    updated = store.update("Users", "email", email, {
        "password_hash": encoded,
        "password_salt": salt,
        "password_version": str(int(user.get("password_version") or "1") + 1),
        "must_change_password": False,
        "failed_login_count": 0,
        "locked_until": "",
        "updated_at": iso(),
    })
    if not updated:
        raise SystemExit("The account changed during recovery; no update was made.")
    print("Administrator password updated successfully. You can now sign in.")


if __name__ == "__main__":
    main()
