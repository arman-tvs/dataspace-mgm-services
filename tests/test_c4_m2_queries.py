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
"""C4-M2 queries and views: `get_wallet_info`, `wallet_view` (`GET /companies/{companyId}/wallet`),
`get_holder_access` (case 23) and their HTTP paths (README 6.8, 7.1, 9.1, 9.3, openapi `WalletInfo`, `Wallet`,
`HolderAccess`).
"""
from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("modules.c4_m2.providers") is None,
    reason="not implemented yet: modules.c4_m2.providers (provider adapters)")

import json
import logging
import re
import uuid

import pytest

from portal_common.problems import Problem
from test_c4_m2_common import (COMPANIES, assert_no_secret, companies, osp_factory, schema_errors, seam,
                               step_input)
from tools.keys import ec_jwk

BDRS = "https://bdrs.example.org/api/directory"
STS = "https://ih.example.org/api/sts/token"
WALLET_INFO_FIELDS = {"walletId", "companyId", "bpn", "provider", "providerRef", "status", "did", "didDocumentLocation",
                      "credentialServiceUrl", "issuanceMode", "supportsWalletAccounts", "failureReason", "activatedAt"}
WALLET_VIEW_FIELDS = {"companyId", "provider", "status", "did", "didDocumentLocation", "credentialServiceUrl", "bdrsUrl",
                      "stsTokenUrl", "supportsWalletAccounts", "failureReason", "createdAt", "activatedAt"}
ENV = {"BDRS_PUBLIC_URL": BDRS, "IDENTITYHUB_STS_TOKEN_URL": STS, "STUB_CALLBACK_DELAY_SECONDS": "3600"}

#            key   provider        issuance mode      DID
CASES = [("div", "SAP_DIV", "ISSUER_WRITES", "did:web:div.example.org:did:BPNL0000000DIV01"),
         ("ih", "IDENTITY_HUB", "HOLDER_REQUESTS", "did:web:ih.example.org:BPNL00000000IH01"),
         ("csp", "CSP", "HOLDER_REQUESTS", "did:web:csp-wallet.example.org:BPNLIUK2REMLK3F4")]
IDS = [c[1] for c in CASES]


def create(osp, key, provider, n=1):
    cid = COMPANIES[key]["id"]
    r = osp.post("/api/c4-m2/steps/create-wallet", osp.service("svc-c4-m2"),
                 json=step_input(cid, n, companyId=cid, provider=provider))
    assert r.status_code == 200, r.text
    return r.json()


def activate(osp, key, provider):
    """create-wallet, then let the built-in SAP DIV stand-in call back (the others are ACTIVE in the call)."""
    create(osp, key, provider)
    seam("modules.c4_m2.providers").flush_stand_in()
    seam("modules.c4_m2.service").run_timer_once()
    info = seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES[key]["id"])
    assert info["status"] == "ACTIVE", info
    return info


def holder_http(osp, key, token=None):
    return osp.get(f"/api/c4-m2/internal/wallets/{COMPANIES[key]['id']}/holder-access",
                   token or osp.service("svc-c4-m1"))


# ============================================================================================ WalletInfo
@pytest.mark.parametrize("key,provider,mode,did", CASES, ids=IDS)
def test_get_wallet_info_returns_exactly_the_wallet_info_fields(osp_factory, companies, key, provider, mode, did):
    # README 9.1; TEAM3-PLAN 6.3 "13 contract fields"
    osp = osp_factory(env=ENV)
    activate(osp, key, provider)
    info = seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES[key]["id"])
    assert set(info) == WALLET_INFO_FIELDS
    assert schema_errors("c4-m2", "WalletInfo", info) == []
    assert not [k for k in info if k.startswith("_")]
    assert (info["provider"], info["issuanceMode"], info["did"]) == (provider, mode, did)
    assert info["companyId"] == COMPANIES[key]["id"] and info["bpn"] == COMPANIES[key]["bpn"]
    assert str(uuid.UUID(info["walletId"])) == info["walletId"]
    assert info["status"] == "ACTIVE" and info["failureReason"] is None and info["activatedAt"]
    assert info["supportsWalletAccounts"] is True        # README 6.11: yes for all three adapters
    # README 5: did_document_location is derived from the DID (did:web rules: host/path/did.json)
    host_path = did.removeprefix("did:web:").replace(":", "/")
    assert info["didDocumentLocation"] == f"https://{host_path}/did.json"
    assert info["credentialServiceUrl"] and info["credentialServiceUrl"].startswith("http")


