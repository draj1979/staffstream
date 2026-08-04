"""OAuth access/refresh tokens are the one thing in this service that must
never be readable from a DB dump alone — encrypt them at rest with Fernet
(AES-128-CBC + HMAC, authenticated so tampering is detected on decrypt),
keyed by `OAUTH_ENCRYPTION_KEY`. Everything else (which skill, whether
it's enabled, connection metadata) stays plaintext; only the token
columns themselves go through this module.
"""

from cryptography.fernet import Fernet

from .config import settings

_fernet = Fernet(settings.oauth_encryption_key.encode())


def encrypt_token(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()
