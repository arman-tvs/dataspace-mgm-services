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
"""C4-M2 callbacks of SAP DIV (README 7.6, 6.2, 6.4, 6.8, 6.10, 13 cases 5, 6, 7).

`POST /api/c4-m2/callbacks/sap-div/wallets/{bpn}`. Wallets are ordered with `STUB_CALLBACK_DELAY_SECONDS`
3600 so that the stand-in does not call back by itself; the tests send the callback over HTTP (or let the
stand-in do it with `providers.flush_stand_in()`). Time is driven by the kit `Clock` on `service.now`.
OPEN-QUESTION: the DID check "in the background immediately after the commit" (README 7.6 step 6) is not
observable in a test; tests that need the end of the check call `service.run_timer_once()` (next_check_at =
now at the callback). OPEN-QUESTION: the built-in resolution finds the DID document that the SAP DIV
stand-in publishes when the order is accepted (README 11.1 "supplies the DID documents"), so a manual
callback with the stand-in's DID can reach ACTIVE.
"""
from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("modules.c4_m2.providers") is None,
    reason="not implemented yet: modules.c4_m2.providers (provider adapters)")

import json
import logging
import threading

import jwt
import pytest

from test_c4_m2_common import (COMPANIES, Clock, assert_no_secret, companies, event_errors,  # noqa: F401
                               osp_factory, seam, step_input, uuid_str)

MODULE = "c4-m2"
DIV, IH, CSPC = COMPANIES["div"], COMPANIES["ih"], COMPANIES["csp"]
FAIL01, FAIL02 = COMPANIES["fail_did"], COMPANIES["fail_no_callback"]
HOLD = {"STUB_CALLBACK_DELAY_SECONDS": "3600"}
SECRET = "callback-client-secret-do-not-leak"
X, Y = "f83OJ3D2xF1Bg8vub9tLe1gHMzV76e8Tus9uPHvRVEU", "x_FEzRu9m36HLN_tue659LNpXW6pCyStikYjKIWI5a0"


# ------------------------------------------------------------------------------------------ helpers
def m2():
    return seam("modules.c4_m2.interface")


def service():
    return seam("modules.c4_m2.service")


def providers():
    return seam("modules.c4_m2.providers")


def did_of(company: dict) -> str:
    return f"did:web:div.example.org:did:{company['bpn']}"


def did_document(did: str, endpoint: str = "https://div.example.org/api/credentials/BPNL") -> dict:
    return {"@context": ["https://www.w3.org/ns/did/v1", "https://w3id.org/security/suites/jws-2020/v1"],
            "id": did,
            "service": [{"id": f"{did}#credential-service", "type": "CredentialService",
                         "serviceEndpoint": endpoint}],
            "verificationMethod": [{"id": f"{did}#key-1", "type": "JsonWebKey2020", "controller": did,
                                    "publicKeyJwk": {"kty": "EC", "crv": "P-256", "x": X, "y": Y}}]}


def body(company: dict, did: str | None = None, document: dict | None = None, secret: str = SECRET) -> dict:
    did = did or did_of(company)
    return {"did": did, "didDocument": document if document is not None else did_document(did),
            "authenticationDetails": {"authenticationServiceUrl": "https://div.example.org/auth",
                                      "clientID": "div-client-1", "clientSecret": secret}}


def callback_path(bpn: str) -> str:
    return f"/api/c4-m2/callbacks/sap-div/wallets/{bpn}"


def div_token(osp) -> str:
    return osp.service("sa-div-callback", ["submit_wallet_callback"])


def send(osp, company_or_bpn, payload: dict, token: str | None = "default"):
    bpn = company_or_bpn["bpn"] if isinstance(company_or_bpn, dict) else company_or_bpn
    return osp.post(callback_path(bpn), div_token(osp) if token == "default" else token, json=payload)


def start(osp_factory, company: dict = DIV, env: dict | None = None, create: bool = True):
    """OSP with the SAP DIV wallet of `company` ordered (REQUESTED), no callback yet."""
    osp = osp_factory(env={**HOLD, **(env or {})})
    if create:
        m2().create_wallet(step_input(company["id"], 1, provider="SAP_DIV"))
    return osp


def order(company: dict = DIV) -> None:
    m2().create_wallet(step_input(company["id"], 1, provider="SAP_DIV"))


def row(company: dict) -> dict:
    return m2().store().get_wallet(company["id"])


def ev(osp, type_: str, company: dict | None = None) -> list[dict]:
    return [e for e in osp.events(type_) if company is None or e["data"].get("companyId") == company["id"]]


def claims(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False})