@pytest.mark.parametrize("key,provider,providerRef", [("div", "SAP_DIV", "BPNL0000000DIV01"),
                                                      ("ih", "IDENTITY_HUB", "BPNL00000000IH01")], ids=["SAP_DIV", "IDENTITY_HUB"])
def test_get_wallet_info_provider_ref(osp_factory, companies, key, provider, providerRef):
    # README 5 `provider_ref`: SAP DIV the BPN; IdentityHub the participant context (= BPN, case 9)
    osp = osp_factory(env=ENV)
    activate(osp, key, provider)
    assert seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES[key]["id"])["providerRef"] == providerRef


def test_get_wallet_info_provider_ref_of_the_csp_is_the_participant_context(osp_factory, companies):
    osp = osp_factory(env=ENV)
    info = activate(osp, "csp", "CSP")
    access = seam("modules.c4_m2.interface").get_holder_access(companyId=COMPANIES["csp"]["id"])
    assert info["providerRef"] and info["providerRef"] == access["participantContextId"]


def test_get_wallet_info_while_requested_has_no_did_and_no_secret(osp_factory, companies):
    # README 6.2 REQUESTED: SAP DIV order sent, callback pending; schema allows null did, location, activatedAt
    osp = osp_factory(env=ENV)
    create(osp, "div", "SAP_DIV")
    info = seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES["div"]["id"])
    assert set(info) == WALLET_INFO_FIELDS and schema_errors("c4-m2", "WalletInfo", info) == []
    assert info["status"] == "REQUESTED"
    assert info["did"] is None and info["activatedAt"] is None and info["failureReason"] is None


def test_get_wallet_info_contains_no_secret_of_any_provider(osp_factory, companies, caplog):
    # README 9.1 "No secrets"
    osp = osp_factory(env=ENV)
    secrets = []
    for key, provider, *_ in CASES:
        activate(osp, key, provider)
        access = seam("modules.c4_m2.interface").get_holder_access(companyId=COMPANIES[key]["id"])
        secrets += [access.get("apiKey") or access["clientSecret"]]
    crypto, store = seam("modules.c4_m2.crypto"), seam("modules.c4_m2.interface").store()
    for key, *_ in CASES:
        wid = seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES[key]["id"])["walletId"]
        row = store.get_secret(wid, "STS_ACCESS")
        if row:
            secrets.append(crypto.decrypt(row["secret_encrypted"], row["nonce"], row["key_version"]))
    assert len(secrets) == 4 and all(len(s) >= 8 for s in secrets)
    for key, *_ in CASES:
        info = seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES[key]["id"])
        for s in secrets:
            assert_no_secret(s, info, osp.get(f"/api/c4-m2/internal/wallets/{COMPANIES[key]['id']}",
                                              osp.service("svc-c4-m2")).text)


def test_get_wallet_info_without_wallet_is_404_not_found(osp_factory, companies):
    # README 9.1 "No wallet: 404"
    osp_factory(env=ENV)
    with pytest.raises(Problem) as err:
        seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES["div"]["id"])
    assert err.value.status == 404 and err.value.name == "not-found"


