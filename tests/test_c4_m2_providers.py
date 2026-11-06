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
"""C4-M2 providers: built-in stand-ins first (cases 8, 9), the same case 8 against the shared CSP stand-in,
provider errors (case 24), secrets (case 25) and the DID rules (README 6.4, 11.4).

Seams (TEAM3-PLAN 12.2): `interface`, `service.run_timer_once`, `service.now`, `providers.orders()`,
`providers.flush_stand_in()`, `did.check_form`, `did.check_document`. Every import is lazy.
"""
from __future__ import annotations

import json
import logging
from urllib.parse import unquote

import httpx
import jwt
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from portal_common import http as phttp
from test_c4_m2_common import (COMPANIES, CSP_URL, OSP_A_ID, OSP_B_ID, SECRETS_KEY_HEX, Clock, assert_no_secret, companies,
                               event_errors, osp_factory, schema_errors, seam, step_input)
from tools.keys import ec_jwk

CSP_BPN = "BPNLIUK2REMLK3F4"
IH_BPN = "BPNL00000000IH01"
IH_DID = "did:web:ih.example.org:BPNL00000000IH01"
CSP_DID = "did:web:csp-wallet.example.org:BPNLIUK2REMLK3F4"
SHARED_CSP_ENV = {"CSP_WALLET_URL": CSP_URL + "/wallet/v1", "DID_RESOLVER_URL": CSP_URL}


# ------------------------------------------------------------------------------------------ helpers
def create(osp, key, provider=None, n=1):
    """HTTP step `create-wallet` with the service account of the process orchestration."""
    cid = COMPANIES[key]["id"]
    body = step_input(cid, n, companyId=cid)
    if provider:
        body["provider"] = provider
    return osp.post("/api/c4-m2/steps/create-wallet", osp.service("svc-c4-m2"), json=body)


def info(key):
    return seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES[key]["id"])


def row(key):
    return seam("modules.c4_m2.interface").store().get_wallet(COMPANIES[key]["id"])


def wallet_events(osp):
    return [e for e in osp.events(source="urn:c4-m2") if e["type"].startswith("DataspaceWallet")]


def wallet_orders():
    # OPEN-QUESTION: the shape of providers.orders() (`provider`, `bpn`, `kind`) is the TEAM3-PLAN 12.2 convention,
    # not README text; the README only says "no second order to the stand-in".
    return [(o["provider"], o["bpn"], o["kind"]) for o in seam("modules.c4_m2.providers").orders()]


class Spy:
    """Records every `portal_common.http.request` and may answer a call itself (a response) or raise."""

    def __init__(self, monkeypatch, handler=None):
        self.calls: list[tuple[str, str, dict]] = []
        real = phttp.request

        def request(method, url, timeout=phttp.DEFAULT_TIMEOUT, **kw):
            self.calls.append((method.upper(), url, kw))
            if handler:
                answer = handler(method.upper(), url, kw)
                if isinstance(answer, Exception):
                    raise answer
                if answer is not None:
                    return answer
            return real(method, url, timeout=timeout, **kw)

        monkeypatch.setattr(phttp, "request", request)

    def to(self, fragment: str, method: str | None = None) -> list[tuple[str, str]]:
        return [(m, u) for m, u, _ in self.calls if fragment in u and (method is None or m == method)]


def doc(did, service="https://doc.example.org/credentials", key="ec", service_type="CredentialService"):
    pub = {k: v for k, v in ec_jwk(f"{did}#key-1")[1].items() if k in ("kty", "crv", "x", "y")}
    d = {"@context": ["https://www.w3.org/ns/did/v1"], "id": did,
         "verificationMethod": [{"id": f"{did}#key-1", "type": "JsonWebKey2020", "controller": did, "publicKeyJwk": pub}]}
    if key == "okp":
        d["verificationMethod"][0]["publicKeyJwk"] = {"kty": "OKP", "crv": "Ed25519", "x": pub["x"]}
    if service:
        d["service"] = [{"id": f"{did}#credential-service", "type": service_type, "serviceEndpoint": service}]
    return d


def resolver(state: dict) -> FastAPI:
    """A Universal Resolver at `http://resolver.test` (README 11.4); `state` = {status, body, requests}."""
    app = FastAPI()

    @app.get("/1.0/identifiers/{did:path}")
    def resolve(did: str):
        state["requests"].append(unquote(did))
        body = state["body"]() if callable(state["body"]) else state["body"]
        return JSONResponse(body, status_code=state["status"])

    phttp.register_local("http://resolver.test", app)
    return app


NOT_FOUND = {"didDocument": None, "didResolutionMetadata": {"error": "notFound"}, "didDocumentMetadata": {}}


def found(document):
    return {"didDocument": document, "didResolutionMetadata": {}, "didDocumentMetadata": {}}


# ================================================================================= case 8, built-in CSP
def test_case_08_builtin_csp_standin_wallet_active_within_the_call(osp_factory, companies):
    # README 13 case 8 / 11.3 built-in stand-in (CSP_WALLET_URL empty); 8.1 step 4 CSP, step 5, step 6
    osp = osp_factory()
    r = create(osp, "csp", "CSP")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "RUNNING"                                           # README 6.9: complete in the call, still RUNNING
    assert schema_errors("c4-m2", "StepResultWallet", body) == []
    res = body["result"]
    assert (res["companyId"], res["provider"]) == (COMPANIES["csp"]["id"], "CSP")
    assert res["status"] == "ACTIVE"                                            # README 8.1 step 5: ACTIVE within this call
    w = info("csp")
    assert (w["status"], w["did"], w["provider"], w["issuanceMode"]) == ("ACTIVE", CSP_DID, "CSP", "HOLDER_REQUESTS")
    assert w["didDocumentLocation"] == "https://csp-wallet.example.org/BPNLIUK2REMLK3F4/did.json"
    # README 11.3: the stand-in DID document has the service CredentialService with this endpoint
    assert w["credentialServiceUrl"] == "https://csp-wallet.example.org/api/credentials/v1/participants/BPNLIUK2REMLK3F4"
    assert w["providerRef"] and w["supportsWalletAccounts"] is True
    assert wallet_orders() == [("CSP", CSP_BPN, "wallet")]