def problem_type(r) -> str:
    assert r.headers["content-type"].startswith("application/problem+json"), r.text
    return r.json()["type"]


def audit_of(azp: str) -> list[dict]:
    """Audit entries of one caller. Not absolute counts: README 5 does not say what else is audited."""
    return [e for e in m2().store().list_audit() if e.get("azp") == azp]


def snapshot(company: dict) -> dict:
    w = row(company)
    return {k: w[k] for k in ("status", "did", "failure_reason", "attempt", "validating_since", "next_check_at",
                              "did_document_location", "credential_service_url", "activated_at")}


# ----------------------------------------------------------------------- case 6: who may call back
def test_case_06_callback_without_token_is_401(osp_factory, companies):
    # README 6.8, 12
    osp = start(osp_factory)
    r = send(osp, DIV, body(DIV), token=None)
    assert r.status_code == 401
    assert row(DIV)["status"] == "REQUESTED"


def test_case_06_callback_without_the_permission_is_403(osp_factory, companies):
    # README 13 case 6, 7.6: permission `submit_wallet_callback` first
    osp = start(osp_factory)
    token = osp.service("sa-div-callback", ["query_c4_m2"])             # right client, wrong permission
    r = send(osp, DIV, body(DIV), token=token)
    assert r.status_code == 403 and problem_type(r) == "urn:c4-m2:problem:forbidden"
    assert snapshot(DIV)["status"] == "REQUESTED" and m2().store().get_secret(row(DIV)["id"], "HOLDER_ACCESS") is None


def test_case_06_other_service_account_with_the_permission_is_403(osp_factory, companies):
    # README 13 case 6, 6.8: azp must equal SAP_DIV_CALLBACK_CLIENT_ID
    osp = start(osp_factory)
    other = osp.service("sa-other-callback", ["submit_wallet_callback"])
    assert claims(other)["azp"] == "sa-other-callback"
    r = send(osp, DIV, body(DIV), token=other)
    assert r.status_code == 403 and problem_type(r) == "urn:c4-m2:problem:forbidden"
    assert row(DIV)["status"] == "REQUESTED" and row(DIV)["did"] is None
    # Our convention (TEAM3-PLAN 12.2, not README text): a 403 is not an accepted callback and is not audited.
    # OPEN-QUESTION: README 5 / 7.6 say "every callback writes an audit log entry with azp" without saying
    # whether a rejected one counts; only entries of the rejected client are looked at.
    assert audit_of("sa-other-callback") == []


def test_case_06_check_order_permission_then_client_then_lookup(osp_factory, companies):
    # README 7.6: 403 (permission, client) is decided before the wallet lookup (404)
    osp = start(osp_factory)
    unknown = "BPNL000000NOBODY"
    no_perm = osp.service("sa-div-callback", ["query_c4_m2"])
    other = osp.service("sa-other-callback", ["submit_wallet_callback"])
    assert send(osp, unknown, body(DIV), token=no_perm).status_code == 403
    assert send(osp, unknown, body(DIV), token=other).status_code == 403
    r = send(osp, unknown, body(DIV))
    assert r.status_code == 404 and problem_type(r) == "urn:c4-m2:problem:not-found"


def test_case_06_unknown_bpn_is_404(osp_factory, companies):
    # README 13 case 6, 7.6 step 1
    osp = start(osp_factory)
    r = send(osp, "BPNL000000NOBODY", body(DIV))
    assert r.status_code == 404 and problem_type(r) == "urn:c4-m2:problem:not-found"
    assert row(DIV)["status"] == "REQUESTED"


@pytest.mark.parametrize("company,provider", [(IH, "IDENTITY_HUB"), (CSPC, "CSP")])
def test_case_06_wallet_of_another_provider_is_404(osp_factory, companies, company, provider):
    # README 7.6 step 1: "wallet with this BPN and provider SAP_DIV, otherwise 404"
    osp = osp_factory(env=HOLD)
    m2().create_wallet(step_input(company["id"], 1, provider=provider))
    before = snapshot(company)
    r = send(osp, company, body(company, did=f"did:web:div.example.org:did:{company['bpn']}"))
    assert r.status_code == 404 and problem_type(r) == "urn:c4-m2:problem:not-found"
    assert snapshot(company) == before and row(company)["provider"] == provider
    assert len(ev(osp, "DataspaceWalletCreated")) == 1 and ev(osp, "DataspaceWalletFailed") == []


