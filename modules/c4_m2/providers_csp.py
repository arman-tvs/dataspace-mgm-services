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
"""Adapter for the dataspace wallet of the CSP (README 6.3, 6.11, 8.1, 8.2, 8.3, 11.3).

With `CSP_WALLET_URL` the calls go through `portal_common.csp` (token by `private_key_jwt`, README 4). Without it
the built-in stand-in answers the same four calls in memory, so the adapter code is the same for both. Errors
(README 11.3): 403 is `provider-rejected`; 401, 5xx and timeout are `upstream-error`; 409 on a wallet or an account
from an aborted attempt deletes it at the CSP and creates it again.
"""
from __future__ import annotations

import os
import threading
import uuid

from portal_common import csp

from . import providers_common as common

PROVIDER = "CSP"
STANDIN_HOST = "csp-wallet.example.org"
STANDIN_STS_TOKEN_URL = f"https://{STANDIN_HOST}/api/sts/token"
STANDIN_IDENTITY_API = f"https://{STANDIN_HOST}/api/identity/v1"

_lock = threading.RLock()
_wallets: dict[str, dict] = {}


def reset() -> None:
    with _lock:
        _wallets.clear()


# --------------------------------------------------------------------------------------- stand-in
def _create_wallet(body: dict) -> tuple[int, dict | None]:
    bpn = body["bpn"]
    failed = common.failures(bpn)
    if "CSP_REJECTED" in failed:
        return 403, None
    if "ORDER_ERROR" in failed:
        return 503, None
    common.record_order(PROVIDER, bpn, "wallet")
    with _lock:
        if bpn in _wallets:
            return 409, None
        did = f"did:web:{STANDIN_HOST}:{bpn}"
        wallet = {"participantContextId": str(uuid.uuid4()), "did": did,
                  "credentialServiceUrl": f"https://{STANDIN_HOST}/api/credentials/v1/participants/{bpn}",
                  "identityApiUrl": STANDIN_IDENTITY_API, "apiKey": common.random_secret()}
        _wallets[bpn] = {**wallet, "accounts": {}}
    common.publish_wallet_document(bpn, did, wallet["credentialServiceUrl"])
    return 201, wallet


def _create_account(bpn: str, body: dict) -> tuple[int, dict | None]:
    if "ORDER_ERROR" in common.failures(bpn):
        return 503, None
    external_id = body["externalId"]
    common.record_order(PROVIDER, bpn, "account", external_id)
    with _lock:
        wallet = _wallets.get(bpn)
        if wallet is None:
            return 404, None
        if external_id in wallet["accounts"]:
            return 409, None
        account = {"tokenUrl": STANDIN_STS_TOKEN_URL, "clientId": f"sts-{bpn}-{external_id}",
                   "clientSecret": common.random_secret()}
        wallet["accounts"][external_id] = account
    return 201, account


def _standin(method: str, path: str, body: dict | None) -> tuple[int, dict | None]:
    parts = path.strip("/").split("/")                  # wallets[/{bpn}[/accounts[/{externalId}]]]
    if method == "POST" and len(parts) == 1:
        return _create_wallet(body or {})
    if method == "DELETE" and len(parts) == 2:
        with _lock:
            _wallets.pop(parts[1], None)
        return 204, None
    if method == "POST" and len(parts) == 3:
        return _create_account(parts[1], body or {})
    if method == "DELETE" and len(parts) == 4:
        if "ORDER_ERROR" in common.failures(parts[1]):
            return 503, None
        common.record_order(PROVIDER, parts[1], "account-deletion", parts[3])
        with _lock:
            found = _wallets.get(parts[1], {}).get("accounts", {}).pop(parts[3], None)
        return (204 if found else 404), None
    return 404, None


class CspAdapter:
    provider = PROVIDER
    supports_wallet_accounts = True
    issuance_mode = "HOLDER_REQUESTS"
    deletion_is_async = False

    def did_for(self, bpn: str) -> None:
        """README 6.4 step 1: the CSP decides host and path, only the form `did:web:` is checked."""
        return None

    def callback_router(self):
        return None

    def _call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict | None]:
        url = os.environ.get("CSP_WALLET_URL", "").strip()
        if not url:
            return _standin(method, path, body)
        try:
            status, answer = csp.request(url, method, path, body)
        except csp.CspUnavailable as error:
            raise common.upstream_error(f"CSP wallet API not reachable: {error}") from error
        except (OSError, ValueError, KeyError) as error:
            raise common.upstream_error(f"CSP sign-in failed: {type(error).__name__}") from error
        return status, answer if isinstance(answer, dict) else None

    def _created(self, status: int, answer: dict | None, what: str, keys: tuple[str, ...] = ()) -> dict:
        if status == 403:
            raise common.provider_rejected(f"the CSP rejected the {what}")
        if status != 201 or not answer:
            raise common.upstream_error(f"CSP wallet API answered {status}")
        if any(key not in answer for key in keys):
            raise common.upstream_error("CSP wallet API answered without the expected fields")
        return answer

    def order_wallet(self, order: dict) -> dict:
        bpn = order["bpn"]
        status, answer = self._call("POST", "/wallets", {"bpn": bpn})
        if status == 409:
            self._call("DELETE", f"/wallets/{bpn}")
            status, answer = self._call("POST", "/wallets", {"bpn": bpn})
        answer = self._created(status, answer, "wallet",
                               ("did", "participantContextId", "identityApiUrl", "apiKey"))
        return {"result": "CREATED", "did": answer["did"], "did_document_location": common.did_location(answer["did"]),
                "credential_service_url": answer.get("credentialServiceUrl"),
                "provider_ref": answer["participantContextId"],
                "secrets": {"HOLDER_ACCESS": {"url": answer["identityApiUrl"],
                                              "client_id": answer["participantContextId"],
                                              "secret": answer["apiKey"]}}}

    def order_account(self, order: dict) -> dict:
        bpn, ref = order["bpn"], order["wallet_account_ref"]
        body = {"externalId": ref, "name": order["provider_name"]}
        status, answer = self._call("POST", f"/wallets/{bpn}/accounts", body)
        if status == 409:
            self._call("DELETE", f"/wallets/{bpn}/accounts/{ref}")
            status, answer = self._call("POST", f"/wallets/{bpn}/accounts", body)
        answer = self._created(status, answer, "wallet account", ("tokenUrl", "clientId", "clientSecret"))
        return {"result": "CREATED", "token_url": answer["tokenUrl"], "client_id": answer["clientId"],
                "client_secret": answer["clientSecret"]}

    def order_account_deletion(self, account: dict) -> dict:
        status, _ = self._call("DELETE", f"/wallets/{account['bpn']}/accounts/{account['wallet_account_ref']}")
        if status not in (204, 404):                    # README 11.3: 404 counts as deleted
            raise common.upstream_error(f"CSP wallet API answered {status}")
        return {"result": "DELETED"}
