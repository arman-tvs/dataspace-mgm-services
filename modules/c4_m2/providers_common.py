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
#################################################################################
"""Shared helpers of the provider adapters of C4-M2: the log of stand-in orders, `STUB_FAILURES` (README 14.3),
delayed stand-in tasks (`STUB_CALLBACK_DELAY_SECONDS`) and the DID documents that the stand-ins supply to the
built-in resolution (README 11.4). State lives in memory and is cleared by `reset()`.
"""
from __future__ import annotations

import base64
import logging
import os
import threading
import uuid
from typing import Callable

from cryptography.hazmat.primitives.asymmetric import ec

from portal_common.problems import Problem

MODULE = "c4-m2"
log = logging.getLogger(__name__)

_lock = threading.RLock()
_orders: list[dict] = []
_documents: dict[str, dict] = {}
_pending: list[dict] = []


def number(name: str, default: float) -> float:
    """A non-negative number from the environment, read at call time; the default if unset or unusable."""
    try:
        value = float(os.environ.get(name, "").strip())
    except ValueError:
        return default
    return value if value >= 0 else default


def failures(subject: str) -> set[str]:
    """The failures that `STUB_FAILURES` (`<BPN or technicalUserId>:<failure>`, comma-separated) names for `subject`."""
    found: set[str] = set()
    for entry in os.environ.get("STUB_FAILURES", "").split(","):
        name, _, failure = entry.strip().partition(":")
        if failure and name.strip().lower() == str(subject).lower():
            found.add(failure.strip().upper())
    return found


def upstream_error(detail: str) -> Problem:
    """README 12: the provider did not accept an order or is not reachable."""
    return Problem(MODULE, 502, "upstream-error", detail=detail, retryable=True)


def provider_rejected(detail: str) -> Problem:
    """README 12: the provider rejects on business grounds."""
    return Problem(MODULE, 409, "provider-rejected", detail=detail, retryable=False)


# ------------------------------------------------------------------------------------- order log
def record_order(provider: str, bpn: str, kind: str, external_id: str | None = None) -> None:
    """Remember an order that a built-in stand-in received (`kind`: wallet, account, account-deletion)."""
    entry = {"provider": provider, "bpn": bpn, "kind": kind}
    if external_id is not None:
        entry["external_id"] = external_id
    with _lock:
        _orders.append(entry)


def orders() -> list[dict]:
    with _lock:
        return [dict(entry) for entry in _orders]


# ----------------------------------------------------------------------------------- DID documents
def publish_document(did: str, document: dict) -> None:
    with _lock:
        _documents[did] = document


def documents() -> dict[str, dict]:
    """DID -> document. `DID_NOT_RESOLVABLE` (README 14.3) hides the document of that BPN while it is set; it is
    read at call time, so the document becomes resolvable as soon as the failure is removed."""
    with _lock:
        published = dict(_documents)
    return {did: document for did, document in published.items()
            if "DID_NOT_RESOLVABLE" not in failures(did.rsplit(":", 1)[-1])}


def p256_jwk() -> dict:
    """The public part of a new P-256 key (README 11.1 to 11.3: the stand-ins generate a key per wallet)."""
    numbers = ec.generate_private_key(ec.SECP256R1()).public_key().public_numbers()

    def encode(value: int) -> str:
        return base64.urlsafe_b64encode(value.to_bytes(32, "big")).rstrip(b"=").decode()

    return {"kty": "EC", "crv": "P-256", "x": encode(numbers.x), "y": encode(numbers.y)}


def did_document(did: str, credential_service: str | None, with_key: bool = True) -> dict:
    """A DID document as README 6.4 step 3 wants it: one key and, if given, the service `CredentialService`."""
    document: dict = {"@context": ["https://www.w3.org/ns/did/v1", "https://w3id.org/security/suites/jws-2020/v1"],
                      "id": did, "service": []}
    if credential_service:
        document["service"].append({"id": f"{did}#credential-service", "type": "CredentialService",
                                    "serviceEndpoint": credential_service})
    if with_key:
        document["verificationMethod"] = [{"id": f"{did}#key-1", "type": "JsonWebKey2020", "controller": did,
                                           "publicKeyJwk": p256_jwk()}]
    else:
        document["verificationMethod"] = []
    return document


def publish_wallet_document(bpn: str, did: str, credential_service: str | None) -> None:
    """The DID document of a stand-in wallet for the built-in resolution, with the failures of README 14.3:
    `INVALID_DID_DOCUMENT` has no key; `DID_NOT_RESOLVABLE` hides the document in `documents()`."""
    failed = failures(bpn)
    publish_document(did, did_document(did, credential_service, with_key="INVALID_DID_DOCUMENT" not in failed))


def did_location(did: str) -> str:
    """Where the DID document of a `did:web` DID lives (did:web method: path segments after the host)."""
    return "https://" + "/".join(did.split(":")[2:]) + "/did.json"


def random_secret() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


# ---------------------------------------------------------------------------- delayed stand-in tasks
def _run(entry: dict) -> None:
    with _lock:
        if entry["done"]:
            return
        entry["done"] = True
        if entry in _pending:
            _pending.remove(entry)
        timer = entry.get("timer")
    if timer is not None:
        timer.cancel()
    try:
        entry["task"]()
    except Exception as error:  # noqa: BLE001 - a failing stand-in callback must not stop the others
        log.warning("stand-in task failed: %s: %s", type(error).__name__, error)


def schedule(task: Callable[[], None]) -> None:
    """Run a stand-in callback after `STUB_CALLBACK_DELAY_SECONDS`; at once if that is 0. A pending task also
    runs when `flush()` is called (tests do not wait for the timer)."""
    delay = number("STUB_CALLBACK_DELAY_SECONDS", 1.0)
    entry = {"task": task, "done": False, "timer": None}
    if delay <= 0:
        _run(entry)
        return
    timer = threading.Timer(delay, _run, args=(entry,))
    timer.daemon = True
    entry["timer"] = timer
    with _lock:
        _pending.append(entry)
    timer.start()


def flush() -> None:
    """Run every pending stand-in task now, in the order in which it was scheduled."""
    with _lock:
        waiting = list(_pending)
    for entry in waiting:
        _run(entry)


def reset() -> None:
    with _lock:
        waiting = list(_pending)
        _pending.clear()
        _orders.clear()
        _documents.clear()
    for entry in waiting:
        entry["done"] = True
        if entry.get("timer") is not None:
            entry["timer"].cancel()