@pytest.mark.parametrize("payload", [
    {},
    {"did": "did:web:div.example.org:did:BPNL0000000DIV01"},
    {"did": "did:web:div.example.org:did:BPNL0000000DIV01", "didDocument": {}},
    {"did": "did:web:div.example.org:did:BPNL0000000DIV01", "didDocument": {},
     "authenticationDetails": {"authenticationServiceUrl": "https://div.example.org/auth"}},
])
def test_callback_with_a_malformed_body_is_400_validation(osp_factory, companies, payload):
    # openapi SapDivWalletCallback requires did, didDocument, authenticationDetails{3 fields}; FRAMEWORK 4.5
    osp = start(osp_factory)
    r = send(osp, DIV, payload)
    assert r.status_code == 400 and problem_type(r) == "urn:c4-m2:problem:validation"
    assert row(DIV)["status"] == "REQUESTED"


# ------------------------------------------------------------------------- the valid callback (7.6)
def test_valid_callback_stores_the_access_encrypted_and_moves_to_validating(osp_factory, companies, caplog):
    # README 7.6 steps 4 and 5, README 5 (wallet_secret), 6.2 REQUESTED -> VALIDATING.
    # DID_NOT_RESOLVABLE keeps the wallet VALIDATING so that the state after step 5 is visible.
    caplog.set_level(logging.DEBUG)                   # README 4: no secrets in logs, whatever the level
    osp = start(osp_factory, env={"STUB_FAILURES": f"{DIV['bpn']}:DID_NOT_RESOLVABLE"})
    wid = row(DIV)["id"]
    r = send(osp, DIV, body(DIV, document=did_document(did_of(DIV), "https://div.example.org/cs/v1")))
    assert r.status_code == 204 and r.content == b""
    w = row(DIV)
    assert w["status"] == "VALIDATING"
    assert w["did"] == did_of(DIV)
    assert w["did_document_location"] == "https://div.example.org/did/BPNL0000000DIV01/did.json"
    assert w["credential_service_url"] == "https://div.example.org/cs/v1"
    assert w["validating_since"] and w["next_check_at"] and w["did_validated_at"] is None
    assert w["activated_at"] is None
    secret = m2().store().get_secret(wid, "HOLDER_ACCESS")
    assert secret["url"] == "https://div.example.org/auth" and secret["client_id"] == "div-client-1"
    assert {"secret_encrypted", "nonce", "key_version"} <= set(secret)
    assert isinstance(secret["secret_encrypted"], bytes) and SECRET.encode() not in secret["secret_encrypted"]
    # OPEN-QUESTION: nonce of 12 bytes is our convention (AES-GCM default), README 5 only says `nonce bytea`
    assert len(secret["nonce"]) == 12 and secret["key_version"] == 1     # AES-GCM nonce, SECRETS_KEY_VERSION
    assert "clientSecret" not in secret and SECRET not in secret.values()
    assert seam("modules.c4_m2.crypto").decrypt(secret["secret_encrypted"], secret["nonce"],
                                                secret["key_version"]) == SECRET
    assert ev(osp, "DataspaceWalletCreated") == [] and ev(osp, "DataspaceWalletFailed") == []
    assert_no_secret(SECRET, m2().store().dump(), osp.events(), r.text, caplog.text)
    assert_no_secret(SECRET, m2().store().list_audit(), m2().store().list_step_log())


def test_valid_callback_completes_to_active_with_one_event(osp_factory, companies):
    # README 7.6 steps 5 and 6, 6.4 step 4, 6.2 VALIDATING -> ACTIVE
    osp = start(osp_factory)
    r = send(osp, DIV, body(DIV))
    assert r.status_code == 204
    assert row(DIV)["status"] in ("VALIDATING", "ACTIVE")
    service().run_timer_once()                       # the check is due at once (next_check_at = now)
    w = row(DIV)
    assert w["status"] == "ACTIVE" and w["did_validated_at"] and w["activated_at"] and w["did"] == did_of(DIV)
    created = ev(osp, "DataspaceWalletCreated")
    assert len(created) == 1 and event_errors(MODULE, created[0]) == []
    assert created[0]["data"] == {"companyId": DIV["id"], "did": did_of(DIV), "walletId": w["id"],
                                  "provider": "SAP_DIV", "bpn": DIV["bpn"],
                                  "didDocumentLocation": "https://div.example.org/did/BPNL0000000DIV01/did.json"}
    service().run_timer_once()                       # a further pass changes nothing
    assert len(ev(osp, "DataspaceWalletCreated")) == 1
    assert m2().get_wallet_info(companyId=DIV["id"])["did"] == created[0]["data"]["did"]