def test_internal_wallet_query_over_http_needs_query_c4_m2(osp_factory, companies):
    # README 6.8: `GET /internal/wallets/{companyId}` needs `query_c4_m2`
    osp = osp_factory(env=ENV)
    activate(osp, "ih", "IDENTITY_HUB")
    path = f"/api/c4-m2/internal/wallets/{COMPANIES['ih']['id']}"
    ok = osp.get(path, osp.service("svc-c4-m2"))
    assert ok.status_code == 200 and schema_errors("c4-m2", "WalletInfo", ok.json()) == []
    assert ok.json() == seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES["ih"]["id"])
    assert osp.get(path, osp.service("sa-only-steps", ["execute_steps_c4_m2"])).status_code == 403
    assert osp.get(path, osp.service("sa-query", ["query_c4_m2"])).status_code == 200
    assert osp.get(path).status_code == 401
    person = osp.person("p-it", ["IT Admin"], company_id=COMPANIES["ih"]["id"])
    assert osp.get(path, person).status_code == 403
    missing = osp.get(f"/api/c4-m2/internal/wallets/{COMPANIES['div']['id']}", osp.service("svc-c4-m2"))
    assert missing.status_code == 404 and missing.json()["type"] == "urn:c4-m2:problem:not-found"


# ================================================================== GET /companies/{companyId}/wallet
@pytest.mark.parametrize("key,provider,mode,did", CASES, ids=IDS)
def test_own_wallet_view_uses_the_wallet_schema_not_wallet_info(osp_factory, companies, key, provider, mode, did):
    # README 7.1 / openapi `Wallet`: different schema than `WalletInfo`
    osp = osp_factory(env=ENV)
    activate(osp, key, provider)
    cid = COMPANIES[key]["id"]
    token = osp.person("p-own", ["IT Admin"], company_id=cid)
    r = osp.get(f"/api/c4-m2/companies/{cid}/wallet", token)
    assert r.status_code == 200, r.text
    body = r.json()
    assert schema_errors("c4-m2", "Wallet", body) == []
    assert not {"walletId", "bpn", "providerRef", "issuanceMode"} & set(body)
    assert set(body) <= WALLET_VIEW_FIELDS and {"companyId", "provider", "status", "supportsWalletAccounts", "createdAt"} <= set(body)
    assert (body["companyId"], body["provider"], body["status"], body["did"]) == (cid, provider, "ACTIVE", did)
    assert body["bdrsUrl"] == BDRS                                      # README 7.1: BDRS_PUBLIC_URL
    assert body["supportsWalletAccounts"] is True
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", body["createdAt"]) and body["activatedAt"]
    assert body.get("stsTokenUrl") == (STS if provider == "IDENTITY_HUB" else None)   # README 7.1: IdentityHub only (property optional)
    assert body["didDocumentLocation"].startswith("https://") and body["credentialServiceUrl"]
    assert body == seam("modules.c4_m2.interface").wallet_view(companyId=cid)


def test_own_wallet_view_bdrs_url_is_empty_without_configuration(osp_factory, companies):
    osp = osp_factory(env={**ENV, "BDRS_PUBLIC_URL": ""})
    activate(osp, "csp", "CSP")
    cid = COMPANIES["csp"]["id"]
    body = osp.get(f"/api/c4-m2/companies/{cid}/wallet", osp.person("p-own", ["IT Admin"], company_id=cid)).json()
    assert body.get("bdrsUrl") is None and schema_errors("c4-m2", "Wallet", body) == []


def test_own_wallet_view_contains_no_secret(osp_factory, companies):
    osp = osp_factory(env=ENV)
    activate(osp, "ih", "IDENTITY_HUB")
    cid = COMPANIES["ih"]["id"]
    api_key = seam("modules.c4_m2.interface").get_holder_access(companyId=cid)["apiKey"]
    r = osp.get(f"/api/c4-m2/companies/{cid}/wallet", osp.person("p-own", ["Company Admin"], company_id=cid))
    assert r.status_code == 200
    assert_no_secret(api_key, r.text)


