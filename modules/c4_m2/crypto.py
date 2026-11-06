#################################################################################
#  Copyright (c) 2026 Contributors to the Eclipse Foundation
#
#  See the NOTICE file(s) distributed with this work for additional
#  information regarding copyright ownership.
#
#  This program and the accompanying materials are made available under the
#  terms of the Apache License, Version 2.0 which is available at
#  https://www.apache.org/licenses/LICENSE-2.0.
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
#
#  AI Disclosure: This file was entirely AI-generated.
#  The AI-generated portions are made available under CC0-1.0 and not subject
#  to the project's license. The human contributor has reviewed and verified
#  that the code is correct.
#
#  SPDX-License-Identifier: Apache-2.0 AND CC0-1.0
#  Assisted-By: Claude Code (claude-sonnet-5-5)
"""AES-256-GCM encryption of the secrets of C4-M2 at rest (README 4, 5 `wallet_secret`, 6.7).

`encrypt(secret)` returns `(ciphertext, nonce, key_version)`: a random 12-byte nonce, the 16-byte GCM
tag appended to the ciphertext. Keys come from the environment at call time (never at import):

- `SECRETS_KEY`: the current key, 64 hex characters (AES-256);
- `SECRETS_KEY_VERSION`: its version number, default 1;
- `SECRETS_KEY_<version>`: older keys, so that rows of an earlier version stay readable.

If `SECRETS_KEY` is unset, one random key per process is used (see OPEN-QUESTIONS.md). A set but
malformed key raises a `ValueError` naming the variable and never falls back. No error message or log
line contains a secret.
"""
from __future__ import annotations

import os
import re
import secrets as _secrets
import threading

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
_HEX_KEY = re.compile(r"[0-9a-fA-F]{64}")

_lock = threading.Lock()
_auto_key: bytes | None = None


def reset() -> None:
    """Forget the per-process random key (used when `SECRETS_KEY` is unset)."""
    global _auto_key
    with _lock:
        _auto_key = None


def _current_version() -> int:
    raw = os.environ.get("SECRETS_KEY_VERSION", "").strip()
    if not raw:
        return 1
    try:
        version = int(raw)
    except ValueError:
        raise ValueError("SECRETS_KEY_VERSION must be a positive integer") from None
    if version < 1:
        raise ValueError("SECRETS_KEY_VERSION must be a positive integer")
    return version


def _parse_key(name: str, value: str) -> bytes:
    if not _HEX_KEY.fullmatch(value):
        raise ValueError(f"{name} must be an AES-256 key as 64 hex characters")
    return bytes.fromhex(value)


def _key_for(version: int) -> bytes:
    global _auto_key
    if version == _current_version():
        value = os.environ.get("SECRETS_KEY", "")
        if value == "":
            with _lock:
                if _auto_key is None:
                    _auto_key = _secrets.token_bytes(32)
                return _auto_key
        return _parse_key("SECRETS_KEY", value)
    name = f"SECRETS_KEY_{version}"
    value = os.environ.get(name, "")
    if value == "":
        raise ValueError(f"no key for key version {version}: {name} is not set")
    return _parse_key(name, value)


def encrypt(secret: str) -> tuple[bytes, bytes, int]:
    """Encrypt `secret` with the current key; returns `(ciphertext, nonce, key_version)`."""
    version = _current_version()
    nonce = _secrets.token_bytes(NONCE_BYTES)
    return AESGCM(_key_for(version)).encrypt(nonce, secret.encode("utf-8"), None), nonce, version


def decrypt(ciphertext: bytes, nonce: bytes, key_version: int) -> str:
    """Decrypt a row written under `key_version`; raises `ValueError` on a wrong key or tampered data."""
    key = _key_for(int(key_version))
    try:
        return AESGCM(key).decrypt(bytes(nonce), bytes(ciphertext), None).decode("utf-8")
    except (InvalidTag, ValueError):
        raise ValueError("secret cannot be decrypted: wrong key or tampered data") from None
