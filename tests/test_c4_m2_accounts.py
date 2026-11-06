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
#  Assisted-By: Claude Code (claude-opus-5-5)
#  Assisted-By: Claude Code (claude-sonnet-5-5)
#################################################################################
"""C4-M2 wallet accounts (README 5, 6.3, 6.7, 6.10, 7.2, 7.3, 7.6 account callbacks, 8.2, 8.3, 9.2, 10, 12, 13
cases 14 to 17 and 19 to 22, case 25 for accounts; case 18 and the own wallet are `later` and not tested here).

Written test-first: red against the stand-in (no accounts, no store, no providers seam). Seams of TEAM3-PLAN.md
section 12 are imported lazily. SAP DIV answers only on request of the test (`STUB_CALLBACK_DELAY_SECONDS` 3600
plus `providers.flush_stand_in()`); time is driven by the kit `Clock` on `service.now` and `service.run_timer_once()`.

OPEN-QUESTION: README 6.10 says "order older than the deadline" for accounts without naming the variable; the
tests use PROVIDER_CALLBACK_TIMEOUT_MINUTES (the only deadline variable of the README).
OPEN-QUESTION: whether the deletion-deadline event WalletAccountDeletionFailed repeats on every timer pass is not
specified; the tests only require it after the first pass and do not assert a second pass.
OPEN-QUESTION: create-wallet-account for a company without any wallet row: README 8.2 says 409
`wallet-not-active` ("wallet ... not ACTIVE"); a 404 is also conceivable, the test follows 8.2.
OPEN-QUESTION: "the CSP stand-in no longer knows the account" (case 20) is observed through the
`account-deletion` order in `providers.orders()` and through the 409-then-recreate path (README 8.2), because
the stand-in has no other public read seam.
OPEN-QUESTION: README 5 (table `wallet_account`, `provider_name`) says `tu-` + technical_user_id for SAP DIV and CSP
only; 8.2 step 3 sets it for every account. The tests follow 8.2 (every provider, IdentityHub too).
OPEN-QUESTION: README 8.3 step 3 / 6.9 do not say whether deleting a FAILED account answers RUNNING (the object was
not complete at the call) or DONE; the test of that case does not assert the step state, only the account and event.
OPEN-QUESTION: README 8.3 gives the `walletAccountRef` conflict in the Input paragraph and the REQUESTED precondition
under Preconditions; when both apply the tests assert preconditions first (invalid-state), then the conflict.
OPEN-QUESTION: credentials_state of an account that became DELETED without retrieval: README 6.3 only deletes the
row, 6.7 names no transition, so the tests expect the value to stay as it was (AVAILABLE).

Time: `expires_at`, `provider_ordered_at`, `deletion_ordered_at` and the other timestamps must come from
`service.now()` at call time (never from import time or `datetime.now()` directly), so that the kit `Clock` drives them.
"""
from __future__ import annotations

import datetime as dt
import itertools
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from portal_common import http as phttp
from portal_common import problems
from tools import test_iam
from test_c4_m2_common import (COMPANIES, CSP_URL, Clock, assert_no_secret, companies, event_errors, osp_factory,  # noqa: F401
                               response_errors, schema_errors, seam, step_input, uuid_str)

MODULE = "c4-m2"
DIV, IH, CSPC, INA = COMPANIES["div"], COMPANIES["ih"], COMPANIES["csp"], COMPANIES["inactive"]
HOLD = {"STUB_CALLBACK_DELAY_SECONDS": "3600"}
ENV = {**HOLD, "IDENTITYHUB_STS_TOKEN_URL": "https://ih.example.org/api/sts/token",
       "IDENTITYHUB_CREDENTIAL_SERVICE_URL": "https://ih.example.org/api/credentials",
       "ACCOUNT_CREDENTIALS_RETENTION_DAYS": "30", "PROVIDER_CALLBACK_TIMEOUT_MINUTES": "60"}
CSP_TOKEN_URL = "https://csp-wallet.example.org/api/sts/token"
SAP_AUTH = "https://div.example.org/auth"
CB_SECRET, CB_CLIENT = "div-account-secret-do-not-leak", "div-account-client-do-not-leak"
_steps = itertools.count(100)
_VIEW = "/api/c4-m2/technical-users/{}/wallet-account"


@pytest.fixture(autouse=True)
def _csp_company_is_active(companies):
    # The kit lists the CSP company (c0000001-...) twice, as "csp" (ACTIVE) and as "u1" (REQUESTED); the later
    # entry wins in the fake C3-M1. README 8.2 needs an ACTIVE company for a new wallet account.
    companies.set_status(COMPANIES["csp"]["id"], "ACTIVE")


# ------------------------------------------------------------------------------------------ helpers
def m2():
    return seam("modules.c4_m2.interface")


def service():
    return seam("modules.c4_m2.service")


def providers():
    return seam("modules.c4_m2.providers")


def tu(n: int) -> str:
    return f"7b0c0000-0000-4000-8000-{n:012d}"


def store():
    return m2().store()


def make_wallet(company: dict, provider: str) -> dict:
    out = m2().create_wallet(step_input(company["id"], next(_steps), provider=provider))
    if provider == "SAP_DIV":
        providers().flush_stand_in()
    w = store().get_wallet(company["id"])
    assert w and w["status"] == "ACTIVE", (out, w)
    return w


def create(company: dict, n: int, **extra) -> dict:
    return m2().create_wallet_account(step_input(company["id"], next(_steps), technicalUserId=tu(n), **extra))


def delete(company: dict, n: int, **extra) -> dict:
    return m2().delete_wallet_account(step_input(company["id"], next(_steps), technicalUserId=tu(n), **extra))


def acct(n: int) -> dict | None:
    return store().get_account(tu(n))


def creds(n: int) -> dict | None:
    return store().get_account_credentials(acct(n)["id"])


def evs(osp, type_: str, n: int | None = None) -> list[dict]:
    return [e for e in osp.events(type_) if n is None or e["data"].get("technicalUserId") == tu(n)]


def account_orders(kind: str | None = None) -> list[dict]:
    return [o for o in providers().orders() if o["kind"] in ((kind,) if kind else ("account", "account-deletion"))]


def step_problem(fn, company: dict, n: int, **extra) -> problems.Problem:
    with pytest.raises(Exception) as e:
        fn(step_input(company["id"], next(_steps), technicalUserId=tu(n), **extra))
    return problems.to_problem(MODULE, e.value, True)


def assert_problem(p, status: int, name: str, retryable: bool = False) -> None:
    assert p.status == status and p.name == name, (p.status, p.name, p.detail)
    assert p.ext.get("retryable") is retryable


def plain_secret(n: int) -> str:
    r = creds(n)
    return seam("modules.c4_m2.crypto").decrypt(r["client_secret_encrypted"], r["nonce"], r["key_version"])


def person(osp, uid: str, company: dict | None, roles=("IT Admin",), given="Erika", family="Mustermann") -> str:
    return osp.person(uid, list(roles), company["id"] if company else None, company["bpn"] if company else None,
                      given=given, family=family)


def retrieve(osp, token, n: int):
    return osp.post(_VIEW.format(tu(n)) + "/credentials", token)


def ptype(r) -> str:
    assert r.headers["content-type"].startswith("application/problem+json"), r.text
    return r.json()["type"]


def div_token(osp) -> str:
    return osp.service("sa-div-callback", ["submit_wallet_callback"])


def cb_create(osp, ref: str, token: str | None = "default", secret: str = CB_SECRET):
    return osp.post(f"/api/c4-m2/callbacks/sap-div/technical-users/{ref}",
                    div_token(osp) if token == "default" else token,
                    json={"authenticationServiceUrl": SAP_AUTH, "clientID": CB_CLIENT, "clientSecret": secret})


def cb_delete(osp, ref: str, token: str | None = "default"):
    return osp.post(f"/api/c4-m2/callbacks/sap-div/technical-users/{ref}/delete",
                    div_token(osp) if token == "default" else token)


def div_requested(osp_factory, n: int = 1, env: dict | None = None):
    """OSP, SAP DIV wallet ACTIVE and account n REQUESTED (ordered, no callback yet)."""
    osp = osp_factory(env={**ENV, **(env or {})})
    make_wallet(DIV, "SAP_DIV")
    create(DIV, n)
    return osp


def div_active(osp_factory, n: int = 1, env: dict | None = None):
    osp = div_requested(osp_factory, n, env)
    providers().flush_stand_in()
    assert acct(n)["status"] == "ACTIVE"
    return osp


def assert_account_result(out: dict, n: int, company: dict, state: str, provider: str, status: str) -> dict:
    # README 8.2 Result, openapi StepResultWalletAccount
    assert out["state"] == state and schema_errors(MODULE, "StepResultWalletAccount", out) == []
    res = out["result"]
    assert res["technicalUserId"] == tu(n) and res["companyId"] == company["id"]
    assert res["provider"] == provider and res["status"] == status
    assert res["walletAccountRef"] == acct(n)["id"]
    return res