def test_own_wallet_view_company_scope_and_permissions(osp_factory, companies):
    # README 7.1 step 1; case 15 persons: P1 own company, P2 other company, P3 without company, P4 `Member`
    osp = osp_factory(env=ENV)
    activate(osp, "csp", "CSP")
    csp_id, ih_id = COMPANIES["csp"]["id"], COMPANIES["ih"]["id"]
    path = f"/api/c4-m2/companies/{csp_id}/wallet"
    assert osp.get(path, osp.person("p1", ["IT Admin"], company_id=csp_id)).status_code == 200
    assert osp.get(path, osp.person("p1b", ["Company Admin"], company_id=csp_id)).status_code == 200
    other = osp.get(path, osp.person("p2", ["IT Admin"], company_id=ih_id))
    assert other.status_code == 404 and other.json()["type"] == "urn:c4-m2:problem:not-found"
    no_company = osp.get(path, osp.person("p3", ["IT Admin"], company_id=None))
    assert no_company.status_code == 404 and no_company.json()["type"] == "urn:c4-m2:problem:not-found"
    member = osp.get(path, osp.person("p4", ["Member"], company_id=csp_id))
    assert member.status_code == 403 and member.json()["type"] == "urn:c4-m2:problem:forbidden"
    assert osp.get(path, osp.person("p5", ["Applicant"], company_id=None)).status_code == 403   # permission before company
    unauth = osp.get(path)
    assert unauth.status_code == 401 and unauth.json()["type"] == "urn:c4-m2:problem:unauthorized"


def test_own_wallet_view_company_without_wallet_is_404(osp_factory, companies):
    # README 7.1 step 2
    osp = osp_factory(env=ENV)
    cid = COMPANIES["div"]["id"]
    r = osp.get(f"/api/c4-m2/companies/{cid}/wallet", osp.person("p-div", ["IT Admin"], company_id=cid))
    assert r.status_code == 404 and r.json()["type"] == "urn:c4-m2:problem:not-found"


# ================================================================================== get_holder_access
def _div_callback_body(did, bpn):
    pub = {k: v for k, v in ec_jwk("div-key")[1].items() if k in ("kty", "crv", "x", "y")}
    return {"did": did, "authenticationDetails": {"authenticationServiceUrl": "https://auth.div.example.org/oauth",
                                                  "clientID": "div-client-42", "clientSecret": "div-SECRET-9f8e7d6c5b"},
            "didDocument": {"@context": ["https://www.w3.org/ns/did/v1"], "id": did,
                            "service": [{"id": f"{did}#credential-service", "type": "CredentialService",
                                         "serviceEndpoint": f"https://div.example.org/api/credentials/{bpn}"}],
                            "verificationMethod": [{"id": f"{did}#key-1", "type": "JsonWebKey2020", "controller": did,
                                                    "publicKeyJwk": pub}]}}


@pytest.fixture
def div_with_callback(osp_factory, companies, tmp_path):
    """SAP DIV wallet that the test itself calls back (so the values are known): stand-in silent (NO_CALLBACK),
    DID document of the callback served by `TEST_DID_DOCUMENTS_DIR` (README 11.4, file name = host)."""
    bpn, did = COMPANIES["div"]["bpn"], "did:web:div.example.org:did:BPNL0000000DIV01"
    body = _div_callback_body(did, bpn)
    (tmp_path / "dids").mkdir()
    (tmp_path / "dids" / "div.example.org.json").write_text(json.dumps(body["didDocument"]))
    osp = osp_factory(env={**ENV, "STUB_FAILURES": f"{bpn}:NO_CALLBACK", "TEST_DID_DOCUMENTS_DIR": str(tmp_path / "dids")})
    create(osp, "div", "SAP_DIV")
    r = osp.post(f"/api/c4-m2/callbacks/sap-div/wallets/{bpn}", osp.service("sa-div-callback", ["submit_wallet_callback"]), json=body)
    assert r.status_code == 204, r.text
    seam("modules.c4_m2.service").run_timer_once()
    assert seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES["div"]["id"])["status"] == "ACTIVE"
    return osp