def test_case_08_builtin_csp_event_in_the_relay(osp_factory, companies):
    osp = osp_factory()
    create(osp, "csp", "CSP")
    events = wallet_events(osp)
    assert [e["type"] for e in events] == ["DataspaceWalletCreated"]            # README 13 case 8: in the outbox
    assert event_errors("c4-m2", events[0]) == []
    w = info("csp")
    assert events[0]["data"] == {"companyId": COMPANIES["csp"]["id"], "did": CSP_DID, "walletId": w["walletId"],
                                 "provider": "CSP", "didDocumentLocation": w["didDocumentLocation"], "bpn": CSP_BPN}


def test_case_08_builtin_csp_holder_access_holder_requests(osp_factory, companies):
    # README 13 case 8 "holder-access returns HOLDER_REQUESTS with identityApiUrl, participantContextId and apiKey"
    osp = osp_factory()
    create(osp, "csp", "CSP")
    access = seam("modules.c4_m2.interface").get_holder_access(companyId=COMPANIES["csp"]["id"])
    assert schema_errors("c4-m2", "HolderAccess", access) == []
    assert access["issuanceMode"] == "HOLDER_REQUESTS"
    assert (access["companyId"], access["bpn"], access["did"], access["provider"]) == \
           (COMPANIES["csp"]["id"], CSP_BPN, CSP_DID, "CSP")
    assert access["identityApiUrl"].startswith("http") and access["apiKey"]
    assert access["participantContextId"] == info("csp")["providerRef"]
    store = seam("modules.c4_m2.interface").store()
    secret = store.get_secret(info("csp")["walletId"], "HOLDER_ACCESS")             # README 8.1: stored as HOLDER_ACCESS
    assert secret and secret["client_id"] == access["participantContextId"]
    assert seam("modules.c4_m2.crypto").decrypt(secret["secret_encrypted"], secret["nonce"], secret["key_version"]) == access["apiKey"]


def test_case_08_builtin_csp_without_provider_uses_the_default_provider_csp(osp_factory, companies):
    # README 4 `DEFAULT_PROVIDER`: empty = CSP; 6.1 step 4
    osp = osp_factory(env={"DEFAULT_PROVIDER": ""})
    assert create(osp, "csp").status_code == 200
    assert info("csp")["provider"] == "CSP"


# ==================================================================================== case 9 IdentityHub
def test_case_09_builtin_identity_hub_participant_context_is_the_bpn(osp_factory, companies):
    # README 13 case 9, 11.2 built-in stand-in, 8.1 step 4 IdentityHub
    osp = osp_factory()
    r = create(osp, "ih", "IDENTITY_HUB")
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "RUNNING" and schema_errors("c4-m2", "StepResultWallet", r.json()) == []
    w = info("ih")
    assert (w["status"], w["did"], w["provider"], w["issuanceMode"]) == ("ACTIVE", IH_DID, "IDENTITY_HUB", "HOLDER_REQUESTS")
    assert w["providerRef"] == IH_BPN                                            # participantContextId = BPN
    assert w["didDocumentLocation"] == "https://ih.example.org/BPNL00000000IH01/did.json"
    assert w["credentialServiceUrl"]                                              # service CredentialService in the DID document
    assert wallet_orders() == [("IDENTITY_HUB", IH_BPN, "wallet")]
    events = wallet_events(osp)
    assert [e["type"] for e in events] == ["DataspaceWalletCreated"]
    assert event_errors("c4-m2", events[0]) == []
    assert (events[0]["data"]["did"], events[0]["data"]["provider"], events[0]["data"]["bpn"]) == (IH_DID, "IDENTITY_HUB", IH_BPN)


def test_case_09_identity_hub_holder_access_and_sts_access_are_stored(osp_factory, companies):
    # README 8.1: "store them encrypted as HOLDER_ACCESS and STS_ACCESS"; 9.3 HOLDER_REQUESTS with apiKey
    osp = osp_factory()
    create(osp, "ih", "IDENTITY_HUB")
    interface, crypto = seam("modules.c4_m2.interface"), seam("modules.c4_m2.crypto")
    access = interface.get_holder_access(companyId=COMPANIES["ih"]["id"])
    assert schema_errors("c4-m2", "HolderAccess", access) == []
    assert access["issuanceMode"] == "HOLDER_REQUESTS" and access["participantContextId"] == IH_BPN
    assert access["did"] == IH_DID and access["apiKey"] and access["identityApiUrl"].startswith("http")
    wid, store = info("ih")["walletId"], interface.store()
    holder, sts = store.get_secret(wid, "HOLDER_ACCESS"), store.get_secret(wid, "STS_ACCESS")
    assert holder["client_id"] == IH_BPN                                          # README 5: participant context
    assert crypto.decrypt(holder["secret_encrypted"], holder["nonce"], holder["key_version"]) == access["apiKey"]
    assert sts["client_id"] and sts["client_id"] != IH_BPN
    sts_secret = crypto.decrypt(sts["secret_encrypted"], sts["nonce"], sts["key_version"])
    assert sts_secret and sts_secret != access["apiKey"]
    assert_no_secret(sts_secret, json.dumps(store.dump()))                        # STS_ACCESS stored as ciphertext only