def test_callback_driven_completion_in_the_default_flow(osp_factory, companies):
    # README 11.1: the stand-in calls the callback code itself; create-wallet SAP_DIV -> ... -> ACTIVE
    osp = start(osp_factory)
    assert row(DIV)["status"] == "REQUESTED"
    providers().flush_stand_in()
    assert row(DIV)["status"] in ("VALIDATING", "ACTIVE")      # README 7.6 step 6: background check after the commit
    service().run_timer_once()
    w = row(DIV)
    assert w["status"] == "ACTIVE" and w["did"] == did_of(DIV)
    secret = m2().store().get_secret(w["id"], "HOLDER_ACCESS")        # the stand-in's made-up access
    assert secret and secret["secret_encrypted"] and secret["nonce"] and secret["key_version"] == 1
    assert len(ev(osp, "DataspaceWalletCreated")) == 1
    info = m2().get_wallet_info(companyId=DIV["id"])
    assert info["issuanceMode"] == "ISSUER_WRITES" and info["credentialServiceUrl"] == w["credential_service_url"]
    assert w["credential_service_url"]               # service CredentialService of the stand-in's document


def test_bpn_in_the_did_is_compared_case_insensitively(osp_factory, companies):
    # README 6.4 step 1 (SAP DIV): "case does not matter"
    osp = start(osp_factory, env={"STUB_FAILURES": f"{DIV['bpn']}:DID_NOT_RESOLVABLE"})
    did = f"did:web:DIV.example.org:did:{DIV['bpn'].lower()}"
    assert send(osp, DIV, body(DIV, did=did)).status_code == 204
    assert row(DIV)["status"] == "VALIDATING" and ev(osp, "DataspaceWalletFailed") == []


# -------------------------------------------------------------------------------------- audit log
def test_every_accepted_callback_writes_an_audit_entry_with_azp_and_no_secret(osp_factory, companies):
    # README 5 audit_log, 7.6 "Every callback writes an audit log entry with azp", 13 case 6
    osp = start(osp_factory, env={"STUB_FAILURES": f"{DIV['bpn']}:DID_NOT_RESOLVABLE"})
    token = div_token(osp)
    c = claims(token)
    assert send(osp, DIV, body(DIV), token=token).status_code == 204
    entries = audit_of("sa-div-callback")            # only this caller: the order itself may be audited too
    assert len(entries) == 1
    e = entries[0]
    assert {"occurred_at", "sub", "azp", "company_id", "operation", "object_id"} <= set(e)
    assert e["azp"] == "sa-div-callback" == c["azp"] and e["sub"] == c["sub"]
    assert e["company_id"] == DIV["id"] and e["occurred_at"] and e["operation"]
    # OPEN-QUESTION: README 5 says "object ID"; the object of this callback is the wallet (its id) or its BPN
    assert e["object_id"] in (row(DIV)["id"], DIV["bpn"])
    assert_no_secret(SECRET, entries)
    # a duplicate is an accepted callback too (204)
    assert send(osp, DIV, body(DIV), token=token).status_code == 204
    assert len(audit_of("sa-div-callback")) == 2
    assert_no_secret(SECRET, m2().store().list_audit(), m2().store().dump())


# ---------------------------------------------------------------------------------- repeated callbacks
def test_duplicate_callback_while_validating_is_204_without_change(osp_factory, companies):
    # README 7.6 step 2, 6.9 "Same content: 204 without change"
    osp = start(osp_factory, env={"STUB_FAILURES": f"{DIV['bpn']}:DID_NOT_RESOLVABLE"})
    assert send(osp, DIV, body(DIV)).status_code == 204
    before, secret = snapshot(DIV), m2().store().get_secret(row(DIV)["id"], "HOLDER_ACCESS")
    r = send(osp, DIV, body(DIV, secret="a-different-secret-in-the-repeat"))
    assert r.status_code == 204
    assert snapshot(DIV) == before                                          # nothing changed
    assert m2().store().get_secret(row(DIV)["id"], "HOLDER_ACCESS") == secret
    assert osp.events("DataspaceWalletCreated") == [] and osp.events("DataspaceWalletFailed") == []


def test_duplicate_callback_when_active_is_204_without_second_event(osp_factory, companies):
    # README 7.6 step 2 (ACTIVE with the same DID)
    osp = start(osp_factory)
    providers().flush_stand_in()
    service().run_timer_once()
    before = snapshot(DIV)
    assert before["status"] == "ACTIVE"
    r = send(osp, DIV, body(DIV))
    assert r.status_code == 204
    assert snapshot(DIV) == before and len(ev(osp, "DataspaceWalletCreated")) == 1
    assert ev(osp, "DataspaceWalletFailed") == [] and len(providers().orders()) == 1


