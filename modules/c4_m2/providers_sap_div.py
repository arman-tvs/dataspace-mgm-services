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
"""SAP DIV adapter of C4-M2 (README 6.3, 6.11, 8.1, 8.2, 8.3, 11.1).

SAP DIV answers an order with 2xx and reports the result later by callback (7.6). With `SAP_DIV_URL` the orders go
to the middleware; without it the built-in stand-in accepts them and calls the callback code of this module itself
after `STUB_CALLBACK_DELAY_SECONDS`. `STUB_FAILURES` (README 14.3) simulates a wrong DID, a document without key,
a missing callback, a DID that cannot be resolved and a failing order.
"""
from __future__ import annotations

import os
import threading
import time
from urllib.parse import urlsplit

import httpx

from portal_common import http

from . import providers_common as common

PROVIDER = "SAP_DIV"
STANDIN_HOST = "div-stub.invalid"
STANDIN_BASE = f"https://{STANDIN_HOST}/did"
STANDIN_CREDENTIAL_SERVICE = f"https://{STANDIN_HOST}/api/credentials"
STANDIN_AUTH_URL = f"https://{STANDIN_HOST}/auth"

_lock = threading.Lock()
_token: tuple[str, float] | None = None


def reset() -> None:
    global _token
    with _lock:
        _token = None


def _base() -> str:
    return os.environ.get("SAP_DIV_DID_DOCUMENT_BASE_URL", "").strip().rstrip("/") or STANDIN_BASE


def _access_token() -> str:
    """Client credentials at the middleware (README 4, 11.1), reused until shortly before it expires."""
    global _token
    with _lock:
        if _token and _token[1] > time.time() + 30:
            return _token[0]
    try:
        response = http.request("POST", os.environ.get("SAP_DIV_TOKEN_URL", ""),
                                data={"grant_type": "client_credentials",
                                      "client_id": os.environ.get("SAP_DIV_CLIENT_ID", ""),
                                      "client_secret": os.environ.get("SAP_DIV_CLIENT_SECRET", "")})
        body = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise common.upstream_error(f"SAP DIV token endpoint: {type(error).__name__}") from error
    if response.status_code != 200 or not isinstance(body, dict) or not isinstance(body.get("access_token"), str):
        raise common.upstream_error(f"SAP DIV token endpoint answered {response.status_code}")
    try:
        lifetime = int(body.get("expires_in", 300))
    except (TypeError, ValueError):
        lifetime = 300
    with _lock:
        _token = (body["access_token"], time.time() + lifetime)
    return body["access_token"]


def _real(path: str, params: dict | None, body: dict | None) -> None:
    try:
        response = http.request("POST", os.environ["SAP_DIV_URL"].rstrip("/") + path, params=params, json=body,
                                headers={"Authorization": "Bearer " + _access_token()})
    except httpx.HTTPError as error:
        raise common.upstream_error(f"SAP DIV not reachable: {type(error).__name__}") from error
    if not 200 <= response.status_code < 300:
        raise common.upstream_error(f"SAP DIV answered {response.status_code}")


# ----------------------------------------------------------------------------------- the callbacks
def _wallet_callback(bpn: str, body: dict) -> None:
    from . import service
    service.accept_wallet_callback(bpn, body, common.MODULE)


def _account_created_callback(reference: str, body: dict) -> None:
    from . import accounts
    accounts.accept_account_created(reference, body, common.MODULE)


def _account_deleted_callback(reference: str) -> None:
    from . import accounts
    accounts.accept_account_deleted(reference, common.MODULE)


class SapDivAdapter:
    provider = PROVIDER
    supports_wallet_accounts = True
    issuance_mode = "ISSUER_WRITES"
    deletion_is_async = True

    def did_for(self, bpn: str) -> str:
        """README 6.4 step 1: `did:web:` + host and path of the DID document base (`/` as `:`) + BPN."""
        parts = urlsplit(_base())
        return f"did:web:{(parts.netloc + parts.path).strip('/').replace('/', ':')}:{bpn}"

    def callback_router(self):
        from .providers_callbacks import sap_div_router
        return sap_div_router()

    @staticmethod
    def _standin_refuses(bpn: str) -> None:
        if "ORDER_ERROR" in common.failures(bpn):
            raise common.upstream_error("SAP DIV stand-in answered 503")

    def order_wallet(self, order: dict) -> dict:
        bpn = order["bpn"]
        if os.environ.get("SAP_DIV_URL", "").strip():
            _real("/setup-dim", {"companyName": order.get("company_name") or "", "bpn": bpn,
                                 "didDocumentLocation": f"{_base()}/{bpn}/did.json"}, None)
            return {"result": "ORDERED"}
        self._standin_refuses(bpn)
        common.record_order(PROVIDER, bpn, "wallet")
        failed = common.failures(bpn)
        did = f"did:web:other.example:{bpn}" if "DID_MISMATCH" in failed else self.did_for(bpn)
        document = common.did_document(did, STANDIN_CREDENTIAL_SERVICE, with_key="INVALID_DID_DOCUMENT" not in failed)
        common.publish_document(did, document)      # `DID_NOT_RESOLVABLE` hides it in common.documents()
        if "NO_CALLBACK" not in failed:
            body = {"did": did, "didDocument": document,
                    "authenticationDetails": {"authenticationServiceUrl": STANDIN_AUTH_URL,
                                              "clientID": f"div-{bpn}", "clientSecret": common.random_secret()}}
            common.schedule(lambda: _wallet_callback(bpn, body))
        return {"result": "ORDERED"}

    def order_account(self, order: dict) -> dict:
        bpn, reference, user = order["bpn"], order["wallet_account_ref"], order["technical_user_id"]
        if os.environ.get("SAP_DIV_URL", "").strip():
            _real(f"/technical-user/{bpn}", None, {"externalId": reference, "name": order["provider_name"]})
            return {"result": "ORDERED"}
        self._standin_refuses(bpn)
        common.record_order(PROVIDER, bpn, "account", reference)
        if "NO_CALLBACK" not in common.failures(user):
            body = {"authenticationServiceUrl": STANDIN_AUTH_URL, "clientID": f"div-{user}",
                    "clientSecret": common.random_secret()}
            common.schedule(lambda: _account_created_callback(reference, body))
        return {"result": "ORDERED"}

    def order_account_deletion(self, account: dict) -> dict:
        bpn, reference, user = account["bpn"], account["wallet_account_ref"], account["technical_user_id"]
        if os.environ.get("SAP_DIV_URL", "").strip():
            _real(f"/technical-user/{bpn}/delete", None, {"externalId": reference, "name": account["provider_name"]})
            return {"result": "ORDERED"}
        self._standin_refuses(bpn)
        common.record_order(PROVIDER, bpn, "account-deletion", reference)
        if "NO_DELETE_CALLBACK" not in common.failures(user):
            common.schedule(lambda: _account_deleted_callback(reference))
        return {"result": "ORDERED"}