# ============================================================================ case 8 against the shared CSP
def test_case_08_shared_csp_standin_token_wallet_did_resolution(osp_factory, companies, monkeypatch):
    # README 13 case 8: token from the CSP, client assertion iss = sub = ospId, wallet ACTIVE within the call
    spy = Spy(monkeypatch)
    osp = osp_factory(env=SHARED_CSP_ENV, csp=True)
    osp.csp_register(CSP_BPN)                                                    # OSP A is the home OSP (home_check)
    r = create(osp, "csp", "CSP")
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "RUNNING" and schema_errors("c4-m2", "StepResultWallet", r.json()) == []
    # token with private_key_jwt: assertion iss = sub = ospId from SETTINGS_FILE (README 4, 13 case 8)
    tokens = [kw for m, u, kw in spy.calls if m == "POST" and u == CSP_URL + "/oauth/token"]
    assert tokens, "the module fetched no token at the CSP"
    # OPEN-QUESTION: `kw["data"]`, `kw["json"]` and `kw["headers"]` of portal_common.http.request are how this
    # test reads the form, body and Authorization header; the README does not fix how the adapter calls the client.
    form = tokens[0]["data"]
    assert form["grant_type"] == "client_credentials"
    assert form["client_assertion_type"] == "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
    claims = jwt.decode(form["client_assertion"], options={"verify_signature": False})
    assert claims["iss"] == claims["sub"] == OSP_A_ID
    assert claims["aud"] == CSP_URL + "/oauth/token"            # RFC 7523: the audience is the token endpoint
    assert claims.get("exp") and claims.get("jti")              # OPEN-QUESTION: exp/jti are RFC 7523 practice, not README text
    # signed with the key of the OSP (the stand-in verifies it against the trust list; checked here too)
    pub = json.loads(osp.tmp_path.joinpath("trust.json").read_text())[OSP_A_ID]["jwk"]
    jwt.decode(form["client_assertion"], jwt.PyJWK(pub).key, algorithms=["ES256"], options={"verify_aud": False})
    # README 11.3: POST /wallets with the BPN, with the access token of the CSP
    posts = [kw for m, u, kw in spy.calls if m == "POST" and u == CSP_URL + "/wallet/v1/wallets"]
    assert len(posts) == 1 and posts[0]["json"] == {"bpn": CSP_BPN}
    assert posts[0]["headers"]["Authorization"].startswith("Bearer ")
    # the stand-in accepted the order only because the token was valid: its wallet exists
    stand_in = osp.csp.wallets[CSP_BPN]
    w = info("csp")
    assert (w["status"], w["did"], w["provider"]) == ("ACTIVE", CSP_DID, "CSP")
    assert w["providerRef"] == stand_in["participantContextId"]
    assert w["credentialServiceUrl"] == stand_in["credentialServiceUrl"]
    # README 11.4: DID_RESOLVER_URL set -> GET {url}/1.0/identifiers/{did}
    assert [unquote(u) for _, u in spy.to("/1.0/identifiers/", "GET")] == [f"{CSP_URL}/1.0/identifiers/{CSP_DID}"]
    assert wallet_orders() == []                                                  # no built-in stand-in involved
    events = wallet_events(osp)
    assert [e["type"] for e in events] == ["DataspaceWalletCreated"] and event_errors("c4-m2", events[0]) == []
    assert events[0]["data"]["did"] == CSP_DID


def test_case_08_shared_csp_standin_holder_access(osp_factory, companies):
    osp = osp_factory(env=SHARED_CSP_ENV, csp=True)
    osp.csp_register(CSP_BPN)
    create(osp, "csp", "CSP")
    access = seam("modules.c4_m2.interface").get_holder_access(companyId=COMPANIES["csp"]["id"])
    stand_in = osp.csp.wallets[CSP_BPN]
    assert schema_errors("c4-m2", "HolderAccess", access) == []
    assert access["issuanceMode"] == "HOLDER_REQUESTS"
    assert access["identityApiUrl"] == stand_in["identityApiUrl"] == CSP_URL + "/identity/v1"
    assert access["participantContextId"] == stand_in["participantContextId"]
    assert access["apiKey"] == stand_in["apiKey"]
    assert access["credentialServiceUrl"] == stand_in["credentialServiceUrl"]


def test_case_08_shared_csp_standin_unregistered_company_is_provider_rejected(osp_factory, companies):
    # README 11.3: 403 "other home OSP or BPN unknown at the CSP" -> 409 provider-rejected
    osp = osp_factory(env=SHARED_CSP_ENV, csp=True)                              # BPNLIUK2REMLK3F4 unknown at the CSP
    r = create(osp, "csp", "CSP")
    assert r.status_code == 409 and r.json()["type"] == "urn:c4-m2:problem:provider-rejected"
    assert r.json()["retryable"] is False


# ================================================================================================ case 24
def _assert_untouched_order_state(osp, key, attempt=1):
    w = row(key)
    assert w is not None and w["status"] == "REQUESTED" and w["attempt"] == attempt     # README 8.1 step 4
    assert w.get("provider_ordered_at") is None
    assert wallet_events(osp) == []                                                   # no event at all


def test_case_24_csp_rejected_is_409_provider_rejected_not_retryable(osp_factory, companies, monkeypatch):
    # README 13 case 24; 8.1 step 4 CSP; 12 `provider-rejected`
    bpn = COMPANIES["csp_rejected"]["bpn"]
    osp = osp_factory(env={"STUB_FAILURES": f"{bpn}:CSP_REJECTED"})
    r = create(osp, "csp_rejected", "CSP")
    assert r.status_code == 409, r.text
    assert r.json()["type"] == "urn:c4-m2:problem:provider-rejected" and r.json()["retryable"] is False
    _assert_untouched_order_state(osp, "csp_rejected")
    # a repetition continues (README 8.1 step 2: REQUESTED without provider_ordered_at re-orders)
    monkeypatch.setenv("STUB_FAILURES", "")
    again = create(osp, "csp_rejected", "CSP", n=2)
    assert again.status_code == 200 and again.json()["state"] == "RUNNING"
    w = row("csp_rejected")
    assert w["status"] == "ACTIVE" and w["provider_ordered_at"] and w["attempt"] == 1
    assert [e["type"] for e in wallet_events(osp)] == ["DataspaceWalletCreated"]


PROVIDERS = [("div", "SAP_DIV"), ("ih", "IDENTITY_HUB"), ("csp", "CSP")]


@pytest.mark.parametrize("key,provider", PROVIDERS, ids=[p[1] for p in PROVIDERS])
def test_case_24_order_error_is_502_upstream_error_retryable(osp_factory, companies, monkeypatch, key, provider):
    # README 13 case 24; 14.3 ORDER_ERROR: "an order to the stand-in (SAP DIV, IdentityHub or CSP) ends with 503"
    bpn = COMPANIES[key]["bpn"]
    osp = osp_factory(env={"STUB_FAILURES": f"{bpn}:ORDER_ERROR"})
    r = create(osp, key, provider)
    assert r.status_code == 502, r.text
    assert r.json()["type"] == "urn:c4-m2:problem:upstream-error" and r.json()["retryable"] is True
    _assert_untouched_order_state(osp, key)
    monkeypatch.setenv("STUB_FAILURES", "")                                        # README 6.9: a repetition sends it again
    assert create(osp, key, provider, n=2).status_code == 200
    assert row(key)["provider_ordered_at"] is not None


def test_case_24_csp_409_wallet_exists_deletes_and_creates_again(osp_factory, companies, monkeypatch):
    # README 11.3: "If POST /wallets responds with 409 ... the adapter deletes the wallet at the CSP and creates it again"
    spy = Spy(monkeypatch)
    osp = osp_factory(env=SHARED_CSP_ENV, csp=True)
    osp.csp_register(CSP_BPN)
    status, old = osp.csp.create_wallet(OSP_A_ID, {"bpn": CSP_BPN})              # a wallet from an aborted attempt
    assert status == 201
    r = create(osp, "csp", "CSP")
    assert r.status_code == 200, r.text
    wallets_url = CSP_URL + "/wallet/v1/wallets"
    assert spy.to("/wallet/v1/wallets") == [("POST", wallets_url), ("DELETE", f"{wallets_url}/{CSP_BPN}"),
                                            ("POST", wallets_url)]
    fresh = osp.csp.wallets[CSP_BPN]
    assert fresh["apiKey"] != old["apiKey"] and fresh["participantContextId"] != old["participantContextId"]
    access = seam("modules.c4_m2.interface").get_holder_access(companyId=COMPANIES["csp"]["id"])
    assert access["apiKey"] == fresh["apiKey"] and access["participantContextId"] == fresh["participantContextId"]
    assert info("csp")["status"] == "ACTIVE"