@pytest.mark.parametrize("status", ["VALIDATING", "ACTIVE"])
def test_callback_with_another_did_is_409_conflict(osp_factory, companies, status):
    # README 7.6 step 2: VALIDATING or ACTIVE with another DID -> 409 conflict
    osp = start(osp_factory, env={"STUB_FAILURES": f"{DIV['bpn']}:DID_NOT_RESOLVABLE"} if status == "VALIDATING" else None)
    if status == "VALIDATING":
        assert send(osp, DIV, body(DIV)).status_code == 204
    else:
        providers().flush_stand_in()
        service().run_timer_once()
    assert row(DIV)["status"] == status
    before = snapshot(DIV)
    other = "did:web:div.example.org:did:BPNL0000000DIV02"
    r = send(osp, DIV, body(DIV, did=other))
    assert r.status_code == 409 and problem_type(r) == "urn:c4-m2:problem:conflict"
    assert snapshot(DIV) == before and row(DIV)["did"] == did_of(DIV)
    assert ev(osp, "DataspaceWalletFailed") == []


def test_callback_for_a_failed_wallet_is_409_invalid_state(osp_factory, companies):
    # README 7.6 step 2: FAILED -> 409 invalid-state (a new attempt is needed)
    osp = start(osp_factory, FAIL01, env={"STUB_FAILURES": f"{FAIL01['bpn']}:DID_MISMATCH"})
    providers().flush_stand_in()
    assert row(FAIL01)["status"] == "FAILED"
    r = send(osp, FAIL01, body(FAIL01))
    assert r.status_code == 409 and problem_type(r) == "urn:c4-m2:problem:invalid-state"
    assert row(FAIL01)["status"] == "FAILED" and row(FAIL01)["failure_reason"] == "DID_MISMATCH"
    assert m2().store().get_secret(row(FAIL01)["id"], "HOLDER_ACCESS") is None
    assert len(ev(osp, "DataspaceWalletFailed")) == 1 and ev(osp, "DataspaceWalletCreated") == []


# ------------------------------------------------------------------------------ wrong DID, bad document
@pytest.mark.parametrize("wrong", [
    "did:web:other.example:BPNL0000000DIV01",                      # the stand-in's DID_MISMATCH value
    "did:web:div.example.org:did:BPNL0000000DIV99",                # other BPN
    "did:web:div.example.org:BPNL0000000DIV01",                    # path of SAP_DIV_DID_DOCUMENT_BASE_URL missing
    "did:web:div.example.org:did:BPNL0000000DIV01:extra",
    "did:web:ih.example.org:BPNL0000000DIV01",                     # IdentityHub form
    "did:key:z6Mkexample",
])
def test_case_04_callback_with_wrong_did_form_is_204_and_fails_with_did_mismatch(osp_factory, companies, wrong):
    # README 7.6 step 3, 6.2, 6.4 step 1 ("without further attempts"), openapi: 204 although FAILED
    osp = start(osp_factory)
    r = send(osp, DIV, body(DIV, did=wrong))
    assert r.status_code == 204
    w = row(DIV)
    assert w["status"] == "FAILED" and w["failure_reason"] == "DID_MISMATCH"
    failed = ev(osp, "DataspaceWalletFailed")
    assert len(failed) == 1 and event_errors(MODULE, failed[0]) == []
    assert failed[0]["data"] == {"companyId": DIV["id"], "walletId": w["id"], "provider": "SAP_DIV",
                                 "reason": "DID_MISMATCH"}
    assert m2().store().get_secret(w["id"], "HOLDER_ACCESS") is None
    service().run_timer_once()                                    # no further attempts
    assert row(DIV)["status"] == "FAILED" and len(ev(osp, "DataspaceWalletFailed")) == 1
    assert ev(osp, "DataspaceWalletCreated") == []
    assert len(audit_of("sa-div-callback")) == 1                  # accepted (204), so it is audited


def _drop(key):
    def f(doc):
        doc.pop(key)
    return f


def _vm(mutation):
    def f(doc):
        mutation(doc["verificationMethod"][0])
    return f


