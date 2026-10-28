"""Run the Stage 2 API locally without Google credentials.

This is development-only. Data is discarded when the process stops.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn

from app.config import get_settings
from app.main import create_test_app
from app.service import AccountService
from app.store import MemoryStore


def build_app():
    store = MemoryStore()
    accounts = AccountService(store, get_settings())
    accounts.create_user(
        name="Kaplan Administrator",
        email="aalyanriasatali@gmail.com",
        temporary_password=os.getenv("LOCAL_ADMIN_PASSWORD", "Kaplan!Test123"),
        role="admin",
        attempts_allowed=1,
        actor=None,
    )
    accounts.create_user(
        name="Test Student",
        email="student@example.com",
        temporary_password="Kaplan!Student1",
        role="student",
        attempts_allowed=1,
        actor=None,
    )
    return create_test_app(store)


local_app = build_app()

if __name__ == "__main__":
    print("Local admin: aalyanriasatali@gmail.com")
    print("Temporary password: Kaplan!Test123")
    print("Local student: student@example.com / Kaplan!Student1")
    print("Local data is temporary and disappears when the server stops.")
    uvicorn.run(local_app, host="127.0.0.1", port=8000, log_level="info")
