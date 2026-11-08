from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# Argon2id with the library's recommended defaults (NFR-06).
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False
