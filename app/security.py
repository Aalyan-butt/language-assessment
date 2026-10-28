import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def now_utc() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None = None) -> str:
    return (value or now_utc()).isoformat(timespec="seconds")


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def password_hash(password: str) -> tuple[str, str]:
    # Argon2 embeds a random salt in its encoded hash. The separate salt column is
    # retained for schema transparency, but the value is intentionally not needed.
    return _hasher.hash(password), "embedded-in-argon2"


def password_valid(encoded: str, password: str) -> bool:
    try:
        return _hasher.verify(encoded, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(encoded: str) -> bool:
    try:
        return _hasher.check_needs_rehash(encoded)
    except InvalidHashError:
        return True


def new_token() -> str:
    return secrets.token_urlsafe(48)


def new_nonce() -> str:
    return secrets.token_urlsafe(24)


def token_hash(token: str, secret: str) -> str:
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def session_expiry(minutes: int) -> str:
    return iso(now_utc() + timedelta(minutes=minutes))


def validate_password_strength(password: str) -> None:
    if len(password) < 10 or len(password) > 128:
        raise ValueError("Password must contain 10 to 128 characters.")
    groups = sum((
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ))
    if groups < 3:
        raise ValueError("Use at least three of: uppercase, lowercase, number, symbol.")