# README 7.6 step 4 checks the callback BODY: `@context` list, `id`, `service` list with `id` and `type`,
# `verificationMethod` list with `id`, `type`, `publicKeyJwk` with `kty`, `crv`, `x`, `y`.
# OPEN-QUESTION: openapi marks @context, id, service, verificationMethod as `required` inside `didDocument` (a
# schema check would answer 400 `validation`), README 7.6 step 4 wants 204 + FAILED/INVALID_DID_DOCUMENT: the
# route must not enforce the inner `required` list of didDocument. We expect 204.
INVALID_DOCS = {
    "no @context": _drop("@context"),
    "@context not a list": lambda d: d.update({"@context": "https://www.w3.org/ns/did/v1"}),
    "no id": _drop("id"),
    "no service list": _drop("service"),
    "service without type": lambda d: d["service"][0].pop("type"),
    "service without id": lambda d: d["service"][0].pop("id"),
    "no verificationMethod": _drop("verificationMethod"),
    "verificationMethod without id": _vm(lambda v: v.pop("id")),
    "verificationMethod without type": _vm(lambda v: v.pop("type")),
    "verificationMethod without publicKeyJwk": _vm(lambda v: v.pop("publicKeyJwk")),
    "publicKeyJwk without kty": _vm(lambda v: v["publicKeyJwk"].pop("kty")),
    "publicKeyJwk without crv": _vm(lambda v: v["publicKeyJwk"].pop("crv")),
    "publicKeyJwk without x": _vm(lambda v: v["publicKeyJwk"].pop("x")),
    "publicKeyJwk without y": _vm(lambda v: v["publicKeyJwk"].pop("y")),
}


@pytest.mark.parametrize("what", sorted(INVALID_DOCS))
def test_callback_with_invalid_did_document_is_204_and_fails_with_invalid_did_document(osp_factory, companies, what):
    # README 7.6 step 4 (schema of Portal 2.6.0), 6.2, 6.4 step 3 "without further attempts"
    osp = start(osp_factory)
    doc = did_document(did_of(DIV))
    INVALID_DOCS[what](doc)
    r = send(osp, DIV, body(DIV, document=doc))
    assert r.status_code == 204
    w = row(DIV)
    assert w["status"] == "FAILED" and w["failure_reason"] == "INVALID_DID_DOCUMENT"
    failed = ev(osp, "DataspaceWalletFailed")
    assert len(failed) == 1 and event_errors(MODULE, failed[0]) == []
    assert failed[0]["data"]["reason"] == "INVALID_DID_DOCUMENT" and failed[0]["data"]["walletId"] == w["id"]
    assert m2().store().get_secret(w["id"], "HOLDER_ACCESS") is None
    service().run_timer_once()
    assert row(DIV)["status"] == "FAILED" and ev(osp, "DataspaceWalletCreated") == []
    assert len(ev(osp, "DataspaceWalletFailed")) == 1


@pytest.mark.parametrize("what,mutation", [
    ("id differs from the DID", lambda d: d.update({"id": "did:web:div.example.org:did:BPNL0000000DIV99"})),
    ("empty verificationMethod", lambda d: d.update({"verificationMethod": []})),
])
def test_resolved_document_content_is_checked_by_the_did_check_not_by_the_callback(osp_factory, companies, tmp_path,
                                                                                 monkeypatch, what, mutation):
    # README 6.4 step 3 on the RESOLVED document: `id` equals the DID, at least one verificationMethod with
    # publicKeyJwk. The callback body below is valid (7.6 step 4), so the wallet goes VALIDATING; the document the
    # resolution finds (TEST_DID_DOCUMENTS_DIR, file name = host, README 11.4) is the invalid one.
    # OPEN-QUESTION: the directory is used first (README 4 "before any resolution"), see test_c4_m2_providers.
    bad = did_document(did_of(DIV))
    mutation(bad)
    (tmp_path / "dids").mkdir()
    (tmp_path / "dids" / "div.example.org.json").write_text(json.dumps(bad))
    osp = start(osp_factory, env={"TEST_DID_DOCUMENTS_DIR": str(tmp_path / "dids")})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    r = send(osp, DIV, body(DIV))                                  # valid body
    assert r.status_code == 204
    assert row(DIV)["status"] in ("VALIDATING", "FAILED")          # the background check may already have run
    service().run_timer_once()
    w = row(DIV)
    assert w["status"] == "FAILED" and w["failure_reason"] == "INVALID_DID_DOCUMENT", what
    failed = ev(osp, "DataspaceWalletFailed")
    assert len(failed) == 1 and event_errors(MODULE, failed[0]) == []
    assert failed[0]["data"]["reason"] == "INVALID_DID_DOCUMENT"
    clock.advance(minutes=30)                                      # without further attempts
    service().run_timer_once()
    assert row(DIV)["status"] == "FAILED" and len(ev(osp, "DataspaceWalletFailed")) == 1
    assert ev(osp, "DataspaceWalletCreated") == []


