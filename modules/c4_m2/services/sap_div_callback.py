#################################################################################
#  Copyright (c) 2026 Technovative Solutions
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
#  Assisted-By: Claude Code (claude-opus-5-5)
#################################################################################
"""The wallet callback of SAP DIV (README 7.6 steps 1 to 6): only its callback client, a complete body, a DID and
DID document that fit the wallet; then the holder access is stored and the DID check starts."""
from __future__ import annotations

import os

from modules.c4_m2 import did, errors, service

DEFAULT_CALLBACK_CLIENT = "sa-div-callback"


def _callback_body_problem(body: object) -> str | None:
    """Why a callback body is malformed (openapi `SapDivWalletCallback`), None if it is complete."""
    if not isinstance(body, dict) or not isinstance(body.get("did"), str) or not body["did"]:
        return "did is required"
    if not isinstance(body.get("didDocument"), dict):
        return "didDocument is required"
    details = body.get("authenticationDetails")
    if not isinstance(details, dict):
        return "authenticationDetails is required"
    for name in ("authenticationServiceUrl", "clientID", "clientSecret"):
        if not isinstance(details.get(name), str) or not details[name]:
            return f"authenticationDetails.{name} is required"
    return None


def _callback_document_valid(document: dict) -> bool:
    """README 7.6 step 4: schema of Portal 2.6.0, `@context` list, `id`, `service` list with `id` and `type`,
    `verificationMethod` list with `id`, `type` and `publicKeyJwk` with `kty`, `crv`, `x`, `y`."""
    def text(value: object) -> bool:
        return isinstance(value, str) and value != ""
    if not isinstance(document.get("@context"), list) or not text(document.get("id")):
        return False
    services, methods = document.get("service"), document.get("verificationMethod")
    if not isinstance(services, list) or not isinstance(methods, list):
        return False
    if not all(isinstance(e, dict) and text(e.get("id")) and e.get("type") for e in services):
        return False
    for method in methods:
        jwk = method.get("publicKeyJwk") if isinstance(method, dict) else None
        if not (text(method.get("id")) if isinstance(method, dict) else False) or not method.get("type") \
                or not isinstance(jwk, dict) or not all(text(jwk.get(k)) for k in ("kty", "crv", "x", "y")):
            return False
    return True


def _sap_div_location(bpn: str, did_value: str) -> str | None:
    base = os.environ.get("SAP_DIV_DID_DOCUMENT_BASE_URL", "").strip().rstrip("/")
    return f"{base}/{bpn}/did.json" if base else service.did_web_location(did_value)


def authorize(claims: dict) -> None:
    """README 7.6: only the callback client of SAP DIV (`SAP_DIV_CALLBACK_CLIENT_ID`) may call back (403,
    nothing is audited). Token and permission are checked by the router before."""
    client = os.environ.get("SAP_DIV_CALLBACK_CLIENT_ID", "").strip() or DEFAULT_CALLBACK_CLIENT
    if claims.get("azp") != client:
        raise errors.forbidden("the calling client is not the callback client of SAP DIV")


def accept_wallet_callback(bpn: str, body: dict, claims: dict | str | None) -> None:
    """The wallet callback of SAP DIV (README 7.6 steps 1 to 6). Returns None (the route answers 204);
    raises `Problem` for 400, 404 and 409. Every accepted callback, also a duplicate, is audited."""
    problem = _callback_body_problem(body)
    if problem:
        raise errors.validation(problem)
    store = service.get_store()
    found = store.find_wallet_by_bpn(bpn)
    if found is None or found["provider"] != "SAP_DIV":
        raise errors.not_found("no SAP DIV wallet for this BPN")
    with store.transaction(found["company_id"]):
        wallet = store.get_wallet(found["company_id"])
        if wallet is None or wallet["provider"] != "SAP_DIV":
            raise errors.not_found("no SAP DIV wallet for this BPN")
        announced = body["did"]
        if wallet["status"] in ("VALIDATING", "ACTIVE"):
            if (wallet.get("did") or "").lower() != announced.lower():
                raise errors.conflict("the wallet already has another DID")
        elif wallet["status"] != "REQUESTED":
            raise errors.invalid_state("the wallet is not waiting for a callback; a new attempt is needed")
        elif not did.check_form("SAP_DIV", announced, wallet["bpn"]):
            service.fail_wallet(wallet, "DID_MISMATCH")
        elif not _callback_document_valid(body["didDocument"]):
            service.fail_wallet(wallet, did.INVALID_DID_DOCUMENT)
        else:
            details = body["authenticationDetails"]
            service.store_secret(wallet["id"], service.HOLDER_ACCESS, {"url": details["authenticationServiceUrl"],
                                                        "client_id": details["clientID"],
                                                        "secret": details["clientSecret"]})
            moment = service.now()
            wallet.update(status="VALIDATING", did=announced,
                          did_document_location=_sap_div_location(wallet["bpn"], announced),
                          credential_service_url=service.credential_service_url(body["didDocument"]),
                          validating_since=moment, next_check_at=moment)
            service.save_wallet(wallet)
            service.check_did(wallet)              # README 7.6 step 6: the check starts right after the commit
        service.audit(claims, "SUBMIT_WALLET_CALLBACK", wallet["company_id"], wallet["id"])
