# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import hashlib
import json
import secrets

from cryptography.fernet import Fernet


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def random_token() -> str:
    return secrets.token_urlsafe(32)


class SecretBox:
    def __init__(self, key: str):
        self.key = key

    def cipher(self):
        if not self.key:
            raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY must be configured before authentication")
        return Fernet(self.key.encode())

    def encrypt(self, value: dict) -> str:
        return self.cipher().encrypt(json.dumps(value).encode()).decode()

    def decrypt(self, value: str) -> dict:
        return json.loads(self.cipher().decrypt(value.encode()))