def test_case_23_holder_access_sap_div_issuer_writes_from_the_wallet_callback(div_with_callback):
    # README 13 case 23; 9.3 table ISSUER_WRITES: holder (= DID document location), walletUrl, clientId, clientSecret
    c = COMPANIES["div"]
    access = seam("modules.c4_m2.interface").get_holder_access(companyId=c["id"])
    assert access == {"issuanceMode": "ISSUER_WRITES", "companyId": c["id"], "bpn": c["bpn"],
                      "did": "did:web:div.example.org:did:BPNL0000000DIV01", "provider": "SAP_DIV",
                      "holder": "https://div.example.org/did/BPNL0000000DIV01/did.json",
                      "walletUrl": "https://auth.div.example.org/oauth", "clientId": "div-client-42",
                      "clientSecret": "div-SECRET-9f8e7d6c5b"}
    assert schema_errors("c4-m2", "HolderAccess", access) == []


def test_case_23_holder_access_over_http_with_and_without_the_permission(div_with_callback):
    # README 13 case 23 "Over HTTP without read_wallet_holder_access: 403"; 6.8
    osp = div_with_callback
    ok = holder_http(osp, "div")
    assert ok.status_code == 200 and ok.headers["Cache-Control"] == "no-store"
    assert ok.json()["clientSecret"] == "div-SECRET-9f8e7d6c5b" and schema_errors("c4-m2", "HolderAccess", ok.json()) == []
    for token in (osp.service("sa-query-only", ["query_c4_m2"]), osp.service("svc-c4-m2"),
                  osp.person("p-it", ["IT Admin"], company_id=COMPANIES["div"]["id"])):
        denied = holder_http(osp, "div", token)
        assert denied.status_code == 403, denied.text
        assert denied.json()["type"] == "urn:c4-m2:problem:forbidden"
        assert "div-SECRET-9f8e7d6c5b" not in denied.text
    unauth = osp.get(f"/api/c4-m2/internal/wallets/{COMPANIES['div']['id']}/holder-access")
    assert unauth.status_code == 401


@pytest.mark.parametrize("key,provider,mode,did", CASES, ids=IDS)
def test_holder_access_base_fields_on_every_variant_and_schema(osp_factory, companies, key, provider, mode, did):
    # openapi HolderAccessBase (required: issuanceMode, companyId, bpn, did, provider) + variant fields (README 9.3)
    osp = osp_factory(env=ENV)
    info = activate(osp, key, provider)
    r = holder_http(osp, key)
    assert r.status_code == 200, r.text
    access = r.json()
    assert schema_errors("c4-m2", "HolderAccess", access) == []
    assert (access["issuanceMode"], access["companyId"], access["bpn"], access["did"], access["provider"]) == \
           (mode, COMPANIES[key]["id"], COMPANIES[key]["bpn"], did, provider)
    assert access == seam("modules.c4_m2.interface").get_holder_access(companyId=COMPANIES[key]["id"])
    if mode == "ISSUER_WRITES":
        assert {"holder", "walletUrl", "clientId", "clientSecret"} <= set(access)
        assert access["holder"] == info["didDocumentLocation"]
        assert all(access[k] for k in ("walletUrl", "clientId", "clientSecret"))
        assert not {"identityApiUrl", "participantContextId", "apiKey"} & set(access)
    else:
        assert {"identityApiUrl", "participantContextId", "apiKey", "credentialServiceUrl"} <= set(access)
        assert access["identityApiUrl"].startswith("http") and access["apiKey"]
        assert access["credentialServiceUrl"] == info["credentialServiceUrl"]
        assert not {"holder", "walletUrl", "clientId", "clientSecret"} & set(access)
        assert access["participantContextId"] == (info["bpn"] if provider == "IDENTITY_HUB" else info["providerRef"])


