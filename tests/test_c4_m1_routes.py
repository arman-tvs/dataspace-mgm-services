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
"""C4-M1 routes: README 6.3 (choice of the route), 11.5 (route CSP_ISSUER), 11.6 (route STUB), 8.2 (revocation
through the route); acceptance cases 14, 15, 16 and 19 (README 13).

The CSP is the shared CSP stand-in (`osp_factory(csp=True)`); everything the module sends to it is recorded
by wrapping `portal_common.http.request` (which also lets a test make the CSP answer 503, 401 or time out).
The stand-in calls back through its own `later` thread; the tests wait for the callbacks deterministically by
wrapping `Csp.callback` (an event per finished callback), without sleeping.

OPEN-QUESTION: C4-M1 README 13 case 14 uses OSP B (`99a5685c-...`) as `ospId`; the kit's trust file and
`config/osp-a/installation.json` carry OSP A (`22222222-...`). The tests assert `iss == sub ==
settings.get("ospId")` (= OSP A here), which is the property the spec states.
OPEN-QUESTION: the body of the credential request at the wallet identity API is provisional (the spec names
`issuer`, `holderPid`, credential definition and format, not the JSON keys). The tests assert only what the
CSP stand-in needs: issuer DID, `holderPid`, `x-api-key`, and the kind (`bpn` / `membership`) in `type` or `id`.
OPEN-QUESTION: README 4 gives `BPN:bpn-credential,MEMBERSHIP:membership-credential` as the example of
`CSP_ISSUER_CREDENTIAL_DEFINITIONS`, but the shared CSP stand-in derives the credential kind from `type` or `id` of
the requested credential and only knows `bpn` / `membership`. The end-to-end tests therefore use
`BPN:bpn,MEMBERSHIP:membership`; a separate unit test with a recording fake (`test_case_14_unit_...`) uses the
spec example and asserts that the definition identifier, `CREDENTIAL_FORMAT` and a timeout <= 10 s are sent.
OPEN-QUESTION: `CALLBACK_BASE_URL` and `CSP_ISSUER_CREDENTIAL_DEFINITIONS` are not set in the shipped config;
the tests always set them (plan 11 C4-M1 #6: fall back to `settings.base_url()` and `BPN:bpn,MEMBERSHIP:membership`).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import threading
import uuid

import httpx
import jwt
import pytest

from portal_common import csp as csp_client
from portal_common import tokens
from portal_common import events
from portal_common import http as phttp
from portal_common import settings
from test_c4_m2_common import (
    BASE,
    COMPANIES,
    CSP_URL,
    OSP_A_ID,
    OSP_B_ID,
    assert_no_secret,
    companies,  # noqa: F401  (fixture)
    event_errors,
    osp_factory,  # noqa: F401  (fixture)
    response_errors,
    seam,
    step_input,
    wallet_fake,  # noqa: F401  (fixture)
)

U1, U4, U6 = COMPANIES["u1"], COMPANIES["u4"], COMPANIES["u6"]
ISSUER_URL = CSP_URL + "/issuer/v1"
ISSUER_DID = "did:web:issuer.csp.example.org"
P = "/api/c4-m1"
PROBLEM = "urn:c4-m1:problem:"
CSP_ENV = {"ISSUER_MODE": "CSP", "CSP_ISSUER_URL": ISSUER_URL, "CSP_ISSUER_DID": ISSUER_DID,
           "CALLBACK_BASE_URL": BASE, "CSP_ISSUER_CREDENTIAL_DEFINITIONS": "BPN:bpn,MEMBERSHIP:membership",   # see the OPEN-QUESTION above
           "CREDENTIAL_FORMAT": "VC1_0_JWT", "RESEND_AFTER_HOURS": "24"}


# ------------------------------------------------------------------------------------------ helpers
class Traffic:
    """Records every outgoing `portal_common.http.request`; `rules` make selected calls fail."""

    def __init__(self, monkeypatch) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.rules: list[tuple] = []
        real = phttp.request

        def request(method, url, timeout=phttp.DEFAULT_TIMEOUT, **kw):
            kw = {**kw, "timeout": timeout}                    # the effective per-call timeout is recorded too
            self.calls.append((method, url, kw))
            for match, action in list(self.rules):
                if match(method, url, kw):
                    if isinstance(action, Exception):
                        raise action
                    return httpx.Response(action, json={"type": "about:blank", "status": action},
                                          request=httpx.Request(method, url))
            return real(method, url, **kw)

        monkeypatch.setattr(phttp, "request", request)

    def fail(self, match, action) -> None:
        self.rules.append((match, action))

    def clear_rules(self) -> None:
        self.rules.clear()

    def to(self, prefix: str, method: str | None = None) -> list[tuple[str, str, dict]]:
        return [c for c in self.calls if c[1].startswith(prefix) and (method is None or c[0] == method)]

    def csp(self) -> list[tuple[str, str, dict]]:
        return self.to(CSP_URL)


def put_holder_rule(m, u, kw) -> bool:
    return m == "PUT" and "/issuer/v1/holders/" in u and "/grants/" not in u


def grant_rule(m, u, kw) -> bool:
    return m == "PUT" and "/grants/" in u


def token_rule(m, u, kw) -> bool:
    return u.endswith("/oauth/token")


def csp_rule(m, u, kw) -> bool:
    return u.startswith(CSP_URL)


def request_rule(kind: str | None = None):
    def rule(m, u, kw) -> bool:
        return m == "POST" and u.endswith("/credentials/request") and (
            kind is None or kind in json.dumps(kw.get("json")).lower())
    return rule


def delete_grant_rule(m, u, kw) -> bool:
    return m == "DELETE" and "/grants/" in u


class Callbacks:
    """Waits for the callbacks of the CSP stand-in (its `later` thread) without sleeping."""

    def __init__(self, csp, monkeypatch) -> None:
        self.sem = threading.Semaphore(0)
        orig = csp.callback

        def wrapped(*a, **k):
            try:
                orig(*a, **k)
            finally:
                self.sem.release()

        monkeypatch.setattr(csp, "callback", wrapped)

    def wait(self, n: int) -> None:
        for i in range(n):
            assert self.sem.acquire(timeout=15), f"callback {i + 1} of {n} did not arrive"


class World:
    pass


def store():
    return seam("modules.c4_m1.interface").store()


def start_csp(osp_factory, wallet_fake, monkeypatch, env: dict | None = None, home_osp: str = OSP_A_ID,
              directory_did: str | None = None) -> World:
    """OSP A with the CSP stand-in and the route CSP_ISSUER; U6 has a CSP wallet (HOLDER_REQUESTS)."""
    w = World()
    w.osp = osp_factory({**CSP_ENV, **(env or {})}, csp=True)
    bpn = U6["bpn"]
    w.osp.csp_register(bpn, osp_id=OSP_A_ID)                       # the wallet is created by OSP A
    status, wallet = csp_client.request(CSP_URL + "/wallet/v1", "POST", "/wallets", {"bpn": bpn})
    assert status == 201, wallet
    w.did, w.api_key, w.pcid = wallet["did"], wallet["apiKey"], wallet["participantContextId"]
    w.osp.csp_register(bpn, directory_did or w.did, osp_id=home_osp)   # C3-M2 register-did, home OSP
    wallet_fake.set("u6", provider="CSP", issuanceMode="HOLDER_REQUESTS", providerRef=w.pcid, did=w.did)
    wallet_fake.access[U6["id"]] = {
        "issuanceMode": "HOLDER_REQUESTS", "companyId": U6["id"], "bpn": bpn, "did": w.did, "provider": "CSP",
        "identityApiUrl": wallet["identityApiUrl"], "participantContextId": w.pcid, "apiKey": w.api_key}
    w.fake, w.bpn = wallet_fake, bpn
    w.callbacks = Callbacks(w.osp.csp, monkeypatch)
    csp_client.reset()                                              # the module must fetch its own token
    w.traffic = Traffic(monkeypatch)
    w.svc = w.osp.service("svc-c4-m1")
    return w


def issue(w: World, company: dict = U6, n: int = 1, **extra):
    return w.osp.post(f"{P}/steps/issue-credentials", w.svc, json=step_input(company["id"], n, **extra))


def revoke(w: World, company: dict = U6, n: int = 9, **extra):
    return w.osp.post(f"{P}/steps/revoke-credentials", w.svc,
                      json=step_input(company["id"], n, reason="COMPANY_DEACTIVATED", **extra))


def assert_problem(r, status: int, name: str, retryable: bool) -> None:
    assert r.status_code == status, r.text
    body = r.json()
    assert body["type"] == PROBLEM + name and body["retryable"] is retryable


def not_requested(cid: str, *types: str) -> None:
    for ty in types or ("BPN", "MEMBERSHIP"):
        r = store().get_credential(cid, ty)
        assert r is None or r["status"] != "REQUESTED", f"{ty} must not be REQUESTED: {r}"


def seed_csp_row(w: World, ctype: str, status: str, **kw) -> dict:
    now = dt.datetime(2026, 11, 6, 8, 0, tzinfo=dt.UTC)
    r = {"id": str(uuid.uuid4()), "company_id": U6["id"], "credential_type": ctype, "status": status,
         "route": "CSP_ISSUER", "issuer_did": ISSUER_DID, "wallet_provider": "CSP", "bpn": w.bpn, "holder_did": w.did,
         "request_ref": f"{U6['id']}:{ctype}:1", "attempt": 1, "requested_at": now,
         "issued_at": now if status in ("ISSUED", "REVOKED") else None, "failed_at": None, "revoked_at": None,
         "failure_reason": None, "revocation_reason": None, "created_at": now, "changed_at": now}
    r.update(kw)
    store().put_credential(r)
    return r


def csp_has_grant(w: World, kind: str) -> None:
    w.osp.csp.holders[w.bpn] = w.did
    w.osp.csp.grants[(w.bpn, kind)] = {"callbackUrl": f"{BASE}/api/c4-m1/issuer-callbacks/{kind}", "ospId": OSP_A_ID}


# ------------------------------------------------------------------------- case 14: route CSP_ISSUER
def test_case_14_csp_issuer_registers_holder_sets_grants_and_requests_in_the_wallet(
        osp_factory, companies, wallet_fake, monkeypatch, caplog):
    # README 13 case 14, 11.5 procedure, 11.4 request, 4 (sign-in)
    caplog.set_level(logging.DEBUG)
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    r = issue(w)
    assert r.status_code == 200
    assert r.json()["state"] == "RUNNING"
    assert response_errors("c4-m1", "POST", "/steps/issue-credentials", 200, r.json()) == []
    w.callbacks.wait(2)
    t = w.traffic
    # --- sign-in: private_key_jwt, iss = sub = ospId from SETTINGS_FILE; token reused
    tokens = t.to(CSP_URL + "/oauth/token", "POST")
    assert len(tokens) == 1, "one token fetch for the whole run (README 4: token is reused)"
    form = tokens[0][2]["data"]
    assert form["grant_type"] == "client_credentials" and form["client_assertion_type"] == csp_client.ASSERTION_TYPE
    claims = jwt.decode(form["client_assertion"], options={"verify_signature": False})
    assert claims["iss"] == claims["sub"] == OSP_A_ID
    # --- README 4: time limit per call to the CSP is 10 seconds
    assert t.csp() and all(c[2]["timeout"] <= 10 for c in t.csp()), [c[2]["timeout"] for c in t.csp()]
    # --- holder: PUT /holders/{bpn} with the DID, once per run
    holders = t.to(f"{ISSUER_URL}/holders/{w.bpn}", "PUT")
    holders = [c for c in holders if c[1] == f"{ISSUER_URL}/holders/{w.bpn}"]
    assert len(holders) == 1 and holders[0][2]["json"] == {"did": w.did}
    assert w.osp.csp.holders == {w.bpn: w.did}
    # --- grants: callbackUrl per kind, memberOf only on the membership grant
    grants = {u.rsplit("/", 1)[1]: kw["json"] for m, u, kw in t.to(f"{ISSUER_URL}/holders/{w.bpn}/grants/", "PUT")}
    assert set(grants) == {"bpn", "membership"}
    assert grants["bpn"] == {"callbackUrl": f"{BASE}/api/c4-m1/issuer-callbacks/bpn"}
    assert grants["membership"] == {"callbackUrl": f"{BASE}/api/c4-m1/issuer-callbacks/membership",
                                    "memberOf": settings.get("dataspace")["memberOf"]}   # README 11.5: from the settings
    assert set(w.osp.csp.grants) == {(w.bpn, "bpn"), (w.bpn, "membership")}
    # --- credential requests at the wallet identity API, header x-api-key, holderPid, issuer
    reqs = t.to(f"{CSP_URL}/identity/v1/participants/{w.pcid}/credentials/request", "POST")
    assert len(reqs) == 2
    pids = {}
    for _m, _u, kw in reqs:
        assert kw["headers"]["x-api-key"] == w.api_key
        body = kw["json"]
        assert ISSUER_DID in json.dumps(body)
        kinds = {str(c.get("type") or c.get("id")).lower() for c in body["credentials"]}
        assert len(kinds) == 1
        pids[kinds.pop()] = body["holderPid"]
    assert pids == {"bpn": f"{U6['id']}:BPN:1", "membership": f"{U6['id']}:MEMBERSHIP:1"}   # README 11.4
    assert sorted((c["type"], c["holderPid"]) for c in w.osp.csp.wallets[w.bpn]["credentials"]) == [
        ("bpn", pids["bpn"]), ("membership", pids["membership"])]
    # --- order of the calls: holder, then grant of a kind, then the request of that kind
    idx = {("holder",): [i for i, c in enumerate(t.calls) if c[1] == f"{ISSUER_URL}/holders/{w.bpn}"][0]}
    for kind in ("bpn", "membership"):
        g = next(i for i, c in enumerate(t.calls) if c[1].endswith(f"/grants/{kind}") and c[0] == "PUT")
        q = next(i for i, c in enumerate(t.calls) if c[1].endswith("/credentials/request")
                 and kind in json.dumps(c[2]["json"]).lower())
        assert idx[("holder",)] < g < q
    # --- the callbacks of the CSP stand-in (service account sa-csp-issuer) were accepted with 204
    cb = w.osp.csp.callbacks
    assert len(cb) == 2 and all(c["status"] == 204 for c in cb)
    assert {c["url"] for c in cb} == {f"{BASE}/api/c4-m1/issuer-callbacks/bpn",
                                      f"{BASE}/api/c4-m1/issuer-callbacks/membership"}
    # --- rows: both ISSUED, route and issuer data
    for ty in ("BPN", "MEMBERSHIP"):
        row = store().get_credential(U6["id"], ty)
        assert row["status"] == "ISSUED" and row["route"] == "CSP_ISSUER" and row["attempt"] == 1
        assert row["issuer_did"] == ISSUER_DID and row["request_ref"] == pids[ty.lower()]
        assert row["wallet_provider"] == "CSP" and row["holder_did"] == w.did and row["bpn"] == w.bpn
        assert row["issued_at"] is not None
    done = w.osp.events("CredentialsIssued")
    assert len(done) == 1 and done[0]["source"] == "urn:c4-m1"
    assert sorted(done[0]["data"]["credentialTypes"]) == ["BPN", "MEMBERSHIP"] and done[0]["data"]["companyId"] == U6["id"]
    assert event_errors("c4-m1", done[0]) == []
    assert w.osp.events("CredentialIssuanceFailed") == []
    assert store().get_run(U6["id"])["status"] == "DONE"
    ops = [(a["operation"], a["client_id"]) for a in store().list_audit()]
    assert ops == [("REPORT_CREDENTIAL_STATUS", "sa-csp-issuer")] * 2        # README 7.4 step 5
    # --- issuerDid and route are visible to OSP staff (README 7.2)
    items = w.osp.get(f"{P}/credentials", w.osp.person("p2-osp", ["OSP Admin"]),
                      params={"companyId": U6["id"]}).json()["items"]
    assert {(i["credentialType"], i["route"], i["issuerDid"]) for i in items} == {
        ("BPN", "CSP_ISSUER", ISSUER_DID), ("MEMBERSHIP", "CSP_ISSUER", ISSUER_DID)}


def test_case_14_unit_request_carries_definition_identifier_format_and_a_timeout_of_at_most_10_seconds(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 11.5 step 3 / 11.4: the credential request names `CSP_ISSUER_DID`, the identifier from
    # CSP_ISSUER_CREDENTIAL_DEFINITIONS (spec example) and `CREDENTIAL_FORMAT`; README 4: 10 s limit per call to the CSP.
    # A recording fake replaces `portal_common.http.request`, so the shared CSP stand-in does not have to know the ids.
    w = start_csp(osp_factory, wallet_fake, monkeypatch, env={
        "CSP_ISSUER_CREDENTIAL_DEFINITIONS": "BPN:bpn-credential,MEMBERSHIP:membership-credential",
        "CREDENTIAL_FORMAT": "VC1_0_JWT"})
    calls: list[tuple[str, str, dict]] = []

    def fake(method, url, timeout=phttp.DEFAULT_TIMEOUT, **kw):
        calls.append((method, url, {**kw, "timeout": timeout}))
        if url.endswith("/oauth/token"):
            body, status = {"access_token": "csp-token", "token_type": "Bearer", "expires_in": 300}, 200
        elif url.endswith("/credentials/request"):
            body, status = {"holderPid": (kw.get("json") or {}).get("holderPid"), "state": "REQUESTED"}, 202
        elif "/grants/" in url:
            body, status = None, 204
        else:
            body, status = {"bpn": w.bpn, "did": w.did}, 201
        return httpx.Response(status, json=body, request=httpx.Request(method, url)) if body is not None else \
            httpx.Response(status, request=httpx.Request(method, url))

    tokens._load_jwks()   # load the IAM signing keys before the fake replaces portal_common.http.request
    monkeypatch.setattr(phttp, "request", fake)
    r = issue(w)
    assert r.status_code == 200, r.text
    reqs = [c for c in calls if c[0] == "POST" and c[1].endswith("/credentials/request")]
    assert len(reqs) == 2
    blobs = {("bpn" if "bpn-credential" in json.dumps(kw["json"]) else "membership"): json.dumps(kw["json"])
             for _m, _u, kw in reqs}
    assert set(blobs) == {"bpn", "membership"}
    assert "membership-credential" in blobs["membership"] and "bpn-credential" not in blobs["membership"]
    for blob in blobs.values():
        assert ISSUER_DID in blob and "VC1_0_JWT" in blob                  # issuer and CREDENTIAL_FORMAT
    to_csp = [c for c in calls if c[1].startswith(CSP_URL)]
    assert to_csp and all(c[2]["timeout"] <= 10 for c in to_csp), [(c[1], c[2]["timeout"]) for c in to_csp]


def test_case_14_holder_access_is_fetched_once_and_never_sent_to_the_csp_issuer(
        osp_factory, companies, wallet_fake, monkeypatch, caplog):
    # README 4 "Secrets", 13 case 14: "No holder access goes to the CSP"; secret in no log, event, result, store
    caplog.set_level(logging.DEBUG)
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    r = issue(w)
    w.callbacks.wait(2)
    assert w.fake.holder_access_calls == [U6["id"]]        # once per run, just before the first order
    for _m, url, kw in w.traffic.to(ISSUER_URL) + w.traffic.to(CSP_URL + "/oauth/token"):
        blob = json.dumps(kw, default=str)
        assert w.api_key not in blob and w.pcid not in blob, f"holder access sent to the CSP: {url}"
    assert_no_secret(w.api_key, caplog.text, events.RELAY.log, r.text, store().dump(), store().list_audit(),
                     store().list_history(store().get_credential(U6["id"], "BPN")["id"]))


def test_case_14_second_run_after_issued_makes_no_csp_call(osp_factory, companies, wallet_fake, monkeypatch):
    # README 8.1 step 5 / case 2 on this route: all ISSUED -> DONE, no holder, no grant, no request, no event
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    issue(w)
    w.callbacks.wait(2)
    assert {store().get_credential(U6["id"], t)["status"] for t in ("BPN", "MEMBERSHIP")} == {"ISSUED"}
    n_calls, n_events = len(w.traffic.csp()), len(w.osp.events("CredentialsIssued"))
    r = issue(w, n=2)
    assert r.status_code == 200 and r.json()["state"] == "DONE"
    assert len(w.traffic.csp()) == n_calls and len(w.osp.events("CredentialsIssued")) == n_events
    assert w.fake.holder_access_calls == [U6["id"]]


def test_case_14_revoke_deletes_the_membership_grant_and_revokes(osp_factory, companies, wallet_fake, monkeypatch):
    # README 13 case 14 (end), 8.2: ISSUED, route can revoke -> REVOKED + CredentialRevoked; BPN stays
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    issue(w)
    w.callbacks.wait(2)
    r = revoke(w)
    assert r.status_code == 200 and r.json()["state"] == "DONE"
    assert response_errors("c4-m1", "POST", "/steps/revoke-credentials", 200, r.json()) == []
    assert r.json()["result"] == {"companyId": U6["id"], "revoked": ["MEMBERSHIP"], "cancelled": [], "manualRevocation": []}
    dels = w.traffic.to(ISSUER_URL, "DELETE")
    assert [u for _m, u, _kw in dels] == [f"{ISSUER_URL}/holders/{w.bpn}/grants/membership"]
    assert (w.bpn, "membership") not in w.osp.csp.grants and (w.bpn, "bpn") in w.osp.csp.grants
    ms = store().get_credential(U6["id"], "MEMBERSHIP")
    assert ms["status"] == "REVOKED" and ms["revoked_at"] is not None and ms["revocation_reason"] == "COMPANY_DEACTIVATED"
    assert store().get_credential(U6["id"], "BPN")["status"] == "ISSUED"
    ev = w.osp.events("CredentialRevoked")
    assert [e["data"] for e in ev] == [{"companyId": U6["id"], "credentialType": "MEMBERSHIP",
                                        "revocationReason": "COMPANY_DEACTIVATED"}]
    assert event_errors("c4-m1", ev[0]) == []


def test_revoke_uses_the_route_of_the_order_not_the_current_issuer_mode(osp_factory, companies, wallet_fake, monkeypatch):
    # README 6.3: "A revocation uses the route of the order, even if ISSUER_MODE has been set differently"
    w = start_csp(osp_factory, wallet_fake, monkeypatch, env={"ISSUER_MODE": "OWN", "ISSUER_ROUTES": ""})
    row = seed_csp_row(w, "MEMBERSHIP", "ISSUED")
    csp_has_grant(w, "membership")
    r = revoke(w)
    assert r.status_code == 200 and r.json()["result"]["revoked"] == ["MEMBERSHIP"]
    assert [u for _m, u, _kw in w.traffic.to(ISSUER_URL, "DELETE")] == [f"{ISSUER_URL}/holders/{w.bpn}/grants/membership"]
    assert store().get_credential_by_id(row["id"])["status"] == "REVOKED"


@pytest.mark.parametrize("status", ["REQUESTED", "FAILED"])
def test_revoke_of_open_or_failed_order_removes_the_grant_first_then_cancels(
        osp_factory, companies, wallet_fake, monkeypatch, status):
    # README 8.2: REQUESTED/FAILED -> CANCELLED, no event; route CSP_ISSUER: the grant is removed first
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    row = seed_csp_row(w, "MEMBERSHIP", status)
    csp_has_grant(w, "membership")
    r = revoke(w)
    assert r.status_code == 200
    assert r.json()["result"] == {"companyId": U6["id"], "revoked": [], "cancelled": ["MEMBERSHIP"], "manualRevocation": []}
    assert [u for _m, u, _kw in w.traffic.to(ISSUER_URL, "DELETE")] == [f"{ISSUER_URL}/holders/{w.bpn}/grants/membership"]
    assert (w.bpn, "membership") not in w.osp.csp.grants
    assert store().get_credential_by_id(row["id"])["status"] == "CANCELLED"
    assert w.osp.events("CredentialRevoked") == []


@pytest.mark.parametrize("status,failure", [
    (503, "503"), (401, "401"), (httpx.ReadTimeout("timeout"), "timeout"), (httpx.ConnectError("down"), "connect")])
def test_revoke_of_open_order_with_technical_failure_is_502_and_row_unchanged(
        osp_factory, companies, wallet_fake, monkeypatch, status, failure):
    # README 8.2: "if this fails technically, 502 upstream-error, and the credential keeps its status"
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    row = seed_csp_row(w, "MEMBERSHIP", "REQUESTED")
    csp_has_grant(w, "membership")
    w.traffic.fail(delete_grant_rule, status)
    r = revoke(w)
    assert_problem(r, 502, "upstream-error", True)
    assert store().get_credential_by_id(row["id"])["status"] == "REQUESTED"
    assert (w.bpn, "membership") in w.osp.csp.grants
    assert w.osp.events("CredentialRevoked") == []
    w.traffic.clear_rules()                                  # repetition does the rest
    assert revoke(w, n=10).status_code == 200
    assert store().get_credential_by_id(row["id"])["status"] == "CANCELLED"


def test_revoke_of_issued_credential_with_technical_failure_is_502_and_stays_issued(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 8.2 ISSUED bullet: technical error -> 502 upstream-error; a repetition does the rest
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    row = seed_csp_row(w, "MEMBERSHIP", "ISSUED")
    csp_has_grant(w, "membership")
    w.traffic.fail(delete_grant_rule, 503)
    assert_problem(revoke(w), 502, "upstream-error", True)
    assert store().get_credential_by_id(row["id"])["status"] == "ISSUED"
    assert w.osp.events("CredentialRevoked") == []
    w.traffic.clear_rules()
    assert revoke(w, n=10).status_code == 200
    assert store().get_credential_by_id(row["id"])["status"] == "REVOKED" and len(w.osp.events("CredentialRevoked")) == 1


def test_readme_8_2_partial_technical_failure_keeps_the_revoked_type_revoked_and_a_repetition_does_the_rest(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 8.2 ISSUED bullet: "Technical error: 502 upstream-error; credentials already revoked stay revoked, a
    # repetition does the rest". Types in the given order: BPN first (succeeds), MEMBERSHIP (DELETE fails).
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    bpn = seed_csp_row(w, "BPN", "ISSUED")
    ms = seed_csp_row(w, "MEMBERSHIP", "ISSUED")
    csp_has_grant(w, "bpn")
    csp_has_grant(w, "membership")
    w.traffic.fail(lambda m, u, kw: delete_grant_rule(m, u, kw) and u.endswith("/membership"), 503)
    r = revoke(w, credentialTypes=["BPN", "MEMBERSHIP"])
    assert_problem(r, 502, "upstream-error", True)
    assert store().get_credential_by_id(bpn["id"])["status"] == "REVOKED"
    assert store().get_credential_by_id(ms["id"])["status"] == "ISSUED"
    assert [e["data"]["credentialType"] for e in w.osp.events("CredentialRevoked")] == ["BPN"]
    w.traffic.clear_rules()
    r = revoke(w, n=10, credentialTypes=["BPN", "MEMBERSHIP"])
    assert r.status_code == 200 and r.json()["state"] == "DONE"
    assert r.json()["result"]["revoked"] == ["MEMBERSHIP"]                 # BPN is not revoked a second time
    assert [store().get_credential_by_id(x["id"])["status"] for x in (bpn, ms)] == ["REVOKED", "REVOKED"]
    assert sorted(e["data"]["credentialType"] for e in w.osp.events("CredentialRevoked")) == ["BPN", "MEMBERSHIP"]
    assert [u.rsplit("/", 1)[1] for _m, u, _kw in w.traffic.to(ISSUER_URL, "DELETE")] == [
        "bpn", "membership", "membership"]


def test_readme_6_6_existing_holder_and_existing_grant_count_as_success(osp_factory, companies, wallet_fake,
                                                                          monkeypatch):
    # README 6.6 / 11.4 / 11.5: "an existing holder or an existing grant counts as success": the holder is already
    # registered at the CSP stand-in (PUT /holders -> 200 instead of 201) and the grants exist as well
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    csp_has_grant(w, "bpn")
    csp_has_grant(w, "membership")                                          # holder and both grants exist
    r = issue(w)
    assert r.status_code == 200 and r.json()["state"] == "RUNNING", r.text
    w.callbacks.wait(2)
    puts = [c for c in w.traffic.to(f"{ISSUER_URL}/holders/{w.bpn}", "PUT") if "/grants/" not in c[1]]
    assert len(puts) == 1
    assert {store().get_credential(U6["id"], t)["status"] for t in ("BPN", "MEMBERSHIP")} == {"ISSUED"}
    assert len(w.osp.events("CredentialsIssued")) == 1
    assert w.osp.events("CredentialIssuanceFailed") == []


# ------------------------------------------------------------------------ case 15: route must fit
def test_case_15_csp_mode_with_sap_div_wallet_is_no_issuer_route_and_no_csp_call(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 13 case 15, 6.3 rule 3: ISSUER_MODE CSP, issuance mode ISSUER_WRITES -> 409 no-issuer-route
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    r = issue(w, U4)
    assert_problem(r, 409, "no-issuer-route", False)
    assert w.traffic.csp() == []
    assert w.osp.csp.holders == {} and w.osp.csp.grants == {} and w.osp.csp.callbacks == []
    assert w.fake.holder_access_calls == []
    assert store().get_credential(U4["id"], "BPN") is None and store().get_credential(U4["id"], "MEMBERSHIP") is None


@pytest.mark.parametrize("routes,company", [
    ("SAP_DIV:ISSUER_SERVICE", "u4"),            # ISSUER_SERVICE only fits HOLDER_REQUESTS
    ("IDENTITY_HUB:CREDENTIAL_ISSUER", "u5"),    # CREDENTIAL_ISSUER only fits ISSUER_WRITES
    ("CSP:CREDENTIAL_ISSUER", "u6"),
])
def test_readme_6_3_rule_4_route_must_fit_the_issuance_mode(
        osp_factory, companies, wallet_fake, monkeypatch, routes, company):
    # README 6.3 rule 4 (configuration error): 409 no-issuer-route, nothing ordered, no row
    osp = osp_factory({"ISSUER_MODE": "OWN", "ISSUER_ROUTES": routes})
    c = COMPANIES[company]
    r = osp.post(f"{P}/steps/issue-credentials", osp.service("svc-c4-m1"), json=step_input(c["id"]))
    assert_problem(r, 409, "no-issuer-route", False)
    assert store().get_credential(c["id"], "BPN") is None and wallet_fake.holder_access_calls == []


ROUTES_ALL = "SAP_DIV:CREDENTIAL_ISSUER,IDENTITY_HUB:ISSUER_SERVICE,CSP:ISSUER_SERVICE"


@pytest.mark.parametrize("company,route,host", [
    ("u4", "CREDENTIAL_ISSUER", "http://cred-issuer.test"),
    ("u5", "ISSUER_SERVICE", "http://is-admin.test"),
    ("u6", "ISSUER_SERVICE", "http://is-admin.test"),
])
def test_readme_6_3_rule_2_non_empty_issuer_routes_select_the_configured_route(
        osp_factory, companies, wallet_fake, monkeypatch, company, route, host):
    # README 6.3 rule 2 (+ rule 4: the route fits the issuance mode): the route of the wallet provider comes from
    # ISSUER_ROUTES, is stored with the order, and the order goes to that route. Only the route selection is
    # tested, not the full order protocol: a recording fake answers every call with 2xx.
    calls: list[tuple[str, str]] = []

    def fake(method, url, timeout=phttp.DEFAULT_TIMEOUT, **kw):
        calls.append((method, url))
        return httpx.Response(200, json={"access_token": "t", "token_type": "Bearer", "expires_in": 300},
                              request=httpx.Request(method, url))

    osp = osp_factory({
        "ISSUER_MODE": "OWN", "ISSUER_ROUTES": ROUTES_ALL, "CALLBACK_BASE_URL": BASE,
        "CREDENTIAL_ISSUER_URL": "http://cred-issuer.test", "CREDENTIAL_ISSUER_TOKEN_URL": "http://cred-issuer.test/token",
        "CREDENTIAL_ISSUER_CLIENT_ID": "m1", "CREDENTIAL_ISSUER_CLIENT_SECRET": "s",
        "ISSUER_SERVICE_ADMIN_URL": "http://is-admin.test", "ISSUER_SERVICE_API_KEY": "k",
        "ISSUER_SERVICE_PARTICIPANT_ID": "issuer", "ISSUER_DID": "did:web:issuer.osp-a.example.org",
        "ISSUER_SERVICE_CREDENTIAL_DEFINITIONS": "BPN:bpn-credential-def,MEMBERSHIP:membership-credential-def",
        "CREDENTIAL_FORMAT": "VC1_0_JWT"})
    tokens._load_jwks()   # load the IAM signing keys before the fake replaces portal_common.http.request
    monkeypatch.setattr(phttp, "request", fake)
    c = COMPANIES[company]
    r = osp.post(f"{P}/steps/issue-credentials", osp.service("svc-c4-m1"), json=step_input(c["id"]))
    assert r.status_code == 200, r.text
    assert store().get_credential(c["id"], "BPN")["route"] == route
    assert store().get_credential(c["id"], "MEMBERSHIP")["route"] == route
    assert any(u.startswith(host) for _m, u in calls), calls               # the order goes to the configured route
    other = "http://is-admin.test" if host == "http://cred-issuer.test" else "http://cred-issuer.test"
    assert not any(u.startswith(other) for _m, u in calls)


def test_bring_your_own_wallet_has_no_route_with_a_non_empty_issuer_routes(osp_factory, companies, wallet_fake):
    # README 6.3 last paragraph / rule 2: provider BRING_YOUR_OWN has no entry in ISSUER_ROUTES -> 409 no-issuer-route
    # (OPEN-QUESTION as above: CREDENTIAL_OFFER is rejected before rule 2)
    osp = osp_factory({"ISSUER_MODE": "OWN", "ISSUER_ROUTES": ROUTES_ALL})
    byo = COMPANIES["u7_byo"]
    r = osp.post(f"{P}/steps/issue-credentials", osp.service("svc-c4-m1"), json=step_input(byo["id"]))
    assert_problem(r, 409, "no-issuer-route", False)
    assert store().get_credential(byo["id"], "BPN") is None and wallet_fake.holder_access_calls == []


def test_readme_6_3_rule_2_wallet_provider_without_entry_in_issuer_routes(osp_factory, companies, wallet_fake):
    # README 6.3 rule 2: ISSUER_ROUTES set but no entry for the provider -> 409 no-issuer-route
    osp = osp_factory({"ISSUER_MODE": "OWN", "ISSUER_ROUTES": "IDENTITY_HUB:ISSUER_SERVICE"})
    r = osp.post(f"{P}/steps/issue-credentials", osp.service("svc-c4-m1"), json=step_input(U4["id"]))
    assert_problem(r, 409, "no-issuer-route", False)


def test_bring_your_own_wallet_has_no_route_in_the_csp_mode_either(osp_factory, companies, wallet_fake, monkeypatch):
    # README 6.3 last paragraph: BRING_YOUR_OWN / CREDENTIAL_OFFER has no route in 0.2
    # OPEN-QUESTION: README 6.3 rule 2 (OWN + empty ISSUER_ROUTES => STUB) vs case 5 (BRING_YOUR_OWN => 409
    # no-issuer-route): case 5 wins; the issuance mode CREDENTIAL_OFFER is rejected BEFORE rule 2 (and before the STUB
    # rule 3 of the CSP mode with an empty CSP_ISSUER_URL).
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    byo = COMPANIES["u7_byo"]
    r = issue(w, byo)
    assert_problem(r, 409, "no-issuer-route", False)
    assert w.traffic.csp() == [] and store().get_credential(byo["id"], "BPN") is None


# ------------------------------------------------------------------------------ route STUB, no CSP call
def _assert_no_csp_traffic(osp, traffic) -> None:
    assert traffic.csp() == []
    assert osp.csp.holders == {} and osp.csp.grants == {} and osp.csp.callbacks == []
    assert all(w["credentials"] == [] for w in osp.csp.wallets.values())


def test_route_stub_with_csp_mode_and_empty_csp_issuer_url_makes_no_csp_call(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 6.3 rule 3 ("with an empty CSP_ISSUER_URL STUB"), 11.6; CSP wallet U6 with HOLDER_REQUESTS
    osp = osp_factory({"ISSUER_MODE": "CSP", "CSP_ISSUER_URL": "", "STUB_ISSUER_DELAY_SECONDS": "5"}, csp=True)
    traffic = Traffic(monkeypatch)
    r = osp.post(f"{P}/steps/issue-credentials", osp.service("svc-c4-m1"), json=step_input(U6["id"]))
    assert r.status_code == 200 and r.json()["state"] == "RUNNING"
    for ty in ("BPN", "MEMBERSHIP"):
        row = store().get_credential(U6["id"], ty)
        assert row["status"] == "REQUESTED" and row["route"] == "STUB" and row["request_ref"] == "stub-1"
        assert not row["issuer_did"]
    seam("modules.c4_m1.service").flush_timers()
    assert {store().get_credential(U6["id"], t)["status"] for t in ("BPN", "MEMBERSHIP")} == {"ISSUED"}
    assert len(osp.events("CredentialsIssued")) == 1
    assert wallet_fake.holder_access_calls == []     # README 8.1: no holder access for the route STUB
    _assert_no_csp_traffic(osp, traffic)


def test_route_stub_with_own_mode_and_empty_issuer_routes_makes_no_csp_call(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 6.3 rule 2 ("If ISSUER_ROUTES is empty, STUB applies"), OSP A of the hackathon (README 14); SAP DIV wallet
    osp = osp_factory({"ISSUER_MODE": "OWN", "ISSUER_ROUTES": "", "CSP_ISSUER_URL": ISSUER_URL, "STUB_ISSUER_DELAY_SECONDS": "5"},
                      csp=True)
    traffic = Traffic(monkeypatch)
    r = osp.post(f"{P}/steps/issue-credentials", osp.service("svc-c4-m1"), json=step_input(U4["id"]))
    assert r.status_code == 200 and r.json()["state"] == "RUNNING"
    assert store().get_credential(U4["id"], "BPN")["route"] == "STUB"
    assert wallet_fake.holder_access_calls == []
    _assert_no_csp_traffic(osp, traffic)


def test_route_stub_for_wallet_provider_stub_wins_even_with_csp_issuer_configured(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 6.3 rule 1: wallet provider STUB -> route STUB (U1 of README 14)
    osp = osp_factory({**CSP_ENV, "STUB_ISSUER_DELAY_SECONDS": "5"}, csp=True)
    traffic = Traffic(monkeypatch)
    r = osp.post(f"{P}/steps/issue-credentials", osp.service("svc-c4-m1"), json=step_input(U1["id"]))
    assert r.status_code == 200
    assert store().get_credential(U1["id"], "BPN")["route"] == "STUB"
    _assert_no_csp_traffic(osp, traffic)


# ------------------------------------------------------------------- case 16: errors of the CSP issuer
def test_case_16_other_home_osp_is_403_at_the_csp_and_409_issuer_rejected(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 13 case 16 first half: PUT /holders -> 403 -> 409 issuer-rejected, retryable false, no REQUESTED row
    w = start_csp(osp_factory, wallet_fake, monkeypatch, home_osp=OSP_B_ID)
    r = issue(w)
    assert_problem(r, 409, "issuer-rejected", False)
    assert [c[0] for c in w.traffic.to(f"{ISSUER_URL}/holders")] == ["PUT"]       # stopped at the holder
    not_requested(U6["id"])
    assert w.osp.events("CredentialsIssued") == [] and w.osp.csp.grants == {}
    assert w.fake.holder_access_calls in ([], [U6["id"]])


def test_case_16_did_not_equal_to_the_directory_is_409_at_the_csp_and_issuer_rejected(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 11.5: 409 DID does not match the directory -> issuer-rejected (README 8.1: "the CSP refuses")
    w = start_csp(osp_factory, wallet_fake, monkeypatch, directory_did="did:web:other.example.org:" + U6["bpn"])
    r = issue(w)
    assert_problem(r, 409, "issuer-rejected", False)
    not_requested(U6["id"])


def test_case_16_wrong_dataspace_is_422_at_the_csp_and_issuer_rejected(osp_factory, companies, wallet_fake, monkeypatch):
    # README 11.5: 422 memberOf is not the dataspace of the CSP -> issuer-rejected
    w = start_csp(osp_factory, wallet_fake, monkeypatch, env={"CSP_DATASPACE": "Some-Other-Dataspace"})
    r = issue(w)
    assert_problem(r, 409, "issuer-rejected", False)
    not_requested(U6["id"], "MEMBERSHIP")
    assert (w.bpn, "membership") not in w.osp.csp.grants
    assert not any("membership" in json.dumps(c[2].get("json")).lower() for c in
                   w.traffic.to(CSP_URL + "/identity", "POST"))        # no request for the refused type


@pytest.mark.parametrize("where,rule", [("holder", put_holder_rule), ("grant", grant_rule)])
def test_case_16_404_at_the_csp_is_issuer_rejected(osp_factory, companies, wallet_fake, monkeypatch, where, rule):
    # README 11.5: "Responses 403, 404, 409 and 422 of the CSP give 409 issuer-rejected"
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    w.traffic.fail(rule, 404)
    r = issue(w)
    assert_problem(r, 409, "issuer-rejected", False)
    not_requested(U6["id"])


FAILURES = [
    pytest.param(put_holder_rule, 503, id="holder-503"),
    pytest.param(put_holder_rule, 401, id="holder-401"),
    pytest.param(put_holder_rule, httpx.ReadTimeout("timeout"), id="holder-timeout"),
    pytest.param(grant_rule, 503, id="grant-503"),
    pytest.param(token_rule, 401, id="token-401"),
    pytest.param(token_rule, 503, id="token-503"),
    pytest.param(request_rule(), 503, id="wallet-request-503"),
    pytest.param(request_rule(), httpx.ReadTimeout("timeout"), id="wallet-request-timeout"),
]


@pytest.mark.parametrize("rule,action", FAILURES)
def test_case_16_technical_failure_is_502_upstream_error_retryable(
        osp_factory, companies, wallet_fake, monkeypatch, rule, action):
    # README 13 case 16 second half, 11.5 last paragraph: 401 (token or API), 5xx, timeout -> 502, retryable true
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    w.traffic.fail(rule, action)
    r = issue(w)
    assert_problem(r, 502, "upstream-error", True)
    not_requested(U6["id"])
    assert w.osp.events("CredentialsIssued") == []
    w.traffic.clear_rules()                                           # after the fix a repetition orders
    r = issue(w, n=2)
    assert r.status_code == 200 and r.json()["state"] == "RUNNING"
    w.callbacks.wait(2)
    assert {store().get_credential(U6["id"], t)["status"] for t in ("BPN", "MEMBERSHIP")} == {"ISSUED"}
    assert store().get_credential(U6["id"], "BPN")["attempt"] == 1       # a failed order is no attempt


def test_case_16_orders_already_sent_stay_requested_and_a_repetition_sends_only_the_rest(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 8.1 step 3: "Orders already sent stay REQUESTED; a repetition sends only the rest"
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    w.traffic.fail(request_rule("membership"), 503)
    r = issue(w)
    assert_problem(r, 502, "upstream-error", True)
    assert store().get_credential(U6["id"], "BPN")["status"] in ("REQUESTED", "ISSUED")   # callback may be quick
    not_requested(U6["id"], "MEMBERSHIP")
    first_wallet_state = [c["type"] for c in w.osp.csp.wallets[w.bpn]["credentials"]]
    assert first_wallet_state == ["bpn"]
    w.traffic.clear_rules()
    r = issue(w, n=2)
    assert r.status_code == 200 and r.json()["state"] == "RUNNING"
    w.callbacks.wait(2)                                               # bpn (first run) and membership (second run)
    assert [c["type"] for c in w.osp.csp.wallets[w.bpn]["credentials"]] == ["bpn", "membership"]   # bpn not sent again
    assert store().get_credential(U6["id"], "BPN")["attempt"] == 1
    assert store().get_credential(U6["id"], "MEMBERSHIP")["attempt"] == 1
    assert {store().get_credential(U6["id"], t)["status"] for t in ("BPN", "MEMBERSHIP")} == {"ISSUED"}
    assert len(w.osp.events("CredentialsIssued")) == 1


# --------------------------------------------------------------------------- case 19: issuer unreachable
def test_case_19_issuer_not_reachable_is_502_row_not_requested_then_repetition_orders(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 13 case 19: "502 upstream-error, the credential does not become REQUESTED; after the fix, a repetition
    # triggers it"
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    w.traffic.fail(csp_rule, httpx.ConnectError("connection refused"))
    r = issue(w)
    assert_problem(r, 502, "upstream-error", True)
    not_requested(U6["id"])
    assert w.osp.csp.holders == {} and w.osp.csp.wallets[w.bpn]["credentials"] == []
    assert w.osp.events("CredentialsIssued") == [] and w.osp.events("CredentialIssuanceFailed") == []
    w.traffic.clear_rules()
    r = issue(w, n=2)
    assert r.status_code == 200 and r.json()["state"] == "RUNNING"
    w.callbacks.wait(2)
    for ty in ("BPN", "MEMBERSHIP"):
        row = store().get_credential(U6["id"], ty)
        assert row["status"] == "ISSUED" and row["attempt"] == 1 and row["request_ref"] == f"{U6['id']}:{ty}:1"
    assert len(w.osp.events("CredentialsIssued")) == 1


def test_case_19_wallet_identity_api_not_reachable_is_502_and_row_not_requested(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 8.1 step 3: "issuer, CSP or wallet not reachable ... 502 upstream-error"
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    w.traffic.fail(request_rule(), httpx.ConnectError("connection refused"))
    r = issue(w)
    assert_problem(r, 502, "upstream-error", True)
    not_requested(U6["id"])
    assert w.osp.csp.wallets[w.bpn]["credentials"] == []


def test_case_19_wallet_answering_401_for_the_api_key_is_502_upstream_error(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 8.1 step 3 "unexpected response": wrong api key at the identity API (stand-in answers 401)
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    w.fake.access[U6["id"]]["apiKey"] = "wrong-api-key"
    r = issue(w)
    assert_problem(r, 502, "upstream-error", True)
    not_requested(U6["id"])
    assert "wrong-api-key" not in r.text


def test_case_19_wallet_not_active_is_409_wallet_not_ready_and_no_requested_row(
        osp_factory, companies, wallet_fake, monkeypatch):
    # README 8.1 precondition: wallet must be ACTIVE (409 wallet-not-ready, before any call); no REQUESTED row
    w = start_csp(osp_factory, wallet_fake, monkeypatch)
    wallet_fake.set("u6", status="REQUESTED")
    r = issue(w)
    assert_problem(r, 409, "wallet-not-ready", False)
    assert w.traffic.csp() == [] and store().get_credential(U6["id"], "BPN") is None
