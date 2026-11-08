import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from functools import cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

# Argon2id with the library's recommended defaults (NFR-06).
_hasher = PasswordHasher()

# Rules for a new admin password. The upper limit stops huge inputs from tying up the slow hasher.
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


# --- access tokens (FR-51) --------------------------------------------------

_ALGORITHM = "HS256"
MIN_JWT_SECRET_LENGTH = 32


def jwt_configured() -> bool:
    """Tokens are only issued or accepted when a long enough secret is set. There is no default."""
    return len(settings.jwt_secret.get_secret_value()) >= MIN_JWT_SECRET_LENGTH


def create_access_token(admin_id: int, expires_in: timedelta | None = None) -> str:
    """The token carries only the account id. Role and active status are read from the
    database on every request, so deactivating an account takes effect at once."""
    now = datetime.now(UTC)
    lifetime = expires_in if expires_in is not None else timedelta(minutes=settings.access_token_minutes)
    claims = {"sub": str(admin_id), "iat": now, "exp": now + lifetime}
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=_ALGORITHM)


def read_access_claims(token: str) -> tuple[int, int] | None:
    """Return (admin id, issued-at as Unix seconds) from a valid, unexpired token, or None."""
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[_ALGORITHM],  # pinned: never trust the token's own algorithm header
            options={"require": ["exp", "sub", "iat"]},
        )
        return int(claims["sub"]), int(claims["iat"])
    except (jwt.PyJWTError, ValueError, TypeError):
        return None


def read_access_token(token: str) -> int | None:
    """Return the admin id from a valid, unexpired token, or None for anything else."""
    claims = read_access_claims(token)
    return None if claims is None else claims[0]


# --- one-time reset tokens (FR-56) -------------------------------------------


def new_reset_token() -> tuple[str, str]:
    """Return (token, hash). The token goes in the email; only the hash is stored, so a copy of
    the database cannot be used to take over an account. 256 bits of randomness, so a plain
    SHA-256 is enough (a slow hash is for guessable passwords, not for random tokens)."""
    token = secrets.token_urlsafe(32)
    return token, hash_reset_token(token)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@cache
def _dummy_hash() -> str:
    return hash_password("a-password-nobody-has")


def burn_password_check(password: str) -> None:
    """Spend the same time as a real check when the account does not exist, so response
    timing does not reveal which emails are registered."""
    verify_password(password, _dummy_hash())