CSP_ERRORS = [("api-401", "POST", "/wallet/v1/wallets", 401), ("api-500", "POST", "/wallet/v1/wallets", 500),
              ("api-503", "POST", "/wallet/v1/wallets", 503), ("timeout", "POST", "/wallet/v1/wallets", "timeout"),
              ("token-401", "POST", "/oauth/token", 401), ("token-500", "POST", "/oauth/token", 500)]


@pytest.mark.parametrize("name,method,path,what", CSP_ERRORS, ids=[c[0] for c in CSP_ERRORS])
def test_case_24_csp_401_5xx_timeout_are_502_upstream_error(osp_factory, companies, monkeypatch, name, method, path, what):
    # README 11.3: "Response 401 at the token endpoint or at the API, responses 5xx and timeout: 502 upstream-error (retryable: true)"
    def handler(m, url, kw):
        if m == method and url == CSP_URL + path:
            return httpx.ReadTimeout("timed out") if what == "timeout" else httpx.Response(what, json={"error": "x"})
        return None

    Spy(monkeypatch, handler)
    osp = osp_factory(env=SHARED_CSP_ENV, csp=True)
    osp.csp_register(CSP_BPN)
    r = create(osp, "csp", "CSP")
    assert r.status_code == 502, r.text
    assert r.json()["type"] == "urn:c4-m2:problem:upstream-error" and r.json()["retryable"] is True
    _assert_untouched_order_state(osp, "csp")


def test_case_24_csp_403_from_the_wallet_api_is_provider_rejected(osp_factory, companies):
    # README 11.3: 403 other home OSP -> 409 provider-rejected (retryable false), row stays REQUESTED
    osp = osp_factory(env=SHARED_CSP_ENV, csp=True)
    osp.csp_register(CSP_BPN, osp_id=OSP_B_ID)                                    # home OSP is OSP B
    r = create(osp, "csp", "CSP")
    assert r.status_code == 409 and r.json()["type"] == "urn:c4-m2:problem:provider-rejected"
    assert r.json()["retryable"] is False
    _assert_untouched_order_state(osp, "csp")


# ================================================================================================ case 25
def _all_haystacks(osp, caplog, keys):
    interface = seam("modules.c4_m2.interface")
    store = interface.store()
    http_texts = []
    for key in keys:
        cid = COMPANIES[key]["id"]
        http_texts.append(osp.get(f"/api/c4-m2/internal/wallets/{cid}", osp.service("svc-c4-m2")).text)
        http_texts.append(osp.get(f"/api/c4-m2/companies/{cid}/wallet", osp.person(f"p-{key}", ["IT Admin"], company_id=cid)).text)
    return [caplog.text, osp.events(), store.list_audit(), store.list_step_log(), json.dumps(store.dump(), sort_keys=True),
            http_texts]


def _collect_secrets(osp, keys):
    interface, crypto = seam("modules.c4_m2.interface"), seam("modules.c4_m2.crypto")
    store, secrets = interface.store(), []
    for key in keys:
        r = osp.get(f"/api/c4-m2/internal/wallets/{COMPANIES[key]['id']}/holder-access", osp.service("svc-c4-m1"))
        assert r.status_code == 200, r.text
        access = r.json()
        secrets += [access[k] for k in ("apiKey", "clientSecret") if k in access]
        sts = store.get_secret(info(key)["walletId"], "STS_ACCESS")
        if sts:
            secrets.append(crypto.decrypt(sts["secret_encrypted"], sts["nonce"], sts["key_version"]))
    return secrets


def test_case_25_builtin_standins_secrets_appear_nowhere(osp_factory, companies, caplog):
    # README 13 case 25, 4, 6.7: not in log, outbox (relay), step_log, audit_log, step results, and not in plain text in any table
    caplog.set_level(logging.DEBUG)
    osp = osp_factory(env={"STUB_CALLBACK_DELAY_SECONDS": "3600"})
    results = []
    for n, (key, provider) in enumerate(PROVIDERS, 1):
        results.append(create(osp, key, provider, n=n).text)
    seam("modules.c4_m2.providers").flush_stand_in()
    seam("modules.c4_m2.service").run_timer_once()
    keys = [k for k, _ in PROVIDERS]
    assert all(info(k)["status"] == "ACTIVE" for k in keys)
    secrets = _collect_secrets(osp, keys)
    assert len(secrets) == 4 and all(len(s) >= 8 for s in secrets) and len(set(secrets)) == 4   # DIV, IH api+sts, CSP
    hay = _all_haystacks(osp, caplog, keys) + [results]
    for secret in secrets + [SECRETS_KEY_HEX]:
        assert_no_secret(secret, *hay)
    # the step log really exists, so the scan above is not vacuous
    assert len(seam("modules.c4_m2.interface").store().list_step_log()) >= 3
    assert len(seam("modules.c4_m2.interface").store().list_audit()) >= 3                   # holder-access retrievals


def test_case_25_shared_csp_standin_api_key_appears_nowhere(osp_factory, companies, caplog):
    # the API key of the shared CSP stand-in wallet (README 13 case 25 "including API keys ... of the dataspace wallet of the CSP")
    caplog.set_level(logging.DEBUG)
    osp = osp_factory(env=SHARED_CSP_ENV, csp=True)
    osp.csp_register(CSP_BPN)
    result = create(osp, "csp", "CSP").text
    secrets = _collect_secrets(osp, ["csp"])
    assert secrets == [osp.csp.wallets[CSP_BPN]["apiKey"]]
    for secret in secrets:
        assert_no_secret(secret, *_all_haystacks(osp, caplog, ["csp"]), result)


