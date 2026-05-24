"""
Credential vault — Fernet envelope encryption for stored DB credentials.

The encryption key is loaded from the ENCRYPTION_KEY environment variable (32-byte hex).
Credentials are decrypted only inside worker processes at connect time.
They are never logged and never sent to the LLM.
"""
from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken


class CredentialVault:
    def __init__(self, key_hex: str) -> None:
        """
        key_hex: 32-byte hex string (64 hex characters).
        Generate with: openssl rand -hex 32
        """
        if not key_hex:
            raise ValueError("ENCRYPTION_KEY must be set")
        try:
            key_bytes = bytes.fromhex(key_hex)
        except ValueError as e:
            raise ValueError(f"ENCRYPTION_KEY must be valid hex: {e}") from e
        if len(key_bytes) != 32:
            raise ValueError(f"ENCRYPTION_KEY must be 32 bytes (64 hex chars), got {len(key_bytes)}")
        # Fernet requires URL-safe base64-encoded 32-byte key
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        self._fernet = Fernet(fernet_key)

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        try:
            return self._fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken as e:
            raise ValueError("Credential decryption failed — key may have rotated") from e


def get_vault() -> CredentialVault:
    from app.config import settings
    return CredentialVault(settings.encryption_key)