def test_holder_access_wallet_not_active_is_409_for_requested_and_validating(osp_factory, companies, monkeypatch):
    # README 9.3 "Wallet not ACTIVE: 409 wallet-not-active"
    bpn_ih = COMPANIES["ih"]["bpn"]
    osp = osp_factory(env={**ENV, "STUB_FAILURES": f"{bpn_ih}:DID_NOT_RESOLVABLE"})
    interface = seam("modules.c4_m2.interface")
    create(osp, "div", "SAP_DIV")                          # REQUESTED: callback pending
    create(osp, "ih", "IDENTITY_HUB")                      # VALIDATING: DID document not resolvable yet
    assert interface.get_wallet_info(companyId=COMPANIES["div"]["id"])["status"] == "REQUESTED"
    assert interface.get_wallet_info(companyId=COMPANIES["ih"]["id"])["status"] == "VALIDATING"
    for key in ("div", "ih"):
        with pytest.raises(Problem) as err:
            interface.get_holder_access(companyId=COMPANIES[key]["id"])
        assert (err.value.status, err.value.name) == (409, "wallet-not-active")
        r = holder_http(osp, key)
        assert r.status_code == 409 and r.json()["type"] == "urn:c4-m2:problem:wallet-not-active"


def test_holder_access_wallet_not_active_after_failure(osp_factory, companies, monkeypatch):
    # README 9.3: also FAILED is "not ACTIVE"
    from test_c4_m2_common import Clock
    bpn = COMPANIES["ih"]["bpn"]
    osp = osp_factory(env={**ENV, "STUB_FAILURES": f"{bpn}:DID_NOT_RESOLVABLE", "DID_VALIDATION_MAX_HOURS": "1"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    create(osp, "ih", "IDENTITY_HUB")
    clock.advance(hours=2)
    seam("modules.c4_m2.service").run_timer_once()
    assert seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES["ih"]["id"])["status"] == "FAILED"
    r = holder_http(osp, "ih")
    assert r.status_code == 409 and r.json()["type"] == "urn:c4-m2:problem:wallet-not-active"


def test_holder_access_without_wallet_is_404(osp_factory, companies):
    # openapi: 404 on the holder-access path
    osp = osp_factory(env=ENV)
    r = holder_http(osp, "csp")
    assert r.status_code == 404 and r.json()["type"] == "urn:c4-m2:problem:not-found"
    with pytest.raises(Problem) as err:
        seam("modules.c4_m2.interface").get_holder_access(companyId=COMPANIES["csp"]["id"])
    assert err.value.status == 404


def test_holder_access_response_has_no_store_header_and_is_not_logged(osp_factory, companies, caplog):
    # README 9.3 "Header Cache-Control: no-store ... The response is not logged."
    osp = osp_factory(env=ENV)
    activate(osp, "csp", "CSP")
    caplog.set_level(logging.DEBUG)
    r = holder_http(osp, "csp")
    assert r.headers["Cache-Control"] == "no-store"
    assert_no_secret(r.json()["apiKey"], caplog.text)


# ----------------------------------------------------------------------------------------- audit log
def test_every_holder_access_retrieval_over_http_writes_an_audit_entry_without_secret(osp_factory, companies):
    # README 9.3 "Every call writes an audit log entry (without a secret)"; README 5 audit_log keys
    osp = osp_factory(env=ENV)
    for key, provider, *_ in CASES[:2]:
        activate(osp, key, provider)
    store = seam("modules.c4_m2.interface").store()
    before = len(store.list_audit())
    secrets = []
    for key in ("div", "ih"):
        wid = seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES[key]["id"])["walletId"]
        r = holder_http(osp, key)
        assert r.status_code == 200
        secrets.append(r.json().get("apiKey") or r.json()["clientSecret"])
        entry = store.list_audit()[-1]
        assert set(entry) >= {"occurred_at", "sub", "azp", "company_id", "operation", "object_id"}
        assert entry["azp"] == "svc-c4-m1" and entry["sub"] and entry["operation"]
        assert entry["company_id"] == COMPANIES[key]["id"]
        # OPEN-QUESTION: README 5 says "object ID"; the wallet id and the company id both identify the object
        assert entry["object_id"] in (wid, COMPANIES[key]["id"])
    holder_http(osp, "ih")                                      # a repeated retrieval writes another entry
    assert len(store.list_audit()) == before + 3
    for s in secrets:
        assert_no_secret(s, store.list_audit())


