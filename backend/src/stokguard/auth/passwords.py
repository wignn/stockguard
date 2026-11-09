from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash("unavailable-account-placeholder")


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 256:
        raise ValueError("Password harus terdiri dari 12 hingga 256 karakter.")
    return hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False
