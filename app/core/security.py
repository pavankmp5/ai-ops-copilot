import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.core.settings import get_settings


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    resolved_salt = salt or secrets.token_hex(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        resolved_salt.encode("utf-8"),
        100_000,
    )
    return derived_key.hex(), resolved_salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    computed_hash, _ = hash_password(password, salt=salt)
    return hmac.compare_digest(computed_hash, password_hash)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def _create_token(subject: str, role: str, token_type: str, expires_minutes: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }

    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )

    signature = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    return f"{signing_input}.{_b64url_encode(signature)}"


def create_access_token(subject: str, role: str) -> str:
    return _create_token(
        subject=subject,
        role=role,
        token_type="access",
        expires_minutes=get_settings().jwt_expire_minutes,
    )


def decode_access_token(token: str, expected_type: str = "access") -> dict:
    settings = get_settings()

    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format.",
        ) from exc

    signing_input = f"{header_b64}.{payload_b64}"
    expected_signature = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(_b64url_encode(expected_signature), signature_b64):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature.",
        )

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    if payload.get("exp", 0) < int(datetime.now(UTC).timestamp()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        )

    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token type. Expected '{expected_type}'.",
        )

    return payload