def test_wrong_did_is_checked_before_the_document(osp_factory, companies):
    # README 7.6 order: step 3 (DID form) before step 4 (document)
    # OPEN-QUESTION: didDocument={"id": "x"} lacks fields that openapi marks `required` (see INVALID_DOCS): 204 expected
    osp = start(osp_factory)
    wrong = "did:web:other.example:BPNL0000000DIV01"
    assert send(osp, DIV, body(DIV, did=wrong, document={"id": "x"})).status_code == 204
    assert row(DIV)["failure_reason"] == "DID_MISMATCH"


# ------------------------------------------------------------------ case 5: no callback, deadline
def test_case_05_no_callback_fails_with_provider_timeout_from_the_timer(osp_factory, companies, monkeypatch):
    # README 13 case 5, 6.2, 6.10 "Callback deadline wallet", 14.3 NO_CALLBACK
    osp = start(osp_factory, FAIL02, create=False, env={"STUB_FAILURES": f"{FAIL02['bpn']}:NO_CALLBACK",
                                          "PROVIDER_CALLBACK_TIMEOUT_MINUTES": "1"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")   # before the order: its time is patched time
    order(FAIL02)
    providers().flush_stand_in()                      # the stand-in does not call back (NO_CALLBACK)
    assert row(FAIL02)["status"] == "REQUESTED" and row(FAIL02)["provider_ordered_at"]

    clock.advance(seconds=30)
    service().run_timer_once()
    assert row(FAIL02)["status"] == "REQUESTED" and osp.events("DataspaceWalletFailed") == []

    clock.advance(seconds=90)                         # 2 minutes after the order: beyond the 1 minute deadline
    service().run_timer_once()                        # nobody reads the wallet: the timer alone fires the event
    w = row(FAIL02)
    assert w["status"] == "FAILED" and w["failure_reason"] == "PROVIDER_TIMEOUT"
    failed = ev(osp, "DataspaceWalletFailed")
    assert len(failed) == 1 and event_errors(MODULE, failed[0]) == []
    assert failed[0]["data"] == {"companyId": FAIL02["id"], "walletId": w["id"], "provider": "SAP_DIV",
                                 "reason": "PROVIDER_TIMEOUT"}
    service().run_timer_once()                        # exactly one event
    assert len(ev(osp, "DataspaceWalletFailed")) == 1 and ev(osp, "DataspaceWalletCreated") == []

    r = send(osp, FAIL02, body(FAIL02))               # late callback
    assert r.status_code == 409 and problem_type(r) == "urn:c4-m2:problem:invalid-state"
    assert row(FAIL02)["status"] == "FAILED" and row(FAIL02)["failure_reason"] == "PROVIDER_TIMEOUT"
    assert m2().store().get_secret(w["id"], "HOLDER_ACCESS") is None


def test_case_05_timer_does_not_touch_a_wallet_that_got_its_callback(osp_factory, companies, monkeypatch):
    # README 6.10: the deadline task selects REQUESTED only
    osp = start(osp_factory, create=False, env={"PROVIDER_CALLBACK_TIMEOUT_MINUTES": "1"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    order()
    providers().flush_stand_in()
    assert row(DIV)["status"] == "ACTIVE"
    clock.advance(hours=3)
    service().run_timer_once()
    assert row(DIV)["status"] == "ACTIVE" and osp.events("DataspaceWalletFailed") == []


# ------------------------------------------------------------------ case 7: DID not resolvable
def test_case_07_did_not_resolvable_stays_validating_then_fails_at_the_deadline(osp_factory, companies, monkeypatch):
    # README 13 case 7, 6.4 (interval, deadline counted from validating_since), 6.10 "DID check", 14.3.
    # OPEN-QUESTION: README 4 gives DID_VALIDATION_MAX_HOURS in hours, case 7 says "deadline 2 minutes":
    # the deadline is 1 hour here and the clock is advanced; the interval is 10 minutes.
    osp = start(osp_factory, create=False, env={"STUB_FAILURES": f"{DIV['bpn']}:DID_NOT_RESOLVABLE",
                                                "DID_VALIDATION_INTERVAL_MINUTES": "10",
                                                "DID_VALIDATION_MAX_HOURS": "1"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    order()
    providers().flush_stand_in()                      # callback of the stand-in, DID check starts
    w = row(DIV)
    assert w["status"] == "VALIDATING" and w["validating_since"] and w["did_validated_at"] is None
    assert ev(osp, "DataspaceWalletCreated") == [] and ev(osp, "DataspaceWalletFailed") == []
    for minutes in (11, 15, 20):                      # 11, 26, 46 minutes after the start: within the deadline
        clock.advance(minutes=minutes)
        service().run_timer_once()
        w = row(DIV)
        assert w["status"] == "VALIDATING" and w["failure_reason"] is None and w["did_validated_at"] is None
        assert w["next_check_at"]
        assert osp.events("DataspaceWalletFailed") == [] and osp.events("DataspaceWalletCreated") == []
    clock.advance(minutes=20)                         # 66 minutes: beyond DID_VALIDATION_MAX_HOURS = 1
    service().run_timer_once()                        # nobody reads the wallet
    w = row(DIV)
    assert w["status"] == "FAILED" and w["failure_reason"] == "DID_NOT_RESOLVABLE"
    failed = ev(osp, "DataspaceWalletFailed")
    assert len(failed) == 1 and event_errors(MODULE, failed[0]) == []
    assert failed[0]["data"] == {"companyId": DIV["id"], "walletId": w["id"], "provider": "SAP_DIV",
                                 "reason": "DID_NOT_RESOLVABLE"}
    clock.advance(hours=1)
    service().run_timer_once()
    assert len(ev(osp, "DataspaceWalletFailed")) == 1 and ev(osp, "DataspaceWalletCreated") == []


def test_case_07_resolvable_again_before_the_deadline_becomes_active(osp_factory, companies, monkeypatch):
    # README 6.4 step 2: "No result: next attempt at the next interval" (the later attempt can succeed)
    osp = start(osp_factory, create=False, env={"STUB_FAILURES": f"{DIV['bpn']}:DID_NOT_RESOLVABLE",
                                                "DID_VALIDATION_INTERVAL_MINUTES": "10",
                                                "DID_VALIDATION_MAX_HOURS": "1"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    order()
    providers().flush_stand_in()
    assert row(DIV)["status"] == "VALIDATING"
    clock.advance(minutes=11)
    service().run_timer_once()
    assert row(DIV)["status"] == "VALIDATING"
    monkeypatch.setenv("STUB_FAILURES", "")           # the document becomes resolvable
    clock.advance(minutes=11)
    service().run_timer_once()
    w = row(DIV)
    assert w["status"] == "ACTIVE" and w["did_validated_at"] and w["activated_at"]
    assert len(ev(osp, "DataspaceWalletCreated")) == 1 and ev(osp, "DataspaceWalletFailed") == []


def test_case_07_invalid_document_content_fails_at_once_without_further_attempts(osp_factory, companies, monkeypatch):
    # README 6.4 step 3, 14.3 INVALID_DID_DOCUMENT (document without verificationMethod)
    osp = start(osp_factory, create=False, env={"STUB_FAILURES": f"{DIV['bpn']}:INVALID_DID_DOCUMENT",
                                                "DID_VALIDATION_INTERVAL_MINUTES": "10",
                                                "DID_VALIDATION_MAX_HOURS": "1"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    order()
    providers().flush_stand_in()
    w = row(DIV)
    assert w["status"] == "FAILED" and w["failure_reason"] == "INVALID_DID_DOCUMENT"   # no waiting for a deadline
    failed = ev(osp, "DataspaceWalletFailed")
    assert len(failed) == 1 and failed[0]["data"]["reason"] == "INVALID_DID_DOCUMENT"
    assert event_errors(MODULE, failed[0]) == []
    clock.advance(minutes=30)
    service().run_timer_once()
    assert row(DIV)["status"] == "FAILED" and len(ev(osp, "DataspaceWalletFailed")) == 1
    assert ev(osp, "DataspaceWalletCreated") == []


# ------------------------------------------------------------------------ README 6.9 concurrent callbacks
def test_two_concurrent_identical_callbacks_make_one_did_check_and_one_event(osp_factory, companies):
    # README 6.9: callbacks for the same company never run at the same time; "same content: 204 without change"
    osp = start(osp_factory)
    token = div_token(osp)
    barrier = threading.Barrier(2)
    codes: list = []
    errors: list = []

    def work() -> None:
        try:
            barrier.wait(timeout=5)
            codes.append(send(osp, DIV, body(DIV), token=token).status_code)
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=work) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    assert not errors and codes == [204, 204]
    service().run_timer_once()
    service().run_timer_once()                       # a second pass would be a second check if one were left over
    assert row(DIV)["status"] == "ACTIVE" and row(DIV)["attempt"] == 1
    assert len(ev(osp, "DataspaceWalletCreated")) == 1 and ev(osp, "DataspaceWalletFailed") == []
    assert m2().store().get_secret(row(DIV)["id"], "HOLDER_ACCESS")          # stored once, by the first callback
