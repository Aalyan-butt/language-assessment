from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from fastapi import HTTPException, status

from .config import Settings
from .security import (
    iso, needs_rehash, new_nonce, new_token, now_utc, parse_datetime,
    password_hash, password_valid, session_expiry, token_hash,
    validate_password_strength,
)
from .store import Store


def public_user(user: dict[str, str]) -> dict[str, Any]:
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "status": user["status"],
        "must_change_password": user["must_change_password"] == "TRUE",
        "attempts_allowed": int(user.get("attempts_allowed") or 1),
        "attempts_used": int(user.get("attempts_used") or 0),
        "created_at": user.get("created_at", ""),
        "last_login_at": user.get("last_login_at", ""),
        "password_status": "Temporary" if user.get("must_change_password") == "TRUE" else "Set by user",
    }


@dataclass
class AccountService:
    store: Store
    settings: Settings

    def audit(self, action: str, actor: dict[str, str] | None = None,
              target: dict[str, str] | None = None, success: bool = True,
              details: dict[str, Any] | None = None, user_agent: str = "",
              request_id: str = "") -> None:
        safe_details = details or {}
        # Defensive: credentials and tokens must never reach Audit.
        safe_details = {k: v for k, v in safe_details.items()
                        if k not in {"password", "temporary_password", "token", "csrf_nonce"}}
        self.store.append("Audit", {
            "timestamp": iso(), "actor_user_id": (actor or {}).get("user_id", ""),
            "actor_email": (actor or {}).get("email", ""), "action": action,
            "target_user_id": (target or {}).get("user_id", ""),
            "target_email": (target or {}).get("email", ""),
            "success": success, "details": json.dumps(safe_details, separators=(",", ":")),
            "request_id": request_id, "user_agent": user_agent[:300],
        })

    def create_user(self, *, name: str, email: str, temporary_password: str,
                    role: str, attempts_allowed: int, actor: dict[str, str] | None) -> dict[str, Any]:
        email = email.strip().casefold()
        if self.store.find("Users", "email", email):
            raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
        try:
            validate_password_strength(temporary_password)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        encoded, salt = password_hash(temporary_password)
        created = iso()
        user = {
            "user_id": str(uuid.uuid4()), "email": email, "name": name.strip(), "role": role,
            "password_hash": encoded, "password_salt": salt, "password_version": "1",
            "must_change_password": False, "status": "active",
            "attempts_allowed": attempts_allowed, "attempts_used": 0,
            "failed_login_count": 0, "locked_until": "", "created_at": created,
            "created_by": (actor or {}).get("user_id", "setup"), "last_login_at": "",
            "updated_at": created,
        }
        self.store.append("Users", user)
        stored = self.store.find("Users", "email", email) or {k: str(v) for k, v in user.items()}
        self.audit("USER_CREATED", actor, stored, details={"role": role})
        return public_user(stored)

    def login(self, email: str, password: str, user_agent: str, request_id: str) -> dict[str, Any]:
        email = email.strip().casefold()
        user = self.store.find("Users", "email", email)
        generic = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")
        if not user:
            self.audit("LOGIN_FAILED", details={"email": email, "reason": "unknown_account"},
                       user_agent=user_agent, request_id=request_id, success=False)
            raise generic
        if user.get("status") != "active":
            self.audit("LOGIN_FAILED", target=user, details={"reason": "disabled"},
                       user_agent=user_agent, request_id=request_id, success=False)
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled.")
        locked_until = parse_datetime(user.get("locked_until"))
        if user.get("role") != "admin" and locked_until and locked_until > now_utc():
            self.audit("LOGIN_BLOCKED", target=user, details={"reason": "locked"},
                       user_agent=user_agent, request_id=request_id, success=False)
            raise HTTPException(
                status.HTTP_423_LOCKED,
                f"This account is temporarily locked after too many incorrect passwords. "
                f"Wait {self.settings.account_lock_minutes * 60} seconds and try again. "
                "Other accounts can still sign in.",
            )
        if not password_valid(user.get("password_hash", ""), password):
            if user.get("role") == "admin":
                # Administrators still need the correct password, but are not
                # locked out of the whole management system by typing errors.
                self.store.update("Users", "user_id", user["user_id"], {
                    "failed_login_count": 0, "locked_until": "", "updated_at": iso()
                })
                self.audit("LOGIN_FAILED", target=user, details={"reason": "bad_password"},
                           user_agent=user_agent, request_id=request_id, success=False)
                raise generic
            failures = int(user.get("failed_login_count") or 0) + 1
            changes: dict[str, Any] = {"failed_login_count": failures, "updated_at": iso()}
            if failures >= self.settings.max_login_failures:
                changes["locked_until"] = iso(now_utc() + timedelta(minutes=self.settings.account_lock_minutes))
                changes["failed_login_count"] = 0
            self.store.update("Users", "user_id", user["user_id"], changes)
            self.audit("LOGIN_FAILED", target=user, details={"reason": "bad_password"},
                       user_agent=user_agent, request_id=request_id, success=False)
            raise generic
        updates: dict[str, Any] = {
            "failed_login_count": 0, "locked_until": "", "last_login_at": iso(), "updated_at": iso()
        }
        if needs_rehash(user["password_hash"]):
            updates["password_hash"], updates["password_salt"] = password_hash(password)
        self.store.update("Users", "user_id", user["user_id"], updates)
        user.update({k: str(v) for k, v in updates.items()})
        raw_token, nonce = new_token(), new_nonce()
        self.store.append("Sessions", {
            "session_id": str(uuid.uuid4()), "user_id": user["user_id"],
            "token_hash": token_hash(raw_token, self.settings.app_secret), "csrf_nonce": nonce,
            "created_at": iso(), "last_activity_at": iso(),
            "expires_at": session_expiry(self.settings.session_idle_minutes), "revoked_at": "",
            "user_agent": user_agent[:300],
        })
        self.audit("LOGIN_SUCCEEDED", user, user, user_agent=user_agent, request_id=request_id)
        return {"token": raw_token, "csrf_token": nonce, "expires_in": self.settings.session_idle_minutes * 60,
                "user": public_user(user)}

    def authenticate(self, raw_token: str) -> tuple[dict[str, str], dict[str, str]]:
        digest = token_hash(raw_token, self.settings.app_secret)
        session = self.store.find("Sessions", "token_hash", digest)
        if not session or session.get("revoked_at"):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is invalid or expired.")
        expiry = parse_datetime(session.get("expires_at"))
        if not expiry or expiry <= now_utc():
            self.store.update("Sessions", "session_id", session["session_id"], {"revoked_at": iso()})
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is invalid or expired.")
        user = self.store.find("Users", "user_id", session["user_id"])
        if not user or user.get("status") != "active":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled or unavailable.")
        # Avoid a Sheet write on every request; refresh inactivity after five minutes.
        last = parse_datetime(session.get("last_activity_at"))
        if not last or now_utc() - last >= timedelta(minutes=5):
            changes = {"last_activity_at": iso(), "expires_at": session_expiry(self.settings.session_idle_minutes)}
            self.store.update("Sessions", "session_id", session["session_id"], changes)
            session.update(changes)
        return user, session

    def change_password(self, user: dict[str, str], current: str, new: str) -> None:
        if not password_valid(user["password_hash"], current):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
        try:
            validate_password_strength(new)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        if password_valid(user["password_hash"], new):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must be different.")
        encoded, salt = password_hash(new)
        self.store.update("Users", "user_id", user["user_id"], {
            "password_hash": encoded, "password_salt": salt,
            "password_version": int(user.get("password_version") or 1) + 1,
            "must_change_password": False, "updated_at": iso(),
        })
        self.audit("PASSWORD_CHANGED", user, user)