def test_case_25_failed_orders_do_not_log_secrets_either(osp_factory, companies, caplog, monkeypatch):
    # README 13 case 25, 4, 6.7: a SAP DIV callback that carries a secret but fails (invalid document), then a
    # re-order that fails technically (503 -> 502): the secret of the callback and the key are in no log, event,
    # audit entry, step_log, table dump or response.
    caplog.set_level(logging.DEBUG)
    secret = "callback-secret-9f8e7d6c5b4a-do-not-leak"
    bpn = COMPANIES["div"]["bpn"]
    osp = osp_factory(env={"STUB_CALLBACK_DELAY_SECONDS": "3600"})
    first = create(osp, "div", "SAP_DIV")
    assert first.status_code == 200, first.text
    did = "did:web:div.example.org:did:" + bpn
    bad_document = {"@context": ["https://www.w3.org/ns/did/v1"], "id": did,
                    "service": [{"id": did + "#cs", "type": "CredentialService", "serviceEndpoint": "https://x.example/cs"}]}
    callback = osp.post(f"/api/c4-m2/callbacks/sap-div/wallets/{bpn}",
                        osp.service("sa-div-callback", ["submit_wallet_callback"]),
                        json={"did": did, "didDocument": bad_document,
                              "authenticationDetails": {"authenticationServiceUrl": "https://auth.div.example.org/oauth",
                                                        "clientID": "div-client-7", "clientSecret": secret}})
    assert callback.status_code == 204, callback.text
    assert info("div")["status"] == "FAILED"                                      # no verificationMethod (README 7.6 step 4)
    monkeypatch.setenv("STUB_FAILURES", f"{bpn}:ORDER_ERROR")
    again = create(osp, "div", "SAP_DIV", n=2)
    assert again.status_code == 502, again.text
    assert row("div")["attempt"] == 2 and row("div").get("provider_ordered_at") is None
    store = seam("modules.c4_m2.interface").store()
    assert store.list_audit() and store.list_step_log()                           # the scan is not vacuous
    hay = [caplog.text, osp.events(), store.list_audit(), store.list_step_log(), json.dumps(store.dump(), sort_keys=True),
           first.text, callback.text, again.text]
    assert_no_secret(secret, *hay)
    assert_no_secret(SECRETS_KEY_HEX, *hay)


def test_case_25_failed_ih_order_does_not_log_the_key(osp_factory, companies, caplog):
    caplog.set_level(logging.DEBUG)
    osp = osp_factory(env={"STUB_FAILURES": f"{IH_BPN}:ORDER_ERROR"})
    r = create(osp, "ih", "IDENTITY_HUB")
    assert r.status_code == 502
    assert_no_secret(SECRETS_KEY_HEX, caplog.text, r.text, osp.events())


# ============================================================================================= DID: form
@pytest.fixture
def did(monkeypatch):
    monkeypatch.setenv("SAP_DIV_DID_DOCUMENT_BASE_URL", "https://div.example.org/did")
    monkeypatch.setenv("IDENTITYHUB_DID_BASE", "ih.example.org")
    return seam("modules.c4_m2.did")


DIV_BPN = "BPNL0000000DIV01"


@pytest.mark.parametrize("candidate,bpn,expected", [
    ("did:web:div.example.org:did:BPNL0000000DIV01", DIV_BPN, True),
    ("did:web:div.example.org:did:bpnl0000000div01", DIV_BPN, True),            # README 6.4: case does not matter
    ("DID:WEB:DIV.EXAMPLE.ORG:DID:BPNL0000000DIV01", DIV_BPN, True),
    ("did:web:div.example.org:did:BPNL0000000DIV01", "bpnl0000000div01", True),
    ("did:web:other.example:BPNL0000000DIV01", DIV_BPN, False),                 # DID_MISMATCH of case 4 (14.3)
    ("did:web:other.example:BPNL000000FAIL01", "BPNL000000FAIL01", False),
    ("did:web:div.example.org:BPNL0000000DIV01", DIV_BPN, False),               # path `did` missing
    ("did:web:div.example.org:did:BPNL0000000DIV02", DIV_BPN, False),           # another BPN
    ("did:web:div.example.org:did:BPNL0000000DIV01:extra", DIV_BPN, False),
    ("did:web:div.example.org:did", DIV_BPN, False),
    ("did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK", DIV_BPN, False),
    ("", DIV_BPN, False),
])
def test_did_form_sap_div(did, candidate, bpn, expected):
    # README 6.4 step 1: exactly did:web: + host and path of SAP_DIV_DID_DOCUMENT_BASE_URL ("/" -> ":") + ":" + BPN
    assert did.check_form("SAP_DIV", candidate, bpn) is expected


def test_did_form_sap_div_base_with_a_path_replaces_slashes_by_colons(did, monkeypatch):
    monkeypatch.setenv("SAP_DIV_DID_DOCUMENT_BASE_URL", "https://sap.example.org/a/b")
    assert did.check_form("SAP_DIV", "did:web:sap.example.org:a:b:BPNL0000000DIV01", DIV_BPN) is True
    assert did.check_form("SAP_DIV", "did:web:sap.example.org:a:BPNL0000000DIV01", DIV_BPN) is False
    assert did.check_form("SAP_DIV", "did:web:div.example.org:did:BPNL0000000DIV01", DIV_BPN) is False   # base is read at call time


@pytest.mark.parametrize("candidate,expected", [
    (IH_DID, True),
    ("did:web:ih.example.org:BPNL00000000IH02", False),
    ("did:web:other.example.org:BPNL00000000IH01", False),
    ("did:web:ih.example.org", False),
    ("did:web:ih.example.org:BPNL00000000IH01:more", False),
    ("did:key:z6Mk", False),
])
def test_did_form_identity_hub(did, candidate, expected):
    # README 6.4 step 1: exactly did:web:{IDENTITYHUB_DID_BASE}:{BPN}
    assert did.check_form("IDENTITY_HUB", candidate, IH_BPN) is expected


def test_did_form_identity_hub_base_is_read_from_the_configuration(did, monkeypatch):
    monkeypatch.setenv("IDENTITYHUB_DID_BASE", "hub.example.net")
    assert did.check_form("IDENTITY_HUB", "did:web:hub.example.net:BPNL00000000IH01", IH_BPN) is True
    assert did.check_form("IDENTITY_HUB", IH_DID, IH_BPN) is False


@pytest.mark.parametrize("candidate,expected", [
    (CSP_DID, True),
    ("did:web:wallet.csp.example.org:any:path:BPNLIUK2REMLK3F4", True),         # "the CSP decides host and path"
    ("did:web:csp-wallet.example.org:SOMETHINGELSE", True),
    ("did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK", False),
    ("did:ion:EiClkZMDxPKqC9c", False),
    ("web:csp-wallet.example.org", False),
    ("https://csp-wallet.example.org/did.json", False),
    ("", False),
])
def test_did_form_csp_only_checks_the_did_web_form(did, candidate, expected):
    # README 6.4 step 1: "only the form did:web: is checked, the CSP decides host and path"
    assert did.check_form("CSP", candidate, CSP_BPN) is expected


