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
"""IdentityHub adapter of C4-M2 (README 6.3, 6.11, 8.1, 11.2).

Without `IDENTITYHUB_URL` the built-in stand-in answers the same calls in memory; the adapter code is the same
for both (README 11: the stand-ins run through the real adapter from the point at which the response arrives).
"""
from __future__ import annotations

import base64
import os
import threading

import httpx

from portal_common import http
from portal_common.problems import Problem

from . import providers_common as common

PROVIDER = "IDENTITY_HUB"
DEFAULT_DID_BASE = "ih.example.org"
DEFAULT_CREDENTIAL_SERVICE = "https://ih.example.org/api/credentials"
DEFAULT_IDENTITY_API = "https://ih.example.org/api/identity"
DEFAULT_STS_TOKEN_URL = "https://ih.example.org/api/sts/token"

_lock = threading.RLock()
_contexts: dict[str, dict] = {}


def reset() -> None:
    with _lock:
        _contexts.clear()


def _did_base() -> str:
    return os.environ.get("IDENTITYHUB_DID_BASE", "").strip().strip(":") or DEFAULT_DID_BASE


def _credential_service(context: str) -> str:
    base = os.environ.get("IDENTITYHUB_CREDENTIAL_SERVICE_URL", "").strip().rstrip("/") or DEFAULT_CREDENTIAL_SERVICE
    return f"{base}/v1/participants/{context}"


def _sts_token_url() -> str:
    return os.environ.get("IDENTITYHUB_STS_TOKEN_URL", "").strip() or DEFAULT_STS_TOKEN_URL


def _context_id(bpn: str) -> str:
    """README 11.2: the BPN, unchanged or base64url depending on `IDENTITYHUB_CONTEXT_ID_ENCODING`."""
    if os.environ.get("IDENTITYHUB_CONTEXT_ID_ENCODING", "").strip().lower() == "base64":
        return base64.urlsafe_b64encode(bpn.encode()).rstrip(b"=").decode()
    return bpn


# --------------------------------------------------------------------------------------- stand-in
def _standin(method: str, path: str, body: dict | None) -> tuple[int, dict | None]:
    """The built-in IdentityHub: participant contexts in memory (README 11.2)."""
    context = body["participantContextId"] if method == "POST" else path.rsplit("/", 1)[-1]
    bpn = context
    if method == "DELETE" and os.environ.get("IDENTITYHUB_CONTEXT_ID_ENCODING", "").strip().lower() == "base64":
        bpn = context = base64.urlsafe_b64decode(context + "=" * (-len(context) % 4)).decode()
    if method == "DELETE":
        with _lock:
            _contexts.pop(context, None)
        return 204, None
    if "ORDER_ERROR" in common.failures(bpn):
        return 503, None
    common.record_order(PROVIDER, bpn, "wallet")
    with _lock:
        if context in _contexts:
            return 409, None
        answer = {"apiKey": common.random_secret(), "clientId": f"sts-{bpn}", "clientSecret": common.random_secret()}
        _contexts[context] = answer
    common.publish_wallet_document(bpn, body["did"], body["serviceEndpoints"][0]["serviceEndpoint"])
    return 201, answer


def _real(method: str, path: str, body: dict | None) -> tuple[int, dict | None]:
    try:
        response = http.request(method, os.environ["IDENTITYHUB_URL"].rstrip("/") + path, json=body,
                                headers={"x-api-key": os.environ.get("IDENTITYHUB_API_KEY", "")})
        answer = response.json() if response.content else None
    except httpx.HTTPError as error:
        raise common.upstream_error(f"IdentityHub not reachable: {type(error).__name__}") from error
    except ValueError:
        answer = None
    return response.status_code, answer if isinstance(answer, dict) else None


class IdentityHubAdapter:
    provider = PROVIDER
    supports_wallet_accounts = True
    issuance_mode = "HOLDER_REQUESTS"
    deletion_is_async = False

    def did_for(self, bpn: str) -> str:
        return f"did:web:{_did_base()}:{bpn}"

    def callback_router(self):
        return None

    def _call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict | None]:
        if os.environ.get("IDENTITYHUB_URL", "").strip():
            return _real(method, path, body)
        return _standin(method, path, body)

    def order_wallet(self, order: dict) -> dict:
        """Create the participant context (README 11.2); 409 means a context from an aborted attempt: delete it
        and create it again."""
        bpn = order["bpn"]
        context, did = _context_id(bpn), self.did_for(bpn)
        body = {"participantContextId": bpn, "did": did, "active": True,
                "key": {"keyId": f"{did}#key-1", "privateKeyAlias": f"{bpn}-key-1",
                        "keyGeneratorParams": {"algorithm": "EC", "curve": "secp256r1"}},
                "serviceEndpoints": [{"id": f"{did}#credential-service", "type": "CredentialService",
                                      "serviceEndpoint": _credential_service(context)}], "roles": []}
        status, answer = self._call("POST", "/v1alpha/participants", body)
        if status == 409:
            self._call("DELETE", f"/v1alpha/participants/{context}")
            status, answer = self._call("POST", "/v1alpha/participants", body)
        if status not in (200, 201) or not answer:
            raise common.upstream_error(f"IdentityHub answered {status}")
        identity_api = os.environ.get("IDENTITYHUB_URL", "").strip() or DEFAULT_IDENTITY_API
        return {"result": "CREATED", "did": did, "did_document_location": common.did_location(did),
                "credential_service_url": _credential_service(context), "provider_ref": bpn,
                "secrets": {"HOLDER_ACCESS": {"url": identity_api, "client_id": bpn, "secret": answer["apiKey"]},
                            "STS_ACCESS": {"url": _sts_token_url(), "client_id": answer["clientId"],
                                           "secret": answer["clientSecret"]}}}

    def order_account(self, order: dict) -> dict:
        """README 6.3: every wallet account gets a copy of the one STS access of the participant context."""
        sts = order.get("sts_access")
        if not sts:
            raise Problem(common.MODULE, 409, "wallet-not-active", detail="the wallet has no STS access",
                          retryable=False)
        return {"result": "CREATED", "token_url": _sts_token_url() if os.environ.get("IDENTITYHUB_STS_TOKEN_URL")
                else sts["url"], "client_id": sts["client_id"], "client_secret": sts["secret"]}

    def order_account_deletion(self, account: dict) -> dict:
        """README 6.3: deleting a wallet account changes nothing at the IdentityHub."""
        return {"result": "DELETED"}