# -------------------------------------------------------------- case 14: SAP DIV, provider async
def test_case_14_sap_div_account_running_then_active_after_callback(osp_factory, companies, caplog):
    # README 13 case 14, 8.2 steps 3-5, 6.3, 10
    caplog.set_level("DEBUG")
    osp = osp_factory(env=ENV)
    make_wallet(DIV, "SAP_DIV")
    out = create(DIV, 1)
    res = assert_account_result(out, 1, DIV, "RUNNING", "SAP_DIV", "REQUESTED")
    a = acct(1)
    assert a["status"] == "REQUESTED" and a["provider_name"] == f"tu-{tu(1)}"           # README 5
    assert a["provider"] == "SAP_DIV" and a["company_id"] == DIV["id"] and a["credentials_state"] == "NONE"
    assert a["provider_ordered_at"] and a["wallet_id"] == store().get_wallet(DIV["id"])["id"]
    ref = res["walletAccountRef"]
    assert [o["external_id"] for o in account_orders("account")] == [ref]
    assert account_orders("account")[0]["bpn"] == DIV["bpn"] and account_orders("account")[0]["provider"] == "SAP_DIV"
    assert evs(osp, "WalletAccountCreated") == []

    providers().flush_stand_in()          # callback POST /callbacks/sap-div/technical-users/{externalId}
    a = acct(1)
    assert a["status"] == "ACTIVE" and a["credentials_state"] == "AVAILABLE"
    created = evs(osp, "WalletAccountCreated")
    assert len(created) == 1 and event_errors(MODULE, created[0]) == []
    assert created[0]["data"] == {"technicalUserId": tu(1), "companyId": DIV["id"], "walletAccountRef": a["id"],
                                  "provider": "SAP_DIV"}
    assert a["id"] == ref and evs(osp, "WalletAccountFailed") == []
    # README 13 case 14: no client secret / client ID in event, step result, step_log, audit_log, logs
    row = creds(1)
    secret, client_id = plain_secret(1), row["client_id"]
    for s in (secret, client_id):
        assert_no_secret(s, [e["data"] for e in osp.events()], out, store().list_step_log(), store().list_audit(),
                         caplog.text)