# ======================================================================================= DID: document
def test_did_document_valid_ec_key_and_credential_service_pass_for_every_provider(did):
    for provider, d in (("SAP_DIV", "did:web:div.example.org:did:BPNL0000000DIV01"), ("IDENTITY_HUB", IH_DID), ("CSP", CSP_DID)):
        assert did.check_document(provider, d, doc(d)) is None


def test_did_document_okp_key_passes(did):
    # README 6.4 step 3: kty OKP with crv, x
    assert did.check_document("CSP", CSP_DID, doc(CSP_DID, key="okp")) is None


def test_did_document_sap_div_needs_no_credential_service(did):
    # README 6.4 step 3: CredentialService "IdentityHub, CSP and own wallet" - not SAP DIV
    d = "did:web:div.example.org:did:BPNL0000000DIV01"
    assert did.check_document("SAP_DIV", d, doc(d, service=None)) is None
    assert did.check_document("SAP_DIV", d, doc(d, service_type="SomethingElse")) is None


@pytest.mark.parametrize("provider,d", [("IDENTITY_HUB", IH_DID), ("CSP", CSP_DID)])
def test_did_document_identity_hub_and_csp_need_a_credential_service(did, provider, d):
    assert did.check_document(provider, d, doc(d, service=None)) == "INVALID_DID_DOCUMENT"
    assert did.check_document(provider, d, doc(d, service_type="LinkedDomains")) == "INVALID_DID_DOCUMENT"
    broken = doc(d)
    broken["service"] = []
    assert did.check_document(provider, d, broken) == "INVALID_DID_DOCUMENT"


@pytest.mark.parametrize("provider,d", [("SAP_DIV", "did:web:div.example.org:did:BPNL0000000DIV01"),
                                        ("IDENTITY_HUB", IH_DID), ("CSP", CSP_DID)])
def test_did_document_id_must_equal_the_did(did, provider, d):
    wrong = {**doc(d), "id": "did:web:other.example:BPNL0000000DIV01"}
    assert did.check_document(provider, d, wrong) == "INVALID_DID_DOCUMENT"
    missing = doc(d)
    del missing["id"]
    assert did.check_document(provider, d, missing) == "INVALID_DID_DOCUMENT"


def _with_jwk(d, jwk):
    out = doc(d)
    out["verificationMethod"][0]["publicKeyJwk"] = jwk
    return out


EC = {"kty": "EC", "crv": "P-256", "x": "zGFDpzmtLVxoJo5wJNLhZTpHq0GphHMxsBATEe-XLD8",
      "y": "WYc-FOevkwEhIjj8RmQ7CBgnwS4TpOhEi0RKu5-mXUg"}


@pytest.mark.parametrize("name,jwk", [
    ("ec-without-y", {k: v for k, v in EC.items() if k != "y"}),
    ("ec-without-x", {k: v for k, v in EC.items() if k != "x"}),
    ("ec-without-crv", {k: v for k, v in EC.items() if k != "crv"}),
    ("okp-without-x", {"kty": "OKP", "crv": "Ed25519"}),
    ("okp-without-crv", {"kty": "OKP", "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"}),
    ("rsa", {"kty": "RSA", "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx", "e": "AQAB"}),
    ("no-kty", {"crv": "P-256", "x": EC["x"], "y": EC["y"]}),
    ("empty", {}),
])
def test_did_document_key_shape_is_checked(did, name, jwk):
    # README 6.4 step 3: publicKeyJwk with kty EC (crv, x, y) or kty OKP (crv, x)
    assert did.check_document("IDENTITY_HUB", IH_DID, _with_jwk(IH_DID, jwk)) == "INVALID_DID_DOCUMENT"


def test_did_document_without_verification_method_or_without_public_key_jwk_is_invalid(did):
    # 14.3 INVALID_DID_DOCUMENT: "DID document without verificationMethod"
    no_vm = doc(IH_DID)
    del no_vm["verificationMethod"]
    assert did.check_document("IDENTITY_HUB", IH_DID, no_vm) == "INVALID_DID_DOCUMENT"
    empty = {**doc(IH_DID), "verificationMethod": []}
    assert did.check_document("IDENTITY_HUB", IH_DID, empty) == "INVALID_DID_DOCUMENT"
    multibase = doc(IH_DID)
    multibase["verificationMethod"][0] = {"id": f"{IH_DID}#key-1", "type": "Multikey", "controller": IH_DID,
                                         "publicKeyMultibase": "z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"}
    assert did.check_document("IDENTITY_HUB", IH_DID, multibase) == "INVALID_DID_DOCUMENT"


def test_did_document_one_valid_key_among_invalid_ones_is_enough(did):
    # README 6.4 step 3: "at least one entry in verificationMethod with publicKeyJwk"
    d = doc(IH_DID)
    d["verificationMethod"].insert(0, {"id": f"{IH_DID}#bad", "type": "Multikey", "controller": IH_DID,
                                       "publicKeyMultibase": "z6Mk"})
    assert did.check_document("IDENTITY_HUB", IH_DID, d) is None


# ====================================================================== DID: resolution and the timer
def _ih_env(extra=None):
    return {"DID_RESOLVER_URL": "http://resolver.test", "DID_VALIDATION_INTERVAL_MINUTES": "10",
            "DID_VALIDATION_MAX_HOURS": "1", **(extra or {})}


def test_resolution_files_of_test_did_documents_dir_come_first(osp_factory, companies, tmp_path):
    # README 11.4 / 4: TEST_DID_DOCUMENTS_DIR "used before any resolution"; file name = host
    state = {"status": 500, "body": {}, "requests": []}
    resolver(state)
    endpoint = "https://dir.example.org/credentials/v1/participants/BPNL00000000IH01"
    (tmp_path / "dids").mkdir()
    (tmp_path / "dids" / "ih.example.org.json").write_text(json.dumps(doc(IH_DID, service=endpoint)))
    osp = osp_factory(env=_ih_env({"TEST_DID_DOCUMENTS_DIR": str(tmp_path / "dids")}))
    assert create(osp, "ih", "IDENTITY_HUB").status_code == 200
    w = info("ih")
    assert w["status"] == "ACTIVE" and w["credentialServiceUrl"] == endpoint      # the file, not the stand-in document
    assert state["requests"] == []                                                # the resolver was never asked


