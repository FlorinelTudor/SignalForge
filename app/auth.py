from passlib.context import CryptContext
from passlib.exc import MissingBackendError

pwd_context = CryptContext(schemes=["argon2", "pbkdf2_sha256", "bcrypt"], deprecated="auto")
fallback_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    try:
        return pwd_context.hash(password)
    except MissingBackendError:
        return fallback_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(password, hashed)
    except (ValueError, MissingBackendError):
        return fallback_context.verify(password, hashed)