def test_case_14_create_wallet_account_over_http_with_service_token(osp_factory, companies):
    # openapi POST /steps/create-wallet-account (x-permission execute_steps_c4_m2), README 8.2
    osp = osp_factory(env=ENV)
    make_wallet(DIV, "SAP_DIV")
    body = step_input(DIV["id"], 1, technicalUserId=tu(1))
    assert osp.post("/api/c4-m2/steps/create-wallet-account", json=body).status_code == 401
    assert osp.post("/api/c4-m2/steps/create-wallet-account", osp.service("sa-q", ["query_c4_m2"]),
                    json=body).status_code == 403
    r = osp.post("/api/c4-m2/steps/create-wallet-account", osp.service("svc-c4-m2"), json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["stepRunId"] == uuid_str(1) and out["state"] == "RUNNING"
    assert response_errors(MODULE, "POST", "/steps/create-wallet-account", 200, out) == []
    assert out["result"]["status"] == "REQUESTED" and out["result"]["provider"] == "SAP_DIV"
    assert out["result"]["walletAccountRef"] == acct(1)["id"] and out["result"]["technicalUserId"] == tu(1)
    assert set(out["result"]) <= {"walletAccountRef", "technicalUserId", "companyId", "provider", "status",
                                  "failureReason"}


def test_case_14_step_log_records_the_account_step_without_secrets(osp_factory, companies):
    # README 5 step_log; keys of TEAM3-PLAN 12.2
    osp = div_requested(osp_factory)
    entries = [e for e in store().list_step_log() if e["object_id"] in (tu(1), acct(1)["id"])]
    assert entries and all(set(e) >= {"step_run_id", "process_id", "step", "object_id", "state", "occurred_at"}
                           for e in entries)
    assert any(e["step"] == "create-wallet-account" for e in entries)


# -------------------------------------------------------------------------- case 16, case 17
def test_case_16_create_account_before_wallet_is_active_is_409_wallet_not_active(osp_factory, companies):
    # README 13 case 16, 8.2 preconditions
    osp = osp_factory(env=ENV)
    m2().create_wallet(step_input(DIV["id"], 1, provider="SAP_DIV"))          # REQUESTED, no callback yet
    assert store().get_wallet(DIV["id"])["status"] == "REQUESTED"
    assert_problem(step_problem(m2().create_wallet_account, DIV, 1), 409, "wallet-not-active")
    assert acct(1) is None and account_orders() == []
    r = osp.post("/api/c4-m2/steps/create-wallet-account", osp.service("svc-c4-m2"),
                 json=step_input(DIV["id"], 2, technicalUserId=tu(1)))
    assert r.status_code == 409 and ptype(r) == "urn:c4-m2:problem:wallet-not-active"
    assert r.json()["retryable"] is False


def test_case_16_company_without_any_wallet_is_409_wallet_not_active(osp_factory, companies):
    # README 8.2; OPEN-QUESTION (module docstring): no wallet row at all
    osp_factory(env=ENV)
    assert_problem(step_problem(m2().create_wallet_account, IH, 1), 409, "wallet-not-active")
    assert acct(1) is None


def test_case_17_deactivated_company_gets_no_account_but_can_delete(osp_factory, companies):
    # README 13 case 17, 8.2 preconditions, 8.3 "status of the company does not matter", 6.3 deactivated company
    osp = osp_factory(env=ENV)
    companies.set_status(INA["id"], "ACTIVE")         # the kit lists INA as INACTIVE; here it starts ACTIVE
    make_wallet(INA, "SAP_DIV")                       # wallet ACTIVE while the company is still active
    create(INA, 1)
    providers().flush_stand_in()
    assert acct(1)["status"] == "ACTIVE"
    companies.set_status(INA["id"], "INACTIVE")       # then the company is deactivated

    assert_problem(step_problem(m2().create_wallet_account, INA, 2), 409, "company-not-active", retryable=False)
    assert acct(2) is None and len(account_orders("account")) == 1
    r = osp.post("/api/c4-m2/steps/create-wallet-account", osp.service("svc-c4-m2"),
                 json=step_input(INA["id"], 3, technicalUserId=tu(2)))
    assert r.status_code == 409 and ptype(r) == "urn:c4-m2:problem:company-not-active"
    assert r.json()["retryable"] is False and acct(2) is None

    out = delete(INA, 1)                              # existing account: deletion works as usual
    assert out["state"] == "RUNNING" and acct(1)["status"] == "DELETING"
    providers().flush_stand_in()
    assert acct(1)["status"] == "DELETED" and len(evs(osp, "WalletAccountDeleted", 1)) == 1


# ------------------------------------------------------------------------- case 19: IdentityHub
def test_case_19_identityhub_two_users_active_with_the_same_sts_client_id(osp_factory, companies):
    # README 13 case 19, 8.2 step 4 IdentityHub, 6.3 "IdentityHub" (copy of the STS access)
    osp = osp_factory(env=ENV)
    w = make_wallet(IH, "IDENTITY_HUB")
    sts = store().get_secret(w["id"], "STS_ACCESS")
    outs = [create(IH, 1), create(IH, 2)]
    for n, out in zip((1, 2), outs):
        assert_account_result(out, n, IH, "RUNNING", "IDENTITY_HUB", "ACTIVE")      # ACTIVE within the call
        assert acct(n)["status"] == "ACTIVE" and acct(n)["credentials_state"] == "AVAILABLE"
        # OPEN-QUESTION: README 5 table lists `tu-` only for SAP DIV and CSP; 8.2 step 3 sets it for every account
        assert acct(n)["provider_name"] == f"tu-{tu(n)}"
    c1, c2 = creds(1), creds(2)
    assert c1["client_id"] == c2["client_id"] == sts["client_id"]
    assert c1["token_url"] == c2["token_url"] == ENV["IDENTITYHUB_STS_TOKEN_URL"]
    assert plain_secret(1) == plain_secret(2)         # a copy of the one STS access
    assert c1["client_secret_encrypted"] != c2["client_secret_encrypted"] or c1["nonce"] != c2["nonce"]
    for n in (1, 2):
        ev = evs(osp, "WalletAccountCreated", n)
        assert len(ev) == 1 and event_errors(MODULE, ev[0]) == []
        assert ev[0]["data"]["provider"] == "IDENTITY_HUB" and ev[0]["data"]["walletAccountRef"] == acct(n)["id"]
    assert account_orders() == []                     # nothing is ordered at the IdentityHub stand-in


def test_case_19_delete_at_identityhub_keeps_the_sts_access_for_the_others(osp_factory, companies):
    # README 8.3 step 4 IdentityHub, 6.3 "Deleting a wallet account changes nothing at the IdentityHub"
    osp = osp_factory(env=ENV)
    w = make_wallet(IH, "IDENTITY_HUB")
    create(IH, 1)
    create(IH, 2)
    out = delete(IH, 1)
    assert out["state"] == "RUNNING" and out["result"]["status"] == "DELETED"
    assert schema_errors(MODULE, "StepResultWalletAccount", out) == []
    assert acct(1)["status"] == "DELETED" and store().get_account_credentials(acct(1)["id"]) is None
    ev = evs(osp, "WalletAccountDeleted", 1)
    assert len(ev) == 1 and event_errors(MODULE, ev[0]) == []
    assert acct(2)["status"] == "ACTIVE" and creds(2)["client_id"] == store().get_secret(w["id"], "STS_ACCESS")["client_id"]
    assert store().get_secret(w["id"], "STS_ACCESS") is not None
    assert account_orders() == []


# ----------------------------------------------------------------------------- case 20: CSP
def test_case_20_csp_two_users_active_with_different_client_ids(osp_factory, companies):
    # README 13 case 20, 8.2 step 4 CSP, 11.3 stand-in (separate credentials per account)
    osp = osp_factory(env=ENV)
    make_wallet(CSPC, "CSP")
    outs = [create(CSPC, 1), create(CSPC, 2)]
    for n, out in zip((1, 2), outs):
        assert_account_result(out, n, CSPC, "RUNNING", "CSP", "ACTIVE")
        a = acct(n)
        assert a["status"] == "ACTIVE" and a["credentials_state"] == "AVAILABLE" and a["provider_ordered_at"]
        assert a["provider_name"] == f"tu-{tu(n)}"
        assert creds(n)["token_url"] == CSP_TOKEN_URL
        ev = evs(osp, "WalletAccountCreated", n)
        assert len(ev) == 1 and ev[0]["data"]["provider"] == "CSP"
    assert creds(1)["client_id"] != creds(2)["client_id"] and plain_secret(1) != plain_secret(2)
    assert sorted(o["external_id"] for o in account_orders("account")) == sorted([acct(1)["id"], acct(2)["id"]])


def test_case_20_delete_at_csp_revokes_the_account_at_the_stand_in(osp_factory, companies):
    # README 13 case 20, 8.3 step 4 CSP (DELETE .../accounts/{walletAccountRef}), 6.3
    osp = osp_factory(env=ENV)
    make_wallet(CSPC, "CSP")
    create(CSPC, 1)
    create(CSPC, 2)
    ref = acct(1)["id"]
    out = delete(CSPC, 1, walletAccountRef=ref)
    assert out["state"] == "RUNNING"
    assert out["result"]["status"] == "DELETED" and out["result"]["walletAccountRef"] == ref
    assert schema_errors(MODULE, "StepResultWalletAccount", out) == []
    assert acct(1)["status"] == "DELETED" and store().get_account_credentials(ref) is None
    ev = evs(osp, "WalletAccountDeleted", 1)
    assert len(ev) == 1 and event_errors(MODULE, ev[0]) == []
    assert ev[0]["data"] == {"technicalUserId": tu(1), "companyId": CSPC["id"], "walletAccountRef": ref}
    deletions = account_orders("account-deletion")
    assert [o["external_id"] for o in deletions] == [ref] and deletions[0]["bpn"] == CSPC["bpn"]
    assert acct(2)["status"] == "ACTIVE" and creds(2) is not None and evs(osp, "WalletAccountDeleted", 2) == []


def test_case_20_csp_409_account_exists_deletes_and_creates_again(osp_factory, companies):
    # README 8.2 step 4 CSP "409 (account from an aborted attempt): delete the account at the CSP and create it
    # again"; the aborted attempt is simulated by the row that never learned of the order
    osp = osp_factory(env=ENV)
    make_wallet(CSPC, "CSP")
    create(CSPC, 1)
    ref = acct(1)["id"]
    a = acct(1)
    store().delete_account_credentials(ref)
    a.update(status="REQUESTED", provider_ordered_at=None, credentials_state="NONE")
    store().put_account(a)
    out = m2().create_wallet_account(step_input(CSPC["id"], next(_steps), technicalUserId=tu(1)))   # re-order (8.2 step 1)
    assert out["state"] == "RUNNING" and acct(1)["id"] == ref
    assert acct(1)["status"] == "ACTIVE" and acct(1)["provider_ordered_at"] and creds(1)["token_url"] == CSP_TOKEN_URL
    # how a stand-in records a rejected (409) order is its own business: only the sequence of kinds for `ref` counts
    orders = [o for o in account_orders() if o["external_id"] == ref]
    kinds = [o["kind"] for o in orders]
    assert kinds.count("account") >= 2 and "account-deletion" in kinds, kinds
    first = kinds.index("account")
    last = len(kinds) - 1 - kinds[::-1].index("account")
    assert first < kinds.index("account-deletion") < last, kinds       # delete between the first and the last order
    assert orders[-1]["kind"] == "account" and orders[-1]["external_id"] == ref


def test_case_20_csp_technical_error_is_502_and_account_stays_requested(osp_factory, companies, monkeypatch):
    # README 8.2 step 4 "Technical error of the provider: 502 upstream-error, the account stays REQUESTED without
    # provider_ordered_at"; 14.3 ORDER_ERROR (503 of the stand-in), 6.9 a repetition sends the order again
    osp = osp_factory(env=ENV)
    make_wallet(CSPC, "CSP")
    monkeypatch.setenv("STUB_FAILURES", f"{CSPC['bpn']}:ORDER_ERROR")
    assert_problem(step_problem(m2().create_wallet_account, CSPC, 1), 502, "upstream-error", retryable=True)
    a = acct(1)
    assert a["status"] == "REQUESTED" and not a["provider_ordered_at"] and creds(1) is None
    assert osp.events("WalletAccountCreated") == [] and osp.events("WalletAccountFailed") == []
    monkeypatch.setenv("STUB_FAILURES", "")
    out = m2().create_wallet_account(step_input(CSPC["id"], next(_steps), technicalUserId=tu(1)))
    assert out["state"] == "RUNNING" and acct(1)["status"] == "ACTIVE" and acct(1)["id"] == a["id"]
    assert len(evs(osp, "WalletAccountCreated", 1)) == 1


# ------------------------------------------------------------- case 21: delete at SAP DIV, timeouts
def test_case_21_delete_at_sap_div_running_then_deleted_after_callback(osp_factory, companies):
    # README 13 case 21, 8.3 step 4 SAP DIV, 6.3, 7.6 delete callback, 6.7 credentials of the account
    osp = div_active(osp_factory)
    ref = acct(1)["id"]
    assert creds(1) is not None                                    # not retrieved yet
    out = delete(DIV, 1, walletAccountRef=ref)
    assert out["state"] == "RUNNING" and schema_errors(MODULE, "StepResultWalletAccount", out) == []
    assert out["result"]["status"] == "DELETING" and out["result"]["walletAccountRef"] == ref
    a = acct(1)
    assert a["status"] == "DELETING" and a["deletion_ordered_at"]
    assert [o["external_id"] for o in account_orders("account-deletion")] == [ref]
    assert evs(osp, "WalletAccountDeleted") == []

    providers().flush_stand_in()          # POST /callbacks/sap-div/technical-users/{externalId}/delete
    assert acct(1)["status"] == "DELETED" and store().get_account_credentials(ref) is None
    ev = evs(osp, "WalletAccountDeleted", 1)
    assert len(ev) == 1 and event_errors(MODULE, ev[0]) == []
    assert ev[0]["data"] == {"technicalUserId": tu(1), "companyId": DIV["id"], "walletAccountRef": ref}

    again = delete(DIV, 1, walletAccountRef=ref)                    # repetition
    assert again["state"] == "DONE" and again["result"]["status"] == "DELETED"
    assert len(evs(osp, "WalletAccountDeleted", 1)) == 1 and len(account_orders("account-deletion")) == 1


def test_case_21_repeat_while_deleting_is_running_without_second_order(osp_factory, companies):
    # README 8.3 step 5 "DELETING with deletion_ordered_at: RUNNING"
    osp = div_active(osp_factory)
    delete(DIV, 1)
    out = delete(DIV, 1)
    assert out["state"] == "RUNNING" and out["result"]["status"] == "DELETING"
    assert len(account_orders("account-deletion")) == 1


def test_case_21_delete_without_deletion_callback_fails_after_the_deadline(osp_factory, companies, monkeypatch):
    # README 13 case 21 (NO_DELETE_CALLBACK), 6.3 DELETING -> DELETING + WalletAccountDeletionFailed, 6.10
    osp = osp_factory(env={**ENV, "STUB_FAILURES": f"{tu(1)}:NO_DELETE_CALLBACK"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    make_wallet(DIV, "SAP_DIV")
    create(DIV, 1)
    providers().flush_stand_in()
    ref = acct(1)["id"]
    delete(DIV, 1)
    providers().flush_stand_in()                                    # the stand-in does not call back
    assert acct(1)["status"] == "DELETING"
    clock.advance(minutes=30)
    service().run_timer_once()
    assert evs(osp, "WalletAccountDeletionFailed") == []            # before the deadline
    clock.advance(minutes=31)                                       # 61 minutes after the order
    service().run_timer_once()
    assert acct(1)["status"] == "DELETING"                          # status stays DELETING
    failed = evs(osp, "WalletAccountDeletionFailed", 1)
    assert len(failed) == 1 and event_errors(MODULE, failed[0]) == []
    d = failed[0]["data"]
    assert (d["technicalUserId"], d["companyId"], d["walletAccountRef"]) == (tu(1), DIV["id"], ref)
    assert d["reason"] == "PROVIDER_TIMEOUT"                        # openapi EventWalletAccountDeletionFailed
    assert evs(osp, "WalletAccountDeleted") == []


def test_case_21_no_callback_on_create_fails_with_provider_timeout(osp_factory, companies, monkeypatch):
    # README 6.3 REQUESTED -> FAILED (PROVIDER_TIMEOUT) + WalletAccountFailed, 6.10, 14.3 `<technicalUserId>:NO_CALLBACK`
    osp = osp_factory(env={**ENV, "STUB_FAILURES": f"{tu(1)}:NO_CALLBACK"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    make_wallet(DIV, "SAP_DIV")
    create(DIV, 1)
    providers().flush_stand_in()
    assert acct(1)["status"] == "REQUESTED"
    clock.advance(minutes=59)
    service().run_timer_once()
    assert acct(1)["status"] == "REQUESTED" and evs(osp, "WalletAccountFailed") == []
    clock.advance(minutes=2)
    service().run_timer_once()
    a = acct(1)
    assert a["status"] == "FAILED" and a["failure_reason"] == "PROVIDER_TIMEOUT"
    failed = evs(osp, "WalletAccountFailed", 1)
    assert len(failed) == 1 and event_errors(MODULE, failed[0]) == []
    assert failed[0]["data"] == {"technicalUserId": tu(1), "companyId": DIV["id"], "walletAccountRef": a["id"],
                                 "reason": "PROVIDER_TIMEOUT"}
    service().run_timer_once()
    assert len(evs(osp, "WalletAccountFailed", 1)) == 1 and evs(osp, "WalletAccountCreated") == []
    # a late callback of the middleware is rejected
    r = cb_create(osp, a["id"])
    assert r.status_code == 409 and ptype(r) == "urn:c4-m2:problem:invalid-state"
    assert acct(1)["status"] == "FAILED" and creds(1) is None
    # FAILED: a repetition is DONE without event (8.2 step 1), view shows failureReason (7.2)
    out = create(DIV, 1)
    assert out["state"] == "DONE" and out["result"]["status"] == "FAILED"
    assert out["result"]["failureReason"] == "PROVIDER_TIMEOUT"
    assert len(evs(osp, "WalletAccountFailed", 1)) == 1


# ------------------------------------------------------------------- case 22: retention of credentials
def test_case_22_credentials_not_retrieved_expire_after_the_retention(osp_factory, companies, monkeypatch):
    # README 13 case 22, 6.7, 6.10 "Clean up credentials", 7.3 step 3
    osp = osp_factory(env={**ENV, "ACCOUNT_CREDENTIALS_RETENTION_DAYS": "7"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    make_wallet(CSPC, "CSP")
    create(CSPC, 1)
    ref = acct(1)["id"]
    assert creds(1)["expires_at"] == clock() + dt.timedelta(days=7)
    clock.advance(days=6)
    service().run_timer_once()
    assert creds(1) is not None and acct(1)["credentials_state"] == "AVAILABLE"
    clock.advance(days=1, minutes=1)
    service().run_timer_once()
    assert store().get_account_credentials(ref) is None
    assert acct(1)["credentials_state"] == "EXPIRED" and acct(1)["status"] == "ACTIVE"
    token = person(osp, "p1-erika", CSPC)
    r = osp.get(_VIEW.format(tu(1)), token)
    assert r.status_code == 200 and r.json()["credentialsState"] == "EXPIRED"
    assert r.json()["credentialsExpireAt"] is None
    r = retrieve(osp, token, 1)
    assert r.status_code == 410 and ptype(r) == "urn:c4-m2:problem:credentials-expired"


# ------------------------------------------------------------------- case 15: retrieval (README 7.3)
def csp_account(osp_factory, n: int = 1, env: dict | None = None):
    osp = osp_factory(env={**ENV, **(env or {})})
    make_wallet(CSPC, "CSP")
    create(CSPC, n)
    return osp


def test_case_15_p1_retrieves_credentials_once(osp_factory, companies):
    # README 13 case 15, 7.3 steps 4-5, openapi WalletAccountCredentials
    osp = csp_account(osp_factory)
    secret, client_id, ref = plain_secret(1), creds(1)["client_id"], acct(1)["id"]
    p1 = person(osp, "p1-erika", CSPC)
    r = retrieve(osp, p1, 1)
    assert r.status_code == 200, r.text
    assert r.headers["Cache-Control"] == "no-store"
    body = r.json()
    assert schema_errors(MODULE, "WalletAccountCredentials", body) == []
    assert body["walletAccountRef"] == ref and body["tokenUrl"] == CSP_TOKEN_URL
    assert body["clientId"] == client_id and body["clientSecret"] == secret
    assert body["did"] == "did:web:csp-wallet.example.org:BPNLIUK2REMLK3F4"
    assert body["credentialServiceUrl"] == "https://csp-wallet.example.org/api/credentials/v1/participants/BPNLIUK2REMLK3F4"
    assert store().get_account_credentials(ref) is None and acct(1)["credentials_state"] == "RETRIEVED"
    entries = [e for e in store().list_audit() if e["sub"] == "p1-erika"]
    assert entries and all(e["company_id"] == CSPC["id"] for e in entries)
    assert_no_secret("Erika", store().list_audit())             # no names in the audit log
    assert_no_secret("Mustermann", store().list_audit())
    r2 = retrieve(osp, p1, 1)
    assert r2.status_code == 410 and ptype(r2) == "urn:c4-m2:problem:already-retrieved"
    assert "clientSecret" not in r2.text


def test_case_15_other_company_is_404_member_403_applicant_without_company_403_no_token_401(osp_factory, companies):
    # README 13 case 15, 7.3 step 1, 6.8 ("the permission is checked before the company"), 12
    osp = csp_account(osp_factory)
    assert retrieve(osp, None, 1).status_code == 401
    p3 = person(osp, "p3-applicant", None, roles=("Applicant",))
    r = retrieve(osp, p3, 1)
    assert r.status_code == 403 and ptype(r) == "urn:c4-m2:problem:forbidden"
    p4 = person(osp, "p4-member", CSPC, roles=("Member",))
    r = retrieve(osp, p4, 1)
    assert r.status_code == 403 and ptype(r) == "urn:c4-m2:problem:forbidden"
    p2 = person(osp, "p2-other", IH)
    r = retrieve(osp, p2, 1)
    assert r.status_code == 404 and ptype(r) == "urn:c4-m2:problem:not-found"
    unknown = osp.post(_VIEW.format(tu(99)) + "/credentials", person(osp, "p1-erika", CSPC))
    assert unknown.status_code == 404
    assert creds(1) is not None and acct(1)["credentials_state"] == "AVAILABLE"        # nothing was consumed


def test_case_15_account_not_active_is_409_invalid_state(osp_factory, companies):
    # README 7.3 step 2
    osp = div_requested(osp_factory)
    r = retrieve(osp, person(osp, "p1-div", DIV), 1)
    assert r.status_code == 409 and ptype(r) == "urn:c4-m2:problem:invalid-state"


def test_case_15_credentials_state_none_is_409_no_credentials(osp_factory, companies):
    # README 7.3 step 3 `NONE`
    osp = csp_account(osp_factory)
    a = acct(1)
    store().delete_account_credentials(a["id"])
    a["credentials_state"] = "NONE"
    store().put_account(a)
    r = retrieve(osp, person(osp, "p1-erika", CSPC), 1)
    assert r.status_code == 409 and ptype(r) == "urn:c4-m2:problem:no-credentials"


def test_case_15_two_concurrent_calls_exactly_one_gets_the_credentials(osp_factory, companies):
    # README 13 case 15, 7.3 "Concurrent calls: only one gets the data", store `pop_account_credentials`
    osp = csp_account(osp_factory)
    p1 = person(osp, "p1-erika", CSPC)
    barrier = threading.Barrier(2)

    def call():
        barrier.wait(timeout=10)
        return retrieve(osp, p1, 1)

    with ThreadPoolExecutor(2) as pool:
        results = [f.result(timeout=30) for f in [pool.submit(call), pool.submit(call)]]
    assert sorted(r.status_code for r in results) == [200, 410], [r.text for r in results]
    loser = next(r for r in results if r.status_code == 410)
    assert ptype(loser) == "urn:c4-m2:problem:already-retrieved"


def test_case_15_store_pop_account_credentials_is_exactly_once(osp_factory, companies):
    # TEAM3-PLAN 12.2 `pop_account_credentials` (atomic read + delete)
    osp_factory(env=ENV)
    make_wallet(CSPC, "CSP")
    create(CSPC, 1)
    ref = acct(1)["id"]
    first, second = store().pop_account_credentials(ref), store().pop_account_credentials(ref)
    assert first and first["client_id"] and second is None and store().get_account_credentials(ref) is None


# ------------------------------------------------------------------------- README 7.2 and 9.2 views
def test_view_wallet_account_body_matches_openapi_without_secrets(osp_factory, companies, monkeypatch):
    # README 7.2, openapi WalletAccount (credentialsState, credentialsExpireAt)
    osp = osp_factory(env=ENV)
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    make_wallet(DIV, "SAP_DIV")
    create(DIV, 1)
    token = person(osp, "p1-div", DIV)
    r = osp.get(_VIEW.format(tu(1)), token)
    assert r.status_code == 200, r.text
    body = r.json()
    assert schema_errors(MODULE, "WalletAccount", body) == []
    assert (body["walletAccountRef"], body["technicalUserId"], body["companyId"]) == (acct(1)["id"], tu(1), DIV["id"])
    assert (body["provider"], body["status"], body["credentialsState"]) == ("SAP_DIV", "REQUESTED", "NONE")
    assert body["credentialsExpireAt"] is None
    cb = cb_create(osp, acct(1)["id"])
    assert cb.status_code == 204, cb.text
    body = osp.get(_VIEW.format(tu(1)), token).json()
    assert schema_errors(MODULE, "WalletAccount", body) == []
    assert (body["status"], body["credentialsState"]) == ("ACTIVE", "AVAILABLE")
    assert dt.datetime.fromisoformat(body["credentialsExpireAt"].replace("Z", "+00:00")) == clock() + dt.timedelta(days=30)
    for s in (CB_SECRET, CB_CLIENT):
        assert_no_secret(s, osp.get(_VIEW.format(tu(1)), token).text)


def test_view_wallet_account_permission_company_and_404(osp_factory, companies):
    # README 7.2 steps 1-2, 6.8
    osp = csp_account(osp_factory)
    assert osp.get(_VIEW.format(tu(1))).status_code == 401
    assert osp.get(_VIEW.format(tu(1)), person(osp, "p4", CSPC, roles=("Member",))).status_code == 403
    assert osp.get(_VIEW.format(tu(1)), person(osp, "p2", IH)).status_code == 404       # other company
    p1 = person(osp, "p1", CSPC)
    r = osp.get(_VIEW.format(tu(77)), p1)
    assert r.status_code == 404 and ptype(r) == "urn:c4-m2:problem:not-found"
    assert osp.get(_VIEW.format(tu(1)), p1).status_code == 200


def test_current_account_is_the_row_not_deleted_else_the_latest(osp_factory, companies):
    # README 7.2 step 2, 8.3 "at most one non-DELETED account per technical user", TEAM3-PLAN 12.2 `get_account`
    osp = osp_factory(env=ENV)
    make_wallet(IH, "IDENTITY_HUB")
    create(IH, 1)
    first = acct(1)["id"]
    delete(IH, 1)
    p1 = person(osp, "p1-ih", IH)
    r = osp.get(_VIEW.format(tu(1)), p1)                 # only a DELETED row: the latest
    assert r.status_code == 200 and r.json()["status"] == "DELETED" and r.json()["walletAccountRef"] == first
    # OPEN-QUESTION (module docstring): README 6.3 deletes only the credentials row, 6.7 names no state change
    assert r.json()["credentialsState"] == "AVAILABLE" and r.json()["credentialsExpireAt"] is None
    create(IH, 1)                                        # new account after DELETED
    second = acct(1)["id"]
    assert second != first and acct(1)["status"] == "ACTIVE"
    rows = store().list_accounts(statuses=None)
    assert sorted(a["status"] for a in rows if a["technical_user_id"] == tu(1)) == ["ACTIVE", "DELETED"]
    assert osp.get(_VIEW.format(tu(1)), p1).json()["walletAccountRef"] == second
    assert store().get_account_by_ref(first)["status"] == "DELETED"


def test_internal_wallet_account_query_without_company_check(osp_factory, companies):
    # README 9.2, 6.8 `query_c4_m2`; operationId getWalletAccountInternal -> `get_wallet_account_internal`
    osp = csp_account(osp_factory)
    path = f"/api/c4-m2/internal/technical-users/{tu(1)}/wallet-account"
    assert osp.get(path).status_code == 401
    assert osp.get(path, osp.service("sa-none", ["submit_wallet_callback"])).status_code == 403
    r = osp.get(path, osp.service("svc-c4-m2"))
    assert r.status_code == 200, r.text
    assert response_errors(MODULE, "GET", "/internal/technical-users/{technicalUserId}/wallet-account", 200,
                           r.json()) == []
    assert r.json()["walletAccountRef"] == acct(1)["id"] and r.json()["companyId"] == CSPC["id"]
    in_process = m2().get_wallet_account_internal(technicalUserId=tu(1))
    assert in_process == r.json() and schema_errors(MODULE, "WalletAccount", in_process) == []
    missing = osp.get(f"/api/c4-m2/internal/technical-users/{tu(55)}/wallet-account", osp.service("svc-c4-m2"))
    assert missing.status_code == 404
    with pytest.raises(Exception) as e:
        m2().get_wallet_account_internal(technicalUserId=tu(55))
    assert problems.to_problem(MODULE, e.value, True).status == 404


# ------------------------------------------------------------------ README 8.2 behaviour step 1
def test_create_existing_account_of_another_company_is_409_conflict(osp_factory, companies):
    # README 8.2 step 1 "different companyId: 409 conflict"
    osp_factory(env=ENV)
    make_wallet(DIV, "SAP_DIV")
    make_wallet(IH, "IDENTITY_HUB")
    create(DIV, 1)
    assert_problem(step_problem(m2().create_wallet_account, IH, 1), 409, "conflict")
    assert acct(1)["company_id"] == DIV["id"] and len(store().list_accounts()) == 1


def test_create_repetition_after_active_is_done_without_event_or_order(osp_factory, companies):
    # README 8.2 step 1 `ACTIVE`, 6.9
    osp = div_active(osp_factory)
    out = create(DIV, 1)
    assert_account_result(out, 1, DIV, "DONE", "SAP_DIV", "ACTIVE")
    assert len(evs(osp, "WalletAccountCreated")) == 1 and len(account_orders("account")) == 1


def test_create_repetition_while_requested_is_running_without_second_order(osp_factory, companies):
    # README 8.2 step 1 "REQUESTED with provider_ordered_at: RUNNING"
    osp = div_requested(osp_factory)
    out = create(DIV, 1)
    assert_account_result(out, 1, DIV, "RUNNING", "SAP_DIV", "REQUESTED")
    assert len(account_orders("account")) == 1 and len(store().list_accounts()) == 1


def test_create_requested_without_provider_ordered_at_orders_again(osp_factory, companies):
    # README 8.2 step 1 "REQUESTED without provider_ordered_at: continue with step 2, then step 4"
    osp = div_requested(osp_factory)
    a = acct(1)
    a["provider_ordered_at"] = None
    store().put_account(a)
    out = create(DIV, 1)
    assert out["state"] == "RUNNING"
    assert acct(1)["provider_ordered_at"] and acct(1)["id"] == a["id"] and len(store().list_accounts()) == 1
    assert [o["external_id"] for o in account_orders("account")] == [a["id"], a["id"]]


def test_create_while_deleting_is_409_invalid_state(osp_factory, companies):
    # README 8.2 step 1 `DELETING`
    osp = div_active(osp_factory)
    delete(DIV, 1)
    assert acct(1)["status"] == "DELETING"
    assert_problem(step_problem(m2().create_wallet_account, DIV, 1), 409, "invalid-state")


# ------------------------------------------------------------------ README 8.3 behaviour
def test_delete_with_foreign_wallet_account_ref_is_409_conflict(osp_factory, companies):
    # README 8.3 input: walletAccountRef not of the current account
    osp = div_active(osp_factory)
    assert_problem(step_problem(m2().delete_wallet_account, DIV, 1, walletAccountRef=str(uuid.uuid4())), 409, "conflict")
    assert acct(1)["status"] == "ACTIVE" and account_orders("account-deletion") == []


def test_delete_while_requested_is_409_invalid_state(osp_factory, companies):
    # README 8.3 preconditions
    osp = div_requested(osp_factory)
    assert_problem(step_problem(m2().delete_wallet_account, DIV, 1), 409, "invalid-state")
    assert acct(1)["status"] == "REQUESTED"


def test_delete_without_account_is_done_with_status_deleted_and_no_event(osp_factory, companies):
    # README 8.3 step 1 "No account ... DONE with status DELETED (or without walletAccountRef)"
    osp = osp_factory(env=ENV)
    make_wallet(IH, "IDENTITY_HUB")
    out = delete(IH, 5)
    assert out["state"] == "DONE" and schema_errors(MODULE, "StepResultWalletAccount", out) == []
    assert out["result"]["status"] == "DELETED" and out["result"].get("walletAccountRef") is None
    assert out["result"]["technicalUserId"] == tu(5) and out["result"]["companyId"] == IH["id"]
    assert osp.events("WalletAccountDeleted") == []
    create(IH, 6)
    delete(IH, 6)
    n_events = len(osp.events("WalletAccountDeleted"))
    again = delete(IH, 6)                                   # only a DELETED account
    assert again["state"] == "DONE" and again["result"]["status"] == "DELETED"
    assert again["result"]["walletAccountRef"] == acct(6)["id"]
    assert len(osp.events("WalletAccountDeleted")) == n_events == 1


def test_delete_for_another_company_is_409_conflict(osp_factory, companies):
    # README 8.3 step 2
    osp = osp_factory(env=ENV)
    make_wallet(IH, "IDENTITY_HUB")
    make_wallet(CSPC, "CSP")
    create(IH, 1)
    assert_problem(step_problem(m2().delete_wallet_account, CSPC, 1), 409, "conflict")
    assert acct(1)["status"] == "ACTIVE"


def test_delete_failed_account_becomes_deleted_with_event(osp_factory, companies, monkeypatch):
    # README 8.3 step 3, 6.3 `FAILED` -> `DELETED`
    # OPEN-QUESTION (module docstring): 6.9 does not say RUNNING or DONE for this case, so the step state is not asserted
    osp = osp_factory(env={**ENV, "STUB_FAILURES": f"{tu(1)}:NO_CALLBACK"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    make_wallet(DIV, "SAP_DIV")
    create(DIV, 1)
    clock.advance(minutes=61)
    service().run_timer_once()
    assert acct(1)["status"] == "FAILED"
    out = delete(DIV, 1)
    assert acct(1)["status"] == "DELETED"
    assert out["result"]["status"] == "DELETED" and schema_errors(MODULE, "StepResultWalletAccount", out) == []
    ev = evs(osp, "WalletAccountDeleted", 1)
    assert len(ev) == 1 and event_errors(MODULE, ev[0]) == []
    assert account_orders("account-deletion") == []         # nothing to delete at the provider


def test_delete_over_http_with_service_token(osp_factory, companies):
    # openapi POST /steps/delete-wallet-account (execute_steps_c4_m2)
    osp = osp_factory(env=ENV)
    make_wallet(IH, "IDENTITY_HUB")
    create(IH, 1)
    body = step_input(IH["id"], 9, technicalUserId=tu(1), walletAccountRef=acct(1)["id"])
    assert osp.post("/api/c4-m2/steps/delete-wallet-account", json=body).status_code == 401
    r = osp.post("/api/c4-m2/steps/delete-wallet-account", osp.service("svc-c4-m2"), json=body)
    assert r.status_code == 200, r.text
    assert response_errors(MODULE, "POST", "/steps/delete-wallet-account", 200, r.json()) == []
    assert r.json()["state"] == "RUNNING" and r.json()["result"]["status"] == "DELETED"


# --------------------------------------------------------------- README 7.6 callbacks for accounts
def test_callback_requires_permission_and_the_sap_div_client(osp_factory, companies):
    # README 7.6, 6.8: permission `submit_wallet_callback` and azp == SAP_DIV_CALLBACK_CLIENT_ID, else 403; no token 401
    osp = div_requested(osp_factory)
    ref = acct(1)["id"]
    assert cb_create(osp, ref, token=None).status_code == 401
    wrong_perm = osp.service("sa-div-callback", ["query_c4_m2"])
    r = cb_create(osp, ref, token=wrong_perm)
    assert r.status_code == 403 and ptype(r) == "urn:c4-m2:problem:forbidden"
    other = osp.service("sa-other-callback", ["submit_wallet_callback"])
    r = cb_create(osp, ref, token=other)
    assert r.status_code == 403 and ptype(r) == "urn:c4-m2:problem:forbidden"
    assert cb_delete(osp, ref, token=other).status_code == 403
    assert acct(1)["status"] == "REQUESTED" and creds(1) is None


def test_callback_unknown_external_id_is_404(osp_factory, companies):
    # README 7.6 create step 1 and delete step 1
    osp = div_requested(osp_factory)
    ghost = str(uuid.uuid4())
    assert cb_create(osp, ghost).status_code == 404 and cb_delete(osp, ghost).status_code == 404
    assert acct(1)["status"] == "REQUESTED"


def test_create_callback_stores_encrypted_credentials_and_activates(osp_factory, companies, monkeypatch):
    # README 7.6 create step 3, 5 `wallet_account_credentials`, 6.7, 10
    osp = osp_factory(env=ENV)
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    make_wallet(DIV, "SAP_DIV")
    create(DIV, 1)
    ref = acct(1)["id"]
    r = cb_create(osp, ref)
    assert r.status_code == 204, r.text
    a, row = acct(1), creds(1)
    assert a["status"] == "ACTIVE" and a["credentials_state"] == "AVAILABLE"
    assert row["token_url"] == SAP_AUTH + "/oauth/token" and row["client_id"] == CB_CLIENT
    assert isinstance(row["client_secret_encrypted"], bytes) and isinstance(row["nonce"], bytes)
    assert row["key_version"] == 1 and row["expires_at"] == clock() + dt.timedelta(days=30)
    assert row["client_secret_encrypted"] != CB_SECRET.encode() and plain_secret(1) == CB_SECRET
    dump = store().dump()
    assert_no_secret(CB_SECRET, dump, store().list_audit(), store().list_step_log(), [e["data"] for e in osp.events()])
    ev = evs(osp, "WalletAccountCreated", 1)
    assert len(ev) == 1 and ev[0]["data"]["walletAccountRef"] == ref and event_errors(MODULE, ev[0]) == []
    audit = [e for e in store().list_audit() if e["azp"] == "sa-div-callback"]
    # README 7.6: audit entry with azp; README 5: company_id is the caller's token claim, a service account has none
    assert audit and audit[-1]["azp"] == "sa-div-callback" and audit[-1]["sub"] == "service-account-sa-div-callback"
    assert audit[-1]["object_id"] == ref


def test_create_callback_repeated_on_active_is_204_without_change(osp_factory, companies):
    # README 7.6 create step 2 `ACTIVE`, 6.9
    osp = div_requested(osp_factory)
    ref = acct(1)["id"]
    assert cb_create(osp, ref).status_code == 204
    before = dict(creds(1))
    again = cb_create(osp, ref, secret="another-secret-value")
    assert again.status_code == 204
    assert creds(1) == before and acct(1)["status"] == "ACTIVE" and len(evs(osp, "WalletAccountCreated")) == 1
    assert len([e for e in store().list_audit() if e["azp"] == "sa-div-callback"]) >= 2   # every callback is audited


def accounts_in_other_states(osp_factory, monkeypatch):
    """SAP DIV accounts: 1 FAILED, 2 DELETING (credentials row still there), 3 DELETED."""
    osp = osp_factory(env={**ENV, "STUB_FAILURES": f"{tu(1)}:NO_CALLBACK"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    make_wallet(DIV, "SAP_DIV")
    create(DIV, 1)                                           # will FAIL
    create(DIV, 2)
    create(DIV, 3)
    providers().flush_stand_in()                             # accounts 2 and 3 become ACTIVE
    clock.advance(minutes=61)
    service().run_timer_once()
    assert (acct(1)["status"], acct(2)["status"]) == ("FAILED", "ACTIVE")
    delete(DIV, 2)                                           # DELETING (callback pending in the stand-in)
    assert acct(2)["status"] == "DELETING" and creds(2) is not None
    delete(DIV, 3)
    cb_delete(osp, acct(3)["id"])                            # DELETED
    assert acct(3)["status"] == "DELETED"
    return osp


def test_create_callback_in_other_states_is_409_invalid_state(osp_factory, companies, monkeypatch):
    # README 7.6 create step 2 `FAILED`, `DELETING`, `DELETED`; 6.3: the credentials row is deleted only on the
    # transition to DELETED, so a DELETING account keeps its row (and credentials_state) unchanged
    osp = accounts_in_other_states(osp_factory, monkeypatch)
    row2, state2 = dict(creds(2)), acct(2)["credentials_state"]
    for n, state in ((1, "FAILED"), (2, "DELETING"), (3, "DELETED")):
        r = cb_create(osp, acct(n)["id"])
        assert r.status_code == 409 and ptype(r) == "urn:c4-m2:problem:invalid-state", (n, r.text)
        assert acct(n)["status"] == state
        if state == "DELETING":
            assert creds(n) == row2 and acct(n)["credentials_state"] == state2
        else:
            assert creds(n) is None


def test_case_15_retrieval_for_failed_deleting_deleted_account_is_409_invalid_state(osp_factory, companies, monkeypatch):
    # README 7.3 step 2 "Status not ACTIVE: 409 invalid-state" (the status is checked before credentials_state)
    osp = accounts_in_other_states(osp_factory, monkeypatch)
    token = person(osp, "p1-div", DIV)
    row2 = dict(creds(2))
    for n, state in ((1, "FAILED"), (2, "DELETING"), (3, "DELETED")):
        r = retrieve(osp, token, n)
        assert r.status_code == 409 and ptype(r) == "urn:c4-m2:problem:invalid-state", (n, r.text)
        assert "clientSecret" not in r.text and acct(n)["status"] == state
    assert creds(2) == row2 and acct(2)["credentials_state"] == "AVAILABLE"       # nothing was consumed


def test_delete_callback_deletes_the_account_and_its_credentials(osp_factory, companies):
    # README 7.6 delete step 2, 6.3 "On the transition to DELETED, the row ... is deleted"
    osp = div_active(osp_factory)
    ref = acct(1)["id"]
    delete(DIV, 1)
    r = cb_delete(osp, ref)
    assert r.status_code == 204, r.text
    assert acct(1)["status"] == "DELETED" and store().get_account_credentials(ref) is None
    assert len(evs(osp, "WalletAccountDeleted", 1)) == 1
    assert any(e["azp"] == "sa-div-callback" for e in store().list_audit())
    again = cb_delete(osp, ref)                              # status DELETED: 204
    assert again.status_code == 204 and len(evs(osp, "WalletAccountDeleted", 1)) == 1


def test_delete_callback_for_an_account_that_is_not_deleting_is_409(osp_factory, companies):
    # README 7.6 delete step 1 "Status other than DELETING: 409 invalid-state"
    osp = div_active(osp_factory)
    r = cb_delete(osp, acct(1)["id"])
    assert r.status_code == 409 and ptype(r) == "urn:c4-m2:problem:invalid-state"
    assert acct(1)["status"] == "ACTIVE" and creds(1) is not None and evs(osp, "WalletAccountDeleted") == []


# --------------------------------------------------------------------------------- case 25 (accounts)
def _secret_scan(osp, caplog, secrets: list[str], client_ids: list[str]) -> None:
    # README 5: `client_id` is stored as plain text, so the table dump is scanned for client SECRETS only;
    # README 13 case 14: client IDs and secrets appear in no event, step result, step_log, audit_log or log
    dump = store().dump()
    for s in secrets:
        assert_no_secret(s, caplog.text, [e for e in osp.events()], store().list_audit(), store().list_step_log(), dump)
    for c in client_ids:
        assert_no_secret(c, caplog.text, [e for e in osp.events()], store().list_audit(), store().list_step_log())


@pytest.mark.parametrize("provider", ["SAP_DIV", "IDENTITY_HUB", "CSP"])
def test_case_25_account_secrets_appear_nowhere_in_plaintext(osp_factory, companies, caplog, provider):
    # README 13 case 25 (account accesses incl. STS secret), 6.7, 10, FRAMEWORK 4.6
    caplog.set_level("DEBUG")
    osp = osp_factory(env=ENV)
    company = {"SAP_DIV": DIV, "IDENTITY_HUB": IH, "CSP": CSPC}[provider]
    w = make_wallet(company, provider)
    outs = [create(company, 1)]
    if provider == "SAP_DIV":
        assert cb_create(osp, acct(1)["id"]).status_code == 204
    assert acct(1)["status"] == "ACTIVE"
    outs.append(delete(company, 7))                                   # a step without account
    secrets, client_ids = [plain_secret(1)], [creds(1)["client_id"]]
    if provider == "IDENTITY_HUB":
        sts = store().get_secret(w["id"], "STS_ACCESS")
        secrets.append(seam("modules.c4_m2.crypto").decrypt(sts["secret_encrypted"], sts["nonce"], sts["key_version"]))
    for s in secrets + client_ids:
        assert_no_secret(s, outs)
    _secret_scan(osp, caplog, secrets, client_ids)
    r = retrieve(osp, person(osp, "p1-any", company), 1)             # the one place that hands the secret out
    assert r.status_code == 200 and r.json()["clientSecret"] == secrets[0]
    _secret_scan(osp, caplog, secrets, client_ids)


# --------------------------------------------------------------- event contract for other teams
def test_events_for_notifications_and_c2_m3_carry_technicalUserId_companyId_walletAccountRef(osp_factory, companies,
                                                                                         monkeypatch):
    # FRAMEWORK 6 (events of wallet accounts, line ~325), C11-M1 rule R14 (reads companyId and technicalUserId),
    # C2-M3 flow apply-wallet-access (walletAccountRef), README 10 table: all four events, source urn:c4-m2
    osp = osp_factory(env={**ENV, "STUB_FAILURES": f"{tu(1)}:NO_CALLBACK,{tu(3)}:NO_DELETE_CALLBACK"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    make_wallet(DIV, "SAP_DIV")
    for n in (1, 2, 3):
        create(DIV, n)
    providers().flush_stand_in()                 # 2 and 3 ACTIVE, 1 gets no callback
    delete(DIV, 2)
    delete(DIV, 3)
    providers().flush_stand_in()                 # 2 DELETED, 3 gets no deletion callback
    clock.advance(minutes=61)
    service().run_timer_once()                   # 1 FAILED, 3 deletion failed
    expected = {"WalletAccountCreated": 2, "WalletAccountFailed": 1, "WalletAccountDeleted": 1,
                "WalletAccountDeletionFailed": 1}
    for type_, count in expected.items():
        found = osp.events(type_)
        assert len(found) == count, (type_, found)
        for e in found:
            assert e["source"] == "urn:c4-m2" and event_errors(MODULE, e) == []
            d = e["data"]
            assert d["technicalUserId"] in {tu(1), tu(2), tu(3)} and d["companyId"] == DIV["id"]
            n = [1, 2, 3][[tu(1), tu(2), tu(3)].index(d["technicalUserId"])]
            assert d["walletAccountRef"] == store().get_account(tu(n))["id"]
    assert {e["data"]["technicalUserId"] for e in osp.events("WalletAccountCreated")} == {tu(2), tu(3)}
    assert osp.events("WalletAccountFailed")[0]["data"]["reason"] == "PROVIDER_TIMEOUT"
    assert osp.events("WalletAccountDeleted")[0]["data"]["technicalUserId"] == tu(2)
    assert osp.events("WalletAccountDeletionFailed")[0]["data"]["technicalUserId"] == tu(3)


# ------------------------------------------------- README 7.2 / 7.3 / 6.8: who may see and retrieve
def test_person_with_permission_but_without_company_id_gets_404(osp_factory, companies):
    # README 7.2 step 2 / 7.3 step 1: `company_id` of the account not equal to `company_id` in the token (here: none) -> 404
    osp = csp_account(osp_factory)
    token = person(osp, "p5-admin-unbound", None, roles=("IT Admin",))      # permission yes, company binding no
    r = osp.get(_VIEW.format(tu(1)), token)
    assert r.status_code == 404 and ptype(r) == "urn:c4-m2:problem:not-found"
    r = retrieve(osp, token, 1)
    assert r.status_code == 404 and ptype(r) == "urn:c4-m2:problem:not-found"
    assert "clientSecret" not in r.text
    assert creds(1) is not None and acct(1)["credentials_state"] == "AVAILABLE"        # nothing was consumed


def test_view_permission_alone_does_not_allow_retrieving_credentials(osp_factory, companies):
    # README 6.8: credentials POST needs `retrieve_wallet_credentials`; `view_dataspace_wallet` is not enough.
    # No stock role has only the view permission, so the test adds a role to the in-memory test IAM
    # (a person token is the only kind the route accepts: scope `company`).
    osp = csp_account(osp_factory)
    iam = test_iam.iam()
    iam.portal_roles["Wallet Viewer (test)"] = {"view_dataspace_wallet"}
    try:
        token = person(osp, "p6-viewer", CSPC, roles=("Wallet Viewer (test)",))
        assert osp.get(_VIEW.format(tu(1)), token).status_code == 200            # may view
        r = retrieve(osp, token, 1)
        assert r.status_code == 403 and ptype(r) == "urn:c4-m2:problem:forbidden"
        assert creds(1) is not None and acct(1)["credentials_state"] == "AVAILABLE"
    finally:
        iam.portal_roles.pop("Wallet Viewer (test)", None)


def test_case_15_retrieval_writes_the_audit_entry_and_consumes_the_row_in_one_operation(osp_factory, companies):
    # README 7.3 step 4 (one transaction: row deleted, credentials_state RETRIEVED, audit entry with the sub), 5 audit_log
    osp = csp_account(osp_factory)
    ref = acct(1)["id"]
    token = person(osp, "p1-erika", CSPC)
    assert [e for e in store().list_audit() if e["object_id"] == ref and e["sub"] == "p1-erika"] == []
    r = retrieve(osp, token, 1)
    assert r.status_code == 200, r.text
    assert store().get_account_credentials(ref) is None and acct(1)["credentials_state"] == "RETRIEVED"
    entries = [e for e in store().list_audit() if e["object_id"] == ref and e["sub"] == "p1-erika"]
    assert len(entries) == 1, entries
    e = entries[0]
    assert e["operation"] and isinstance(e["operation"], str)
    assert e["azp"] == "portal-ui" and e["company_id"] == CSPC["id"]            # claims of the person token
    assert r.json()["clientSecret"] not in repr(e)


# -------------------------------------------------------- README 7.6 callbacks: order of checks, branches
def test_callback_checks_permission_and_client_before_looking_up_the_account(osp_factory, companies):
    # README 7.6: "otherwise 403" for permission and azp; the unknown externalId (404) comes after
    osp = div_requested(osp_factory)
    ghost = str(uuid.uuid4())
    wrong_client = osp.service("sa-other-callback", ["submit_wallet_callback"])
    wrong_perm = osp.service("sa-div-callback", ["query_c4_m2"])
    for token in (wrong_client, wrong_perm):
        assert cb_create(osp, ghost, token=token).status_code == 403
        assert cb_delete(osp, ghost, token=token).status_code == 403
    assert cb_create(osp, ghost).status_code == 404 and cb_delete(osp, ghost).status_code == 404   # right client
    assert acct(1)["status"] == "REQUESTED"


def test_delete_callback_for_an_account_that_was_never_deleted_is_409(osp_factory, companies):
    # README 7.6 delete step 1: status other than DELETING (here REQUESTED, no deletion ordered) -> 409 invalid-state
    osp = div_requested(osp_factory)
    r = cb_delete(osp, acct(1)["id"])
    assert r.status_code == 409 and ptype(r) == "urn:c4-m2:problem:invalid-state"
    assert acct(1)["status"] == "REQUESTED" and not acct(1)["deletion_ordered_at"]
    assert evs(osp, "WalletAccountDeleted") == []


def test_create_callback_on_a_retrieved_active_account_is_204_without_change(osp_factory, companies):
    # README 7.6 create step 2 `ACTIVE`: 204 without change, also after the credentials were retrieved (6.9)
    osp = div_active(osp_factory)
    ref = acct(1)["id"]
    assert retrieve(osp, person(osp, "p1-div", DIV), 1).status_code == 200
    assert acct(1)["credentials_state"] == "RETRIEVED" and creds(1) is None
    r = cb_create(osp, ref, secret="a-late-duplicate-secret")
    assert r.status_code == 204, r.text
    assert acct(1)["status"] == "ACTIVE" and acct(1)["credentials_state"] == "RETRIEVED"
    assert store().get_account_credentials(ref) is None                     # no new credentials appear
    assert len(evs(osp, "WalletAccountCreated")) == 1


# --------------------------------------------------------------- provider errors (README 8.2, 8.3, 6.9)
def test_sap_div_order_error_on_create_is_502_and_account_stays_requested(osp_factory, companies, monkeypatch):
    # README 8.2 step 4 SAP DIV + technical error: 502 upstream-error, the account stays REQUESTED without
    # provider_ordered_at; 6.9 a repetition sends the order again; 14.3 `<BPN>:ORDER_ERROR`
    osp = osp_factory(env=ENV)
    make_wallet(DIV, "SAP_DIV")
    monkeypatch.setenv("STUB_FAILURES", f"{DIV['bpn']}:ORDER_ERROR")
    assert_problem(step_problem(m2().create_wallet_account, DIV, 1), 502, "upstream-error", retryable=True)
    a = acct(1)
    assert a["status"] == "REQUESTED" and not a["provider_ordered_at"] and creds(1) is None
    assert osp.events("WalletAccountCreated") == [] and osp.events("WalletAccountFailed") == []
    monkeypatch.setenv("STUB_FAILURES", "")
    out = create(DIV, 1)
    assert out["state"] == "RUNNING" and acct(1)["id"] == a["id"] and acct(1)["provider_ordered_at"]
    assert any(o["external_id"] == a["id"] for o in account_orders("account"))
    providers().flush_stand_in()
    assert acct(1)["status"] == "ACTIVE"


def test_sap_div_order_error_on_delete_is_502_and_account_stays_deleting(osp_factory, companies, monkeypatch):
    # README 8.3 step 4 SAP DIV "Error: 502, the account stays DELETING without deletion_ordered_at"; step 5 "Without:
    # send the order again"
    osp = div_active(osp_factory)
    ref = acct(1)["id"]
    monkeypatch.setenv("STUB_FAILURES", f"{DIV['bpn']}:ORDER_ERROR")
    assert_problem(step_problem(m2().delete_wallet_account, DIV, 1), 502, "upstream-error", retryable=True)
    a = acct(1)
    assert a["status"] == "DELETING" and not a["deletion_ordered_at"]
    assert creds(1) is not None and evs(osp, "WalletAccountDeleted") == []
    before = len(account_orders("account-deletion"))
    monkeypatch.setenv("STUB_FAILURES", "")
    out = delete(DIV, 1)                                                    # repetition: the order goes out again
    assert out["state"] == "RUNNING" and out["result"]["status"] == "DELETING"
    assert acct(1)["deletion_ordered_at"]
    orders = account_orders("account-deletion")
    assert len(orders) > before and orders[-1]["external_id"] == ref
    providers().flush_stand_in()
    assert acct(1)["status"] == "DELETED" and len(evs(osp, "WalletAccountDeleted", 1)) == 1


def csp_with_http_handler(osp_factory, monkeypatch, handler):
    """Shared CSP stand-in over HTTP (as test_c4_m2_providers.py); `handler(method, url)` may answer a call itself."""
    real = phttp.request

    def request(method, url, timeout=phttp.DEFAULT_TIMEOUT, **kw):
        answer = handler(method.upper(), url)
        if isinstance(answer, Exception):
            raise answer
        return answer if answer is not None else real(method, url, timeout=timeout, **kw)

    monkeypatch.setattr(phttp, "request", request)
    osp = osp_factory(env={**ENV, "CSP_WALLET_URL": CSP_URL + "/wallet/v1", "DID_RESOLVER_URL": CSP_URL}, csp=True)
    osp.csp_register(CSPC["bpn"])
    make_wallet(CSPC, "CSP")
    create(CSPC, 1)
    assert acct(1)["status"] == "ACTIVE"
    return osp


def _is_account_delete(method: str, url: str) -> bool:
    return method == "DELETE" and "/wallet/v1/wallets/" in url and "/accounts/" in url


def test_delete_at_csp_404_counts_as_deleted(osp_factory, companies, monkeypatch):
    # README 8.3 step 4 CSP "204 or 404: status DELETED, event WalletAccountDeleted"
    osp = csp_with_http_handler(osp_factory, monkeypatch,
                                lambda m, u: httpx.Response(404) if _is_account_delete(m, u) else None)
    ref = acct(1)["id"]
    out = delete(CSPC, 1, walletAccountRef=ref)
    assert out["result"]["status"] == "DELETED" and acct(1)["status"] == "DELETED"
    assert store().get_account_credentials(ref) is None and len(evs(osp, "WalletAccountDeleted", 1)) == 1


@pytest.mark.parametrize("failure", ["http-500", "timeout"])
def test_delete_at_csp_error_is_502_and_account_stays_active(osp_factory, companies, monkeypatch, failure):
    # README 8.3 step 4 CSP "Error: 502, the account stays ACTIVE"; 12 `upstream-error` retryable
    def handler(m, u):
        if _is_account_delete(m, u):
            return httpx.ReadTimeout("timed out") if failure == "timeout" else httpx.Response(500, json={"error": "x"})
        return None

    osp = csp_with_http_handler(osp_factory, monkeypatch, handler)
    ref = acct(1)["id"]
    assert_problem(step_problem(m2().delete_wallet_account, CSPC, 1, walletAccountRef=ref), 502, "upstream-error",
                   retryable=True)
    assert acct(1)["status"] == "ACTIVE" and creds(1) is not None
    assert evs(osp, "WalletAccountDeleted") == []


# ------------------------------------------------------------------- validation, precondition order, races
BAD_INPUTS = [(f, v) for f in ("technicalUserId", "companyId") for v in (None, "not-a-uuid")]


@pytest.mark.parametrize("step", ["create_wallet_account", "delete_wallet_account"])
@pytest.mark.parametrize("field,bad", BAD_INPUTS, ids=[f"{f}-{'missing' if v is None else v}" for f, v in BAD_INPUTS])
def test_step_input_validation_is_400_validation(osp_factory, companies, step, field, bad):
    # README 12 `validation` 400 (retryable false); 8.2 / 8.3 input `technicalUserId`, `companyId` (uuid, openapi)
    osp = osp_factory(env=ENV)
    make_wallet(DIV, "SAP_DIV")
    body = step_input(DIV["id"], next(_steps), technicalUserId=tu(1))
    if bad is None:
        body.pop(field)
    else:
        body[field] = bad
    with pytest.raises(Exception) as e:
        getattr(m2(), step)(body)
    assert_problem(problems.to_problem(MODULE, e.value, True), 400, "validation")
    r = osp.post("/api/c4-m2/steps/" + step.replace("_", "-"), osp.service("svc-c4-m2"), json=body)
    assert r.status_code == 400 and ptype(r) == "urn:c4-m2:problem:validation", r.text    # never 422
    assert store().list_accounts() == [] and account_orders() == []


def test_create_with_wallet_not_active_and_company_inactive_reports_wallet_not_active(osp_factory, companies):
    # README 8.2 Preconditions: the wallet is listed first ("... ACTIVE, otherwise 409 wallet-not-active. The company
    # is ACTIVE ..., otherwise 409 company-not-active"), so wallet-not-active wins when both fail
    osp = osp_factory(env=ENV)
    m2().create_wallet(step_input(INA["id"], 1, provider="SAP_DIV"))        # REQUESTED (callback held), company INACTIVE
    assert store().get_wallet(INA["id"])["status"] == "REQUESTED"
    assert_problem(step_problem(m2().create_wallet_account, INA, 1), 409, "wallet-not-active")   # README 8.2
    assert acct(1) is None and account_orders() == []


def test_delete_with_foreign_ref_on_a_requested_account_reports_invalid_state_first(osp_factory, companies):
    # README 8.3: preconditions (no account REQUESTED) are checked before the walletAccountRef conflict.
    # OPEN-QUESTION (module docstring): the Input paragraph, which names the conflict, comes first in the README text.
    osp = div_requested(osp_factory)
    p = step_problem(m2().delete_wallet_account, DIV, 1, walletAccountRef=str(uuid.uuid4()))
    assert_problem(p, 409, "invalid-state")
    assert acct(1)["status"] == "REQUESTED" and account_orders("account-deletion") == []


def test_concurrent_create_calls_for_one_technical_user_make_one_account(osp_factory, companies):
    # README 6.9: advisory lock per technical user; "at most one row with a status other than DELETED" (README 5)
    osp = osp_factory(env=ENV)
    make_wallet(IH, "IDENTITY_HUB")
    barrier = threading.Barrier(2)

    def call(n: int):
        barrier.wait(timeout=10)
        return m2().create_wallet_account(step_input(IH["id"], 500 + n, technicalUserId=tu(1)))

    with ThreadPoolExecutor(2) as pool:
        outs = [f.result(timeout=30) for f in [pool.submit(call, 1), pool.submit(call, 2)]]
    rows = [a for a in store().list_accounts(statuses=None) if a["technical_user_id"] == tu(1)]
    assert len(rows) == 1 and rows[0]["status"] == "ACTIVE"
    assert sorted(o["state"] for o in outs) == ["DONE", "RUNNING"]          # the second call saw the finished object (6.9)
    assert len(evs(osp, "WalletAccountCreated", 1)) == 1
    assert {o["result"]["walletAccountRef"] for o in outs} == {rows[0]["id"]}