def test_resolution_file_with_an_invalid_document_fails_at_once(osp_factory, companies, tmp_path):
    # README 6.4 step 3: invalid content -> FAILED INVALID_DID_DOCUMENT, event DataspaceWalletFailed
    (tmp_path / "dids").mkdir()
    (tmp_path / "dids" / "ih.example.org.json").write_text(json.dumps(doc(IH_DID, service=None)))   # no CredentialService
    osp = osp_factory(env={"TEST_DID_DOCUMENTS_DIR": str(tmp_path / "dids")})
    r = create(osp, "ih", "IDENTITY_HUB")
    assert r.status_code == 200 and r.json()["state"] == "RUNNING"
    w = info("ih")
    assert (w["status"], w["failureReason"]) == ("FAILED", "INVALID_DID_DOCUMENT")
    events = wallet_events(osp)
    assert [e["type"] for e in events] == ["DataspaceWalletFailed"] and event_errors("c4-m2", events[0]) == []
    assert events[0]["data"] == {"companyId": COMPANIES["ih"]["id"], "walletId": w["walletId"], "provider": "IDENTITY_HUB",
                                 "reason": "INVALID_DID_DOCUMENT"}


def test_resolution_through_did_resolver_url(osp_factory, companies):
    # README 11.4: GET {DID_RESOLVER_URL}/1.0/identifiers/{did}; success on 2xx with empty didResolutionMetadata.error
    state = {"status": 200, "body": found(doc(IH_DID, service="https://resolver.example.org/cs")), "requests": []}
    resolver(state)
    osp = osp_factory(env=_ih_env())
    assert create(osp, "ih", "IDENTITY_HUB").status_code == 200
    w = info("ih")
    assert w["status"] == "ACTIVE" and w["credentialServiceUrl"] == "https://resolver.example.org/cs"   # from `didDocument`
    assert state["requests"] == [IH_DID]
    assert [e["type"] for e in wallet_events(osp)] == ["DataspaceWalletCreated"]


@pytest.mark.parametrize("name,status,body", [("200-with-error", 200, NOT_FOUND), ("404", 404, NOT_FOUND),
                                              ("500", 500, {"error": "boom"})])
def test_resolution_failure_keeps_the_wallet_validating(osp_factory, companies, name, status, body):
    # README 6.4 step 2: "No result: next attempt at the next interval" (not FAILED)
    state = {"status": status, "body": body, "requests": []}
    resolver(state)
    osp = osp_factory(env=_ih_env())
    r = create(osp, "ih", "IDENTITY_HUB")
    assert r.status_code == 200 and r.json()["state"] == "RUNNING"
    assert info("ih")["status"] == "VALIDATING" and info("ih")["failureReason"] is None
    assert wallet_events(osp) == []
    assert row("ih")["provider_ordered_at"]


def test_not_resolvable_is_retried_at_the_interval_until_it_resolves(osp_factory, companies, monkeypatch):
    # README 6.4: "repeats every DID_VALIDATION_INTERVAL_MINUTES"; 6.10 DID check; step 4 on success
    state = {"status": 404, "body": NOT_FOUND, "requests": []}
    resolver(state)
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    osp = osp_factory(env=_ih_env())
    service = seam("modules.c4_m2.service")
    create(osp, "ih", "IDENTITY_HUB")
    assert len(state["requests"]) == 1                                            # "starts immediately on entering VALIDATING"
    service.run_timer_once()
    assert len(state["requests"]) == 1                                            # next_check_at not reached
    for expected in (2, 3):
        clock.advance(minutes=10, seconds=1)
        service.run_timer_once()
        assert len(state["requests"]) == expected and info("ih")["status"] == "VALIDATING"
    state.update(status=200, body=found(doc(IH_DID)))
    clock.advance(minutes=10, seconds=1)
    service.run_timer_once()
    w = info("ih")
    assert w["status"] == "ACTIVE" and w["activatedAt"] and row("ih")["did_validated_at"]
    assert [e["type"] for e in wallet_events(osp)] == ["DataspaceWalletCreated"]
    clock.advance(minutes=30)
    service.run_timer_once()
    assert len(state["requests"]) == 4 and len(wallet_events(osp)) == 1           # ACTIVE is final; no more checks


def test_not_resolvable_after_the_deadline_fails_with_did_not_resolvable(osp_factory, companies, monkeypatch):
    # README 6.4 step 2 "after the deadline FAILED, DID_NOT_RESOLVABLE"; deadline DID_VALIDATION_MAX_HOURS from validating_since
    # OPEN-QUESTION: DID_VALIDATION_MAX_HOURS is whole hours (1) here; README 13 case 7 says "2 minutes" (tests patch the clock)
    state = {"status": 404, "body": NOT_FOUND, "requests": []}
    resolver(state)
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    osp = osp_factory(env=_ih_env())
    service = seam("modules.c4_m2.service")
    create(osp, "ih", "IDENTITY_HUB")
    for _ in range(5):                                                            # 50 minutes: still before the deadline
        clock.advance(minutes=10, seconds=1)
        service.run_timer_once()
        assert info("ih")["status"] == "VALIDATING"
    assert wallet_events(osp) == []
    clock.advance(minutes=11)
    service.run_timer_once()
    w = info("ih")
    assert (w["status"], w["failureReason"]) == ("FAILED", "DID_NOT_RESOLVABLE")
    events = wallet_events(osp)
    assert [e["type"] for e in events] == ["DataspaceWalletFailed"] and event_errors("c4-m2", events[0]) == []
    assert events[0]["data"]["reason"] == "DID_NOT_RESOLVABLE"
    seen = len(state["requests"])
    clock.advance(hours=3)
    service.run_timer_once()
    assert len(state["requests"]) == seen and len(wallet_events(osp)) == 1       # FAILED is not retried by the timer


def test_invalid_content_fails_at_once_without_further_attempts(osp_factory, companies, monkeypatch):
    # README 6.4 step 3: "otherwise FAILED, INVALID_DID_DOCUMENT, without further attempts"
    no_key = doc(IH_DID)
    del no_key["verificationMethod"]
    state = {"status": 200, "body": found(no_key), "requests": []}
    resolver(state)
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    osp = osp_factory(env=_ih_env())
    create(osp, "ih", "IDENTITY_HUB")
    w = info("ih")
    assert (w["status"], w["failureReason"]) == ("FAILED", "INVALID_DID_DOCUMENT")
    assert len(state["requests"]) == 1
    clock.advance(minutes=10, seconds=1)
    seam("modules.c4_m2.service").run_timer_once()
    assert len(state["requests"]) == 1 and len(wallet_events(osp)) == 1
    assert wallet_events(osp)[0]["data"]["reason"] == "INVALID_DID_DOCUMENT"


