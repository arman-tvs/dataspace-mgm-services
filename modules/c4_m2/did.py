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
"""DID checks of C4-M2 (README 6.4): the form of the DID and the content of the DID document.

`check_form` is step 1 (before resolution), `check_document` is step 3. The expected DID of a provider
comes from `providers.get(provider).did_for(bpn)` (imported at call time because `providers.py` is a
separate file); if that file does not exist yet, the configured bases are used directly:
`SAP_DIV_DID_DOCUMENT_BASE_URL` and `IDENTITYHUB_DID_BASE`.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx

from portal_common import http

from . import service

log = logging.getLogger(__name__)
RESOLVE_TIMEOUT_SECONDS = 10.0

INVALID_DID_DOCUMENT = "INVALID_DID_DOCUMENT"
CREDENTIAL_SERVICE = "CredentialService"
_PROVIDERS_WITH_CREDENTIAL_SERVICE = {"IDENTITY_HUB", "CSP"}


def _expected_did(provider: str, bpn: str) -> str | None:
    """The DID the provider must use for `bpn`, None if only the form `did:web:` is checked (CSP)."""
    providers = service.optional_module("providers")
    if providers is not None:
        return providers.get(provider).did_for(bpn)
    if provider == "SAP_DIV":
        base = urlsplit(os.environ.get("SAP_DIV_DID_DOCUMENT_BASE_URL", ""))
        location = (base.netloc + base.path).strip("/").replace("/", ":")
        return f"did:web:{location}:{bpn}" if location else None
    if provider == "IDENTITY_HUB":
        base = os.environ.get("IDENTITYHUB_DID_BASE", "").strip().strip(":")
        return f"did:web:{base}:{bpn}" if base else None
    return None


def check_form(provider: str, did: str, bpn: str) -> bool:
    """README 6.4 step 1. SAP DIV and IdentityHub: exactly the expected DID, case does not matter.
    CSP: only the form `did:web:` (the CSP decides host and path)."""
    if not isinstance(did, str) or not did:
        return False
    if provider == "CSP":
        return did.lower().startswith("did:web:") and len(did) > len("did:web:")
    expected = _expected_did(provider, bpn)
    return expected is not None and did.lower() == expected.lower()


def _non_empty(value: object) -> bool:
    return isinstance(value, str) and value != ""


def _usable_key(method: object) -> bool:
    jwk = method.get("publicKeyJwk") if isinstance(method, dict) else None
    if not isinstance(jwk, dict):
        return False
    if jwk.get("kty") == "EC":
        return all(_non_empty(jwk.get(name)) for name in ("crv", "x", "y"))
    if jwk.get("kty") == "OKP":
        return all(_non_empty(jwk.get(name)) for name in ("crv", "x"))
    return False


def _has_credential_service(document: dict) -> bool:
    services = document.get("service")
    if isinstance(services, dict):
        services = [services]
    if not isinstance(services, list):
        return False
    for entry in services:
        kind = entry.get("type") if isinstance(entry, dict) else None
        if kind == CREDENTIAL_SERVICE or (isinstance(kind, list) and CREDENTIAL_SERVICE in kind):
            return True
    return False


def check_document(provider: str, did: str, document: dict) -> str | None:
    """README 6.4 step 3: None if the document is fine, else `INVALID_DID_DOCUMENT`."""
    if not isinstance(document, dict) or document.get("id") != did:
        return INVALID_DID_DOCUMENT
    methods = document.get("verificationMethod")
    if not isinstance(methods, list) or not any(_usable_key(m) for m in methods):
        return INVALID_DID_DOCUMENT
    if provider in _PROVIDERS_WITH_CREDENTIAL_SERVICE and not _has_credential_service(document):
        return INVALID_DID_DOCUMENT
    return None


# ------------------------------------------------------------------------------------- resolution
def _host_and_path(did: str) -> tuple[str, list[str]]:
    """Host and path segments of a `did:web` DID (`%3A` in the host is a port separator)."""
    parts = did.split(":")[2:]
    host = unquote(parts[0]).lower() if parts else ""
    return host, [unquote(part) for part in parts[1:]]


def _from_test_directory(did: str) -> dict | None:
    """README 4, 11.4: `TEST_DID_DOCUMENTS_DIR/<host>.json` is used before any other resolution."""
    directory = os.environ.get("TEST_DID_DOCUMENTS_DIR", "").strip()
    host, _ = _host_and_path(did)
    if not directory or not host:
        return None
    path = Path(directory) / f"{host}.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def _from_stand_in_providers(did: str) -> dict | None:
    providers = service.optional_module("providers")
    if providers is None:
        return None
    documents = providers.stand_in_documents()
    if did in documents:
        return documents[did]
    wanted = did.lower()
    return next((doc for known, doc in documents.items() if known.lower() == wanted), None)


def _from_resolver(base_url: str, did: str) -> dict | None:
    """README 11.4: `GET {DID_RESOLVER_URL}/1.0/identifiers/{did}`; success on 2xx and an empty
    `didResolutionMetadata.error`, the document is in `didDocument`."""
    try:
        response = http.request("GET", f"{base_url.rstrip('/')}/1.0/identifiers/{did}",
                                timeout=RESOLVE_TIMEOUT_SECONDS)
        if not 200 <= response.status_code < 300:
            return None
        body = response.json()
    except (httpx.HTTPError, ValueError):
        log.info("DID resolver not reachable or unreadable for %s", did)
        return None
    if not isinstance(body, dict) or (body.get("didResolutionMetadata") or {}).get("error"):
        return None
    document = body.get("didDocument")
    return document if isinstance(document, dict) else None


def _from_did_web(did: str) -> dict | None:
    """README 11.4: `https://<host>/<path>/did.json` or `https://<host>/.well-known/did.json`, HTTPS only."""
    host, path = _host_and_path(did)
    if not did.lower().startswith("did:web:") or not host:
        return None
    url = f"https://{host}/{'/'.join(path)}/did.json" if path else f"https://{host}/.well-known/did.json"
    try:
        response = http.request("GET", url, timeout=RESOLVE_TIMEOUT_SECONDS)
        document = response.json() if response.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        log.info("did:web document not reachable for %s", did)
        return None
    return document if isinstance(document, dict) else None


def resolve(did: str) -> dict | None:
    """The DID document of `did`, or None if it cannot be resolved now (README 6.4 step 2).

    Order: files of `TEST_DID_DOCUMENTS_DIR`; then `DID_RESOLVER_URL` if set, otherwise the documents
    of the stand-in providers and the built-in `did:web` resolution."""
    document = _from_test_directory(did)
    if document is not None:
        return document
    resolver = os.environ.get("DID_RESOLVER_URL", "").strip()
    if resolver:
        return _from_resolver(resolver, did)
    return _from_stand_in_providers(did) or _from_did_web(did)
