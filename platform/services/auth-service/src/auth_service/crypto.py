"""Each tenant's SSO client secret is the one thing in this service that
must never be readable from a DB dump alone — encrypt it at rest with
Fernet (AES-128-CBC + HMAC, authenticated so tampering is detected on
decrypt), keyed by `SSO_ENCRYPTION_KEY`. Same pattern as Skill
Marketplace's OAuth token encryption (crypto.py there).
"""

from cryptography.fernet import Fernet

from .config import settings

_fernet = Fernet(settings.sso_encryption_key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()