def test_builtin_https_resolution_fetches_did_json_by_the_did_web_rules(osp_factory, companies):
    # README 11.4 (DID_RESOLVER_URL empty): after files and stand-in documents, GET https://<host>/<path>/did.json
    requests = []
    app = FastAPI()

    @app.get("/{bpn}/did.json")
    def did_json(bpn: str):
        requests.append(bpn)
        return doc(CSP_DID, service="https://csp-wallet.example.org/api/own-doc")

    phttp.register_local("https://csp-wallet.example.org", app)
    osp = osp_factory(env={"CSP_WALLET_URL": CSP_URL + "/wallet/v1"}, csp=True)   # DID_RESOLVER_URL empty
    osp.csp_register(CSP_BPN)
    assert create(osp, "csp", "CSP").status_code == 200
    assert requests == [CSP_BPN]
    w = info("csp")
    assert w["status"] == "ACTIVE" and w["credentialServiceUrl"] == "https://csp-wallet.example.org/api/own-doc"


def test_builtin_resolution_uses_https_only(osp_factory, companies, monkeypatch):
    # README 11.4: "HTTPS only", timeout 10 seconds
    spy = Spy(monkeypatch, lambda m, u, kw: httpx.Response(404) if "csp-wallet.example.org/" in u and "/did.json" in u else None)
    osp = osp_factory(env={"CSP_WALLET_URL": CSP_URL + "/wallet/v1"}, csp=True)
    osp.csp_register(CSP_BPN)
    create(osp, "csp", "CSP")
    fetched = [u for m, u in spy.to("did.json", "GET")]
    assert fetched and all(u.startswith("https://") for u in fetched)
    assert info("csp")["status"] == "VALIDATING"


def test_wallet_orders_do_not_include_account_orders(osp_factory, companies):
    # providers.orders() kinds are wallet, account, account-deletion (TEAM3-PLAN 12.2); create-wallet only orders wallets
    osp = osp_factory()
    create(osp, "ih", "IDENTITY_HUB")
    create(osp, "csp", "CSP", n=2)
    assert {o["kind"] for o in seam("modules.c4_m2.providers").orders()} == {"wallet"}


# ============================================================== README 6.4 step 1 end to end: CSP DID form
def _csp_wallet_answer(did, calls=None):
    """A recording fake of the wallet API of the CSP: `POST /wallets` answers 201 with `did`; the token goes through."""
    def handler(method, url, kw):
        if method == "POST" and url == CSP_URL + "/wallet/v1/wallets":
            return httpx.Response(201, json={"participantContextId": "pc-fake", "did": did,
                                             "credentialServiceUrl": "https://fake.example.org/cs",
                                             "identityApiUrl": CSP_URL + "/identity/v1", "apiKey": "fake-api-key-0123456789"})
        return None
    return handler


@pytest.mark.parametrize("did", ["did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK", "did:ion:EiClkZMDxPKqC9c",
                                 "https://csp-wallet.example.org/did.json"])
def test_csp_did_that_is_not_did_web_ends_failed_did_mismatch(osp_factory, companies, monkeypatch, did):
    # README 6.4 step 1: "Dataspace wallet of the CSP: only the form did:web: is checked" -> FAILED, DID_MISMATCH,
    # event DataspaceWalletFailed (6.2), before any resolution
    spy = Spy(monkeypatch, _csp_wallet_answer(did))
    osp = osp_factory(env=SHARED_CSP_ENV, csp=True)
    osp.csp_register(CSP_BPN)
    r = create(osp, "csp", "CSP")
    assert r.status_code == 200 and r.json()["state"] == "RUNNING", r.text
    seam("modules.c4_m2.service").run_timer_once()
    w = info("csp")
    assert (w["status"], w["failureReason"]) == ("FAILED", "DID_MISMATCH")
    events = wallet_events(osp)
    assert [e["type"] for e in events] == ["DataspaceWalletFailed"] and event_errors("c4-m2", events[0]) == []
    assert events[0]["data"] == {"companyId": COMPANIES["csp"]["id"], "walletId": w["walletId"], "provider": "CSP",
                                 "reason": "DID_MISMATCH"}
    assert spy.to("/1.0/identifiers/") == [] and spy.to("did.json") == []        # form is checked before resolution


# ===================================================================== README 11.4: did:web URL rules, HTTPS
def test_builtin_resolution_of_a_host_only_did_uses_well_known_did_json(osp_factory, companies, monkeypatch):
    # README 11.4: "https://<host>/.well-known/did.json per the did:web method" for a DID without path
    did = "did:web:host-only.example.org"
    requests = []
    app = FastAPI()

    @app.get("/.well-known/did.json")
    def well_known():
        requests.append("well-known")
        return doc(did, service="https://host-only.example.org/cs")

    phttp.register_local("https://host-only.example.org", app)
    spy = Spy(monkeypatch, _csp_wallet_answer(did))
    osp = osp_factory(env={"CSP_WALLET_URL": CSP_URL + "/wallet/v1"}, csp=True)      # DID_RESOLVER_URL empty
    osp.csp_register(CSP_BPN)
    assert create(osp, "csp", "CSP").status_code == 200
    assert spy.to("did.json", "GET") == [("GET", "https://host-only.example.org/.well-known/did.json")]
    assert requests == ["well-known"]
    w = info("csp")
    assert w["status"] == "ACTIVE" and w["did"] == did and w["credentialServiceUrl"] == "https://host-only.example.org/cs"


def test_builtin_resolution_fetches_only_https_urls(osp_factory, companies, monkeypatch):
    # README 11.4: "HTTPS only": whatever the DID is, no http:// URL is requested for the document
    spy = Spy(monkeypatch, _csp_wallet_answer("did:web:host-only.example.org"))
    osp = osp_factory(env={"CSP_WALLET_URL": CSP_URL + "/wallet/v1"}, csp=True)
    osp.csp_register(CSP_BPN)
    create(osp, "csp", "CSP")
    fetched = [u for m, u in spy.to("did.json", "GET")]
    assert fetched and all(u.startswith("https://") for u in fetched)
    assert not [u for _, u, _ in spy.calls if u.startswith("http://") and "did.json" in u]
