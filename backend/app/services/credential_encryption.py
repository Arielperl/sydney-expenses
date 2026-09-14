"""Application-level encryption for third-party provider credentials that
must live in our database (Cardcom's per-terminal `ApiName`/`ApiPassword` —
Cardcom has no OAuth/token flow, only these merchant-supplied credentials).

Deliberately not the same mechanism as `connection_secrets.py`: that module
*derives* a value we ourselves generated and never needs to recover the
original plaintext. Here the plaintext (the owner's real Cardcom API
credentials) must be recoverable, in order to call Cardcom's server-to-server
verification API — so this is symmetric encryption (Fernet/AES), not a
one-way derivation, and the key must never leave the server or reach the
frontend, the same trust boundary as `SUPABASE_SECRET_KEY`.
"""

import json

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings


class CredentialEncryptionNotConfigured(RuntimeError):
    pass


class CredentialDecryptionError(RuntimeError):
    pass


def encrypt_credentials(settings: Settings, *, api_name: str, api_password: str | None) -> str:
    key = settings.cardcom_credential_encryption_key
    if not key:
        raise CredentialEncryptionNotConfigured(
            "Cardcom credential storage is not configured. Set CARDCOM_CREDENTIAL_ENCRYPTION_KEY."
        )
    payload = json.dumps({"api_name": api_name, "api_password": api_password}).encode("utf-8")
    return Fernet(key.encode("utf-8")).encrypt(payload).decode("utf-8")


def decrypt_credentials(settings: Settings, encrypted: str) -> dict:
    key = settings.cardcom_credential_encryption_key
    if not key:
        raise CredentialEncryptionNotConfigured(
            "Cardcom credential storage is not configured. Set CARDCOM_CREDENTIAL_ENCRYPTION_KEY."
        )
    try:
        raw = Fernet(key.encode("utf-8")).decrypt(encrypted.encode("utf-8"))
    except InvalidToken as exc:
        # Never include the ciphertext or key material in the error.
        raise CredentialDecryptionError("Stored Cardcom credentials could not be decrypted.") from exc
    return json.loads(raw)
