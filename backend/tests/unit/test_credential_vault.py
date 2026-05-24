"""
Tests for the credential vault encryption/decryption.
"""
import pytest

from app.services.credential_vault import CredentialVault


@pytest.mark.unit
class TestCredentialVault:
    def _vault(self) -> CredentialVault:
        # 32-byte hex key (test only)
        return CredentialVault("a" * 64)

    def test_roundtrip(self):
        vault = self._vault()
        plaintext = "postgresql://user:s3cr3t@host:5432/mydb"
        encrypted = vault.encrypt(plaintext)
        assert encrypted != plaintext.encode()
        decrypted = vault.decrypt(encrypted)
        assert decrypted == plaintext

    def test_different_ciphertexts_same_plaintext(self):
        vault = self._vault()
        plaintext = "test"
        c1 = vault.encrypt(plaintext)
        c2 = vault.encrypt(plaintext)
        # Fernet uses random IV so ciphertexts should differ
        assert c1 != c2

    def test_invalid_key_hex_raises(self):
        with pytest.raises(ValueError, match="valid hex"):
            CredentialVault("not-hex!")

    def test_key_wrong_length_raises(self):
        with pytest.raises(ValueError, match="32 bytes"):
            CredentialVault("aabb")  # too short

    def test_empty_key_raises(self):
        with pytest.raises(ValueError, match="must be set"):
            CredentialVault("")

    def test_tampered_ciphertext_raises(self):
        vault = self._vault()
        encrypted = vault.encrypt("test")
        tampered = encrypted[:-4] + b"xxxx"
        with pytest.raises(ValueError, match="decryption failed"):
            vault.decrypt(tampered)
