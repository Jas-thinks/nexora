"""RFC 6238 TOTP (SHA-1, 6 digits, 30 s) with no external dependency. Verified against the RFC test vectors in tests."""
import base64
import hashlib
import hmac
import secrets
import struct
import time


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def code_at(secret: str, counter: int, digits: int = 6) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    h = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    return str((struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 10 ** digits).zfill(digits)


def verify(secret: str, code: str, last_counter: int = 0, now: float | None = None, window: int = 1) -> int | None:
    """-> the matched counter (store it to block replay) or None. Accepts +-`window` steps for clock drift."""
    if not (code.isdigit() and len(code) == 6):
        return None
    c0 = int((now if now is not None else time.time()) // 30)
    for c in range(c0 - window, c0 + window + 1):
        if c > last_counter and hmac.compare_digest(code_at(secret, c), code):
            return c
    return None


def uri(secret: str, email: str, issuer: str = "Nexora") -> str:
    from urllib.parse import quote
    return f"otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret}&issuer={quote(issuer)}&digits=6&period=30"
