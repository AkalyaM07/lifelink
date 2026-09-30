"""
Life-Link: Security & Password Hashing
Uses PBKDF2-HMAC-SHA256 with cryptographically secure random salt.
Ensures passwords are never stored in plain-text.
"""

import hashlib
import secrets


def hash_password(password: str) -> str:
    """
    Hashes a plain text password using PBKDF2-HMAC-SHA256 with a 16-byte random salt.
    Format: salt:hash_hex
    """
    if not password:
        raise ValueError("Password cannot be empty")
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}:{key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain text password against stored salt:hash_hex string.
    Constant-time comparison to prevent timing attacks.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        parts = hashed_password.split(":")
        if len(parts) != 2:
            return False
        salt, stored_hex = parts
        computed_key = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return secrets.compare_digest(computed_key.hex(), stored_hex)
    except Exception:
        return False