def test_in_process_holder_access_writes_an_audit_entry_too(osp_factory, companies):
    # README 5 audit_log: "In the same process without a token, the entry holds the name of the calling module"
    # OPEN-QUESTION: the field that carries the module name (sub or azp) and its spelling are not fixed; the
    # entry must contain the calling module's name, C4-M1 (README 9.3: only C4-M1 asks), in some field.
    osp = osp_factory(env=ENV)
    activate(osp, "csp", "CSP")
    interface = seam("modules.c4_m2.interface")
    store = interface.store()
    before = len(store.list_audit())
    access = interface.get_holder_access(companyId=COMPANIES["csp"]["id"])
    entries = store.list_audit()[before:]
    assert len(entries) == 1 and entries[0]["company_id"] == COMPANIES["csp"]["id"]
    values = " ".join(str(v).lower() for v in entries[0].values())
    assert "c4-m1" in values or "c4_m1" in values, entries[0]           # README 5: the calling module's name
    assert_no_secret(access["apiKey"], entries)


def test_failed_holder_access_retrieval_does_not_leak_into_the_audit_secret_scan(osp_factory, companies):
    # a 409 retrieval returns no secret, and no audit entry carries one
    osp = osp_factory(env=ENV)
    create(osp, "div", "SAP_DIV")
    assert holder_http(osp, "div").status_code == 409
    assert_no_secret("clientSecret", seam("modules.c4_m2.interface").store().list_audit())


# ================================================================= README 7.1: view of REQUESTED and FAILED
def test_wallet_view_of_a_requested_wallet(osp_factory, companies):
    # README 7.1 step 3 / openapi `Wallet`: no DID yet; did and didDocumentLocation are null, createdAt is set
    osp = osp_factory(env=ENV)
    create(osp, "div", "SAP_DIV")
    cid = COMPANIES["div"]["id"]
    view = seam("modules.c4_m2.interface").wallet_view(companyId=cid)
    assert schema_errors("c4-m2", "Wallet", view) == []
    assert view["status"] == "REQUESTED" and view["provider"] == "SAP_DIV" and view["companyId"] == cid
    assert view.get("did") is None and view.get("didDocumentLocation") is None
    assert view["createdAt"] and re.match(r"^\d{4}-\d{2}-\d{2}T", view["createdAt"])
    assert view.get("failureReason") is None and view.get("activatedAt") is None
    r = osp.get(f"/api/c4-m2/companies/{cid}/wallet", osp.person("p-req", ["IT Admin"], company_id=cid))
    assert r.status_code == 200 and r.json() == view


def test_wallet_view_of_a_failed_wallet(osp_factory, companies):
    # README 7.1 step 3: `failureReason` (one of README 10 reasons); 14.3 DID_MISMATCH
    bpn = COMPANIES["fail_did"]["bpn"]
    osp = osp_factory(env={**ENV, "STUB_FAILURES": f"{bpn}:DID_MISMATCH"})
    create(osp, "fail_did", "SAP_DIV")
    seam("modules.c4_m2.providers").flush_stand_in()
    seam("modules.c4_m2.service").run_timer_once()
    cid = COMPANIES["fail_did"]["id"]
    view = seam("modules.c4_m2.interface").wallet_view(companyId=cid)
    assert schema_errors("c4-m2", "Wallet", view) == []
    assert view["status"] == "FAILED"
    assert view["failureReason"] in ("PROVIDER_TIMEOUT", "DID_MISMATCH", "INVALID_DID_DOCUMENT", "DID_NOT_RESOLVABLE")
    assert view["failureReason"] == "DID_MISMATCH" and view["createdAt"]
    assert view.get("activatedAt") is None
    r = osp.get(f"/api/c4-m2/companies/{cid}/wallet", osp.person("p-fail", ["IT Admin"], company_id=cid))
    assert r.status_code == 200 and r.json() == view
