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
"""C4-M1 `issue-credentials` (README 8.1, 6.1, 6.2, 6.3, acceptance cases 1 to 5, 17, 18), route STUB.

Seams (TEAM3-PLAN 12.3): `interface.store()`, `service.flush_timers()`, `service.now`, `routes.stub_orders()`.
They are imported lazily, so a missing seam fails the single test that needs it.
"""
from __future__ import annotations

import datetime as dt
import threading
import uuid

import httpx
import pytest
from test_c4_m2_common import (
    COMPANIES,
    Clock,
    companies,  # noqa: F401 - fixture
    event_errors,
    osp_factory,  # noqa: F401 - fixture
    response_errors,
    seam,
    step_input,
    wallet_fake,  # noqa: F401 - fixture
)

from portal_common import http as phttp
from portal_common import tokens

U1 = COMPANIES["u1"]["id"]
U1_BPN = "BPNLIUK2REMLK3F4"
STEP = "/api/c4-m1/steps/issue-credentials"
TYPES = ["BPN", "MEMBERSHIP"]


# ------------------------------------------------------------------------------------------ helpers
def cid(key: str) -> str:
    return COMPANIES[key]["id"]


def issue(osp, company_id: str, n: int = 1, **extra):
    """HTTP step with the service account of Process Orchestration (`svc-c4-m1` has execute_steps_c4_m1)."""
    return osp.post(STEP, osp.service("svc-c4-m1"), json=step_input(company_id, n, **extra))


def store():
    return seam("modules.c4_m1.interface").store()


def status_of(company_id: str, ctype: str) -> str | None:
    row = store().get_credential(company_id, ctype)
    return row["status"] if row else None


def row_of(company_id: str, ctype: str) -> dict:
    row = store().get_credential(company_id, ctype)
    assert row is not None, f"no credential row for {ctype}"
    return row


def history(company_id: str, ctype: str) -> list[tuple[str, int]]:
    row = row_of(company_id, ctype)
    return [(h["status"], h["attempt"]) for h in store().list_history(row["id"])]


def orders() -> list[dict]:
    return seam("modules.c4_m1.routes").stub_orders()


def flush() -> None:
    seam("modules.c4_m1.service").flush_timers()


def assert_problem(r, status: int, name: str, retryable: bool | None = None) -> dict:
    assert r.status_code == status, r.text
    body = r.json()
    assert body["type"] == f"urn:c4-m1:problem:{name}", body
    if retryable is not None:
        assert body["retryable"] is retryable, body
    return body


def ts(minutes: int = 0) -> dt.datetime:
    """Store rows hold tz-aware datetimes (TEAM3-PLAN 12.3: `service.now() -> datetime`)."""
    return dt.datetime(2026, 11, 6, 9, 0, tzinfo=dt.UTC) + dt.timedelta(minutes=minutes)


def put_row(company_key: str, ctype: str, status: str, attempt: int = 1, **fields) -> dict:
    """A credential row with the spec keys (README 5 `credential`), written through the store."""
    c = COMPANIES[company_key]
    now = ts(0)
    row = {"id": str(uuid.uuid4()), "company_id": c["id"], "credential_type": ctype, "status": status,
           "route": "STUB", "issuer_did": None, "wallet_provider": "STUB", "bpn": c["bpn"].upper(),
           "holder_did": f"did:web:wallet.example.org:{c['bpn']}", "request_ref": f"stub-{attempt}",
           "attempt": attempt, "requested_at": now, "issued_at": None, "failed_at": None, "revoked_at": None,
           "failure_reason": None, "revocation_reason": None, "created_at": now, "changed_at": now}
    row.update(fields)
    store().put_credential(row)
    return row


def no_rows_created(company_id: str) -> None:
    assert store().list_credentials(company_id=company_id) == []


# ------------------------------------------------------------------------------------------ case 1
def test_case_01_issue_creates_two_requested_rows_and_orders(osp_factory, companies, wallet_fake):
    # README 13 case 1, 8.1 step 2 and 5: a fresh order answers RUNNING, rows REQUESTED, attempt 1
    osp = osp_factory()
    r = issue(osp, U1)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "RUNNING"
    assert body["stepRunId"] == step_input(U1)["stepRunId"]
    assert response_errors("c4-m1", "post", "/steps/issue-credentials", 200, body) == []
    # README 8.1 Result: companyId, per credential type credentialType and status
    assert body["result"]["companyId"] == U1
    assert sorted((c["credentialType"], c["status"]) for c in body["result"]["credentials"]) == [
        ("BPN", "REQUESTED"), ("MEMBERSHIP", "REQUESTED")]
    for t in TYPES:
        row = row_of(U1, t)
        assert row["status"] == "REQUESTED"
        assert row["attempt"] == 1
        assert row["request_ref"] == "stub-1"                       # README 11.6
        assert row["route"] == "STUB"
        assert row["bpn"] == U1_BPN                                 # README 5: upper case
        assert row["company_id"] == U1 and row["credential_type"] == t
        assert row["holder_did"] == f"did:web:wallet.example.org:{U1_BPN}"
        assert row["wallet_provider"] == "STUB"
        assert not row["issuer_did"]                                # README 5: empty for CREDENTIAL_ISSUER and STUB
        assert row["requested_at"] and not row["issued_at"]
        assert history(U1, t) == [("REQUESTED", 1)]                 # README 6.1: every change writes history
    # README 11.6: the order remembers (company, credential type, BPN); both types ordered at the same time
    assert sorted(orders(), key=lambda o: o["credential_type"]) == [
        {"company_id": U1, "credential_type": "BPN", "bpn": U1_BPN, "attempt": 1},
        {"company_id": U1, "credential_type": "MEMBERSHIP", "bpn": U1_BPN, "attempt": 1}]
    run = store().get_run(U1)
    assert run["status"] == "RUNNING"                               # README 5 issuance_run
    assert run["credential_types"] == TYPES
    assert run["process_id"] == step_input(U1)["processId"]
    assert run["step_run_id"] == step_input(U1)["stepRunId"]
    assert osp.events("CredentialsIssued") == []                    # nothing issued before the report


def test_case_01_flush_timers_issues_both_and_publishes_one_event(osp_factory, companies, wallet_fake):
    # README 13 case 1: after STUB_ISSUER_DELAY_SECONDS both ISSUED, exactly one CredentialsIssued, round DONE
    osp = osp_factory()
    assert issue(osp, U1).status_code == 200
    flush()
    for t in TYPES:
        row = row_of(U1, t)
        assert row["status"] == "ISSUED"
        assert row["issued_at"] and row["attempt"] == 1
        assert history(U1, t) == [("REQUESTED", 1), ("ISSUED", 1)]
    evs = osp.events("CredentialsIssued")
    assert len(evs) == 1                                            # README 6.2: exactly one, at the change to DONE
    assert event_errors("c4-m1", evs[0]) == []
    assert evs[0]["source"] == "urn:c4-m1"
    assert evs[0]["data"]["companyId"] == U1
    assert evs[0]["data"]["credentialTypes"] == TYPES               # the types of the round
    run = store().get_run(U1)
    assert run["status"] == "DONE" and run["finished_at"]
    assert osp.events("CredentialIssuanceFailed") == []


def test_case_01_stub_issuer_delay_zero_still_answers_running(osp_factory, companies, wallet_fake):
    # README 8.1 step 5: a fresh order always answers RUNNING (DONE only if everything was already ISSUED)
    osp = osp_factory({"STUB_ISSUER_DELAY_SECONDS": "0"})
    body = issue(osp, U1).json()
    assert body["state"] == "RUNNING"


def test_case_01_subset_of_types_orders_only_these(osp_factory, companies, wallet_fake):
    # README 8.1 Input: credentialTypes is a subset; the round contains only these types (6.2)
    osp = osp_factory()
    assert issue(osp, U1, credentialTypes=["BPN"]).status_code == 200
    assert [o["credential_type"] for o in orders()] == ["BPN"]
    assert store().get_credential(U1, "MEMBERSHIP") is None
    flush()
    evs = osp.events("CredentialsIssued")
    assert len(evs) == 1 and evs[0]["data"]["credentialTypes"] == ["BPN"]


def test_case_01_onboarding_types_come_from_config(osp_factory, companies, wallet_fake):
    # README 8.1 Input: without credentialTypes the default is ONBOARDING_CREDENTIAL_TYPES
    osp = osp_factory({"ONBOARDING_CREDENTIAL_TYPES": "MEMBERSHIP"})
    assert issue(osp, U1).status_code == 200
    assert [o["credential_type"] for o in orders()] == ["MEMBERSHIP"]
    assert store().get_run(U1)["credential_types"] == ["MEMBERSHIP"]


@pytest.mark.parametrize("types", [["FOO"], [], ["BPN", "BPN"]])
def test_case_01_invalid_credential_types_are_validation_errors(osp_factory, companies, wallet_fake, types):
    # README 12 `validation` 400, retryable false; openapi StepIssueCredentials: minItems 1, unique, enum
    osp = osp_factory()
    assert_problem(issue(osp, U1, credentialTypes=types), 400, "validation", retryable=False)
    no_rows_created(U1)


def test_case_01_route_stub_for_csp_mode_with_empty_issuer_url(osp_factory, companies, wallet_fake):
    # README 6.3 rule 3 / 11.6: ISSUER_MODE=CSP with empty CSP_ISSUER_URL is STUB, also for HOLDER_REQUESTS (U5)
    osp = osp_factory({"ISSUER_MODE": "CSP", "CSP_ISSUER_URL": ""})
    r = issue(osp, cid("u5"))
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "RUNNING"
    assert row_of(cid("u5"), "BPN")["route"] == "STUB"
    assert row_of(cid("u5"), "BPN")["wallet_provider"] == "IDENTITY_HUB"
    assert wallet_fake.holder_access_calls == []                    # README 8.1: not fetched for STUB


def test_case_01_route_stub_for_own_mode_with_empty_routes(osp_factory, companies, wallet_fake):
    # README 6.3 rule 2: OWN with empty ISSUER_ROUTES is STUB (OSP A at the hackathon), also for SAP_DIV (U4)
    osp = osp_factory({"ISSUER_MODE": "OWN", "ISSUER_ROUTES": ""})
    r = issue(osp, cid("u4"))
    assert r.status_code == 200, r.text
    assert row_of(cid("u4"), "MEMBERSHIP")["route"] == "STUB"
    assert wallet_fake.holder_access_calls == []


# ------------------------------------------------------------------------------------------ case 2
def test_case_02_repeat_after_issued_is_done_without_order_or_event(osp_factory, companies, wallet_fake):
    # README 13 case 2, 8.1 step 5: all ISSUED -> DONE, no order, no event
    osp = osp_factory()
    issue(osp, U1, 1)
    flush()
    assert len(orders()) == 2 and len(osp.events("CredentialsIssued")) == 1
    r = issue(osp, U1, 2)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "DONE"
    assert body["stepRunId"] == step_input(U1, 2)["stepRunId"]
    assert sorted((c["credentialType"], c["status"]) for c in body["result"]["credentials"]) == [
        ("BPN", "ISSUED"), ("MEMBERSHIP", "ISSUED")]
    assert len(orders()) == 2                                       # no order
    assert len(osp.events("CredentialsIssued")) == 1                # no event
    assert row_of(U1, "BPN")["attempt"] == 1
    assert history(U1, "BPN") == [("REQUESTED", 1), ("ISSUED", 1)]  # no history either
    assert store().get_run(U1)["status"] == "DONE"
    flush()                                                         # nothing pending that could add an event
    assert len(osp.events("CredentialsIssued")) == 1


# ------------------------------------------------------------------------------------------ case 3
def test_case_03_repeat_while_requested_is_running_without_second_order(osp_factory, companies, wallet_fake):
    # README 13 case 3, 8.1 step 2: REQUESTED younger than RESEND_AFTER_HOURS waits for the report
    osp = osp_factory()
    issue(osp, U1, 1)
    r = issue(osp, U1, 2)
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "RUNNING"
    assert r.json()["stepRunId"] == step_input(U1, 2)["stepRunId"]
    assert len(orders()) == 2
    assert [row_of(U1, t)["attempt"] for t in TYPES] == [1, 1]
    assert history(U1, "BPN") == [("REQUESTED", 1)]
    assert store().get_run(U1)["step_run_id"] == step_input(U1, 2)["stepRunId"]   # README 5: last run of the step


def test_case_03_young_requested_row_is_not_resent_before_the_resend_age(osp_factory, companies, wallet_fake,
                                                                         monkeypatch):
    # README 8.1 step 2: "younger than RESEND_AFTER_HOURS: nothing"; 23 h < 24 h
    osp = osp_factory()
    clock = Clock().install(monkeypatch, "modules.c4_m1.service")
    issue(osp, U1, 1)
    clock.advance(hours=23)
    assert issue(osp, U1, 2).json()["state"] == "RUNNING"
    assert len(orders()) == 2


def test_case_03_old_requested_row_is_resent_after_the_resend_age(osp_factory, companies, wallet_fake, monkeypatch):
    # README 8.1 step 2: "REQUESTED and older: send the order again, attempt + 1"; 25 h > 24 h
    osp = osp_factory()
    clock = Clock().install(monkeypatch, "modules.c4_m1.service")
    issue(osp, U1, 1)
    clock.advance(hours=25)
    r = issue(osp, U1, 2)
    assert r.json()["state"] == "RUNNING"
    assert len(orders()) == 4
    assert [row_of(U1, t)["attempt"] for t in TYPES] == [2, 2]
    assert [row_of(U1, t)["request_ref"] for t in TYPES] == ["stub-2", "stub-2"]
    # OPEN-QUESTION: README 6.1 lists no REQUESTED -> REQUESTED transition, yet "every change writes a row to
    # credential_history" and 8.1 step 2 sends the order again with attempt + 1. Reading (ours): a resend is a
    # change of the row and writes a history entry (REQUESTED, 2).
    assert history(U1, "BPN") == [("REQUESTED", 1), ("REQUESTED", 2)]


def test_case_03_resend_after_zero_hours_orders_again_with_attempt_two(osp_factory, companies, wallet_fake):
    # README 13 case 3: with RESEND_AFTER_HOURS = 0 a repetition sends a new order, attempt 2
    osp = osp_factory({"RESEND_AFTER_HOURS": "0"})
    issue(osp, U1, 1)
    r = issue(osp, U1, 2)
    assert r.json()["state"] == "RUNNING"
    assert len(orders()) == 4
    assert [(o["credential_type"], o["attempt"]) for o in orders()[2:]] == [("BPN", 2), ("MEMBERSHIP", 2)]
    for t in TYPES:
        row = row_of(U1, t)
        assert row["status"] == "REQUESTED" and row["attempt"] == 2 and row["request_ref"] == "stub-2"
    assert osp.events("CredentialsIssued") == []


# ------------------------------------------------------------------------------------------ case 4
def test_case_04_failing_type_fails_the_round_and_publishes_one_failure(osp_factory, companies, wallet_fake):
    # README 13 case 4, 6.2: BPN ISSUED, MEMBERSHIP FAILED, one CredentialIssuanceFailed, no CredentialsIssued
    osp = osp_factory({"STUB_ISSUER_FAIL_TYPES": "MEMBERSHIP"})
    issue(osp, U1)
    flush()
    assert status_of(U1, "BPN") == "ISSUED"
    membership = row_of(U1, "MEMBERSHIP")
    assert membership["status"] == "FAILED"
    assert membership["failure_reason"] == "Issuance declined by the stand-in"   # README 11.6
    assert membership["failed_at"]
    assert history(U1, "MEMBERSHIP") == [("REQUESTED", 1), ("FAILED", 1)]
    failed = osp.events("CredentialIssuanceFailed")
    assert len(failed) == 1
    assert event_errors("c4-m1", failed[0]) == []
    assert failed[0]["data"] == {"companyId": U1, "credentialType": "MEMBERSHIP",
                                 "reason": "Issuance declined by the stand-in"}   # README 10, max 200 chars
    assert len(failed[0]["data"]["reason"]) <= 200
    assert osp.events("CredentialsIssued") == []
    assert store().get_run(U1)["status"] == "FAILED"


def test_case_04_rerun_orders_only_the_failed_type_and_then_completes(osp_factory, companies, wallet_fake,
                                                                      monkeypatch):
    # README 13 case 4: empty the fail list, run again: only MEMBERSHIP is triggered; then CredentialsIssued
    osp = osp_factory({"STUB_ISSUER_FAIL_TYPES": "MEMBERSHIP"})
    issue(osp, U1, 1)
    flush()
    monkeypatch.setenv("STUB_ISSUER_FAIL_TYPES", "")                # the spec's own wording: empty the list
    before = len(orders())
    r = issue(osp, U1, 2)
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "RUNNING"
    assert orders()[before:] == [{"company_id": U1, "credential_type": "MEMBERSHIP", "bpn": U1_BPN, "attempt": 2}]
    assert row_of(U1, "BPN")["attempt"] == 1 and row_of(U1, "BPN")["status"] == "ISSUED"
    assert row_of(U1, "MEMBERSHIP")["status"] == "REQUESTED" and row_of(U1, "MEMBERSHIP")["attempt"] == 2
    assert store().get_run(U1)["status"] == "RUNNING"               # README 8.1 step 4: set to RUNNING again
    assert osp.events("CredentialsIssued") == []
    flush()
    assert status_of(U1, "MEMBERSHIP") == "ISSUED"
    evs = osp.events("CredentialsIssued")
    assert len(evs) == 1
    assert evs[0]["data"] == {"companyId": U1, "credentialTypes": TYPES}
    assert store().get_run(U1)["status"] == "DONE"
    assert len(osp.events("CredentialIssuanceFailed")) == 1         # still only the first failure
    assert history(U1, "MEMBERSHIP") == [("REQUESTED", 1), ("FAILED", 1), ("REQUESTED", 2), ("ISSUED", 2)]


def test_case_04_fail_types_apply_to_every_listed_type(osp_factory, companies, wallet_fake):
    # README 11.6: UNSUCCESSFUL for the types in STUB_ISSUER_FAIL_TYPES; both failing = two failure events
    osp = osp_factory({"STUB_ISSUER_FAIL_TYPES": "BPN,MEMBERSHIP"})
    issue(osp, U1)
    flush()
    assert [status_of(U1, t) for t in TYPES] == ["FAILED", "FAILED"]
    assert sorted(e["data"]["credentialType"] for e in osp.events("CredentialIssuanceFailed")) == TYPES
    assert osp.events("CredentialsIssued") == []
    assert store().get_run(U1)["status"] == "FAILED"


# ------------------------------------------------------------------------------------------ case 5
def test_case_05_company_without_bpn_is_not_ready(osp_factory, companies, wallet_fake):
    # README 13 case 5, 8.1 Preconditions: U2 without BPN -> 409 company-not-ready, retryable false, no row
    osp = osp_factory()
    assert_problem(issue(osp, cid("u2")), 409, "company-not-ready", retryable=False)
    no_rows_created(cid("u2"))


def test_case_05_wallet_not_active_is_wallet_not_ready(osp_factory, companies, wallet_fake):
    # README 13 case 5: U3 with a wallet that is not ACTIVE -> 409 wallet-not-ready, retryable false, no row
    osp = osp_factory()
    assert_problem(issue(osp, cid("u3")), 409, "wallet-not-ready", retryable=False)
    no_rows_created(cid("u3"))


@pytest.mark.parametrize("change", [
    {"status": "VALIDATING"}, {"status": "FAILED"}, {"did": None}, {"did": ""}])
def test_case_05_wallet_not_ready_variants(osp_factory, companies, wallet_fake, change):
    # README 8.1 Preconditions C4-M2: wallet ACTIVE with a DID, otherwise wallet-not-ready
    osp = osp_factory()
    wallet_fake.set("u1", **change)
    assert_problem(issue(osp, U1), 409, "wallet-not-ready", retryable=False)
    no_rows_created(U1)


def test_case_05_missing_wallet_is_wallet_not_ready(osp_factory, companies, wallet_fake):
    # OPEN-QUESTION: README 8.1 is silent about a company without any wallet (neighbour answers None);
    # TEAM3-PLAN 11 (C4-M1 #3) reads it as wallet-not-ready.
    osp = osp_factory()
    wallet_fake.remove("u1")
    assert_problem(issue(osp, U1), 409, "wallet-not-ready", retryable=False)
    no_rows_created(U1)


def test_case_05_bring_your_own_wallet_has_no_issuer_route(osp_factory, companies, wallet_fake):
    # README 13 case 5, 6.3 "own wallet has no route in 0.2": 409 no-issuer-route, retryable false, no row
    # OPEN-QUESTION: README 6.3 rule 2 (OWN + empty ISSUER_ROUTES => STUB) contradicts case 5 (BRING_YOUR_OWN =>
    # 409 no-issuer-route) for this default configuration. Case 5 wins: the issuance mode CREDENTIAL_OFFER is
    # rejected BEFORE rule 2 is applied (6.3 last paragraph: "an own wallet has no route in version 0.2").
    osp = osp_factory()
    assert_problem(issue(osp, cid("u7_byo")), 409, "no-issuer-route", retryable=False)
    no_rows_created(cid("u7_byo"))
    assert orders() == []


def test_case_05_bring_your_own_wallet_has_no_route_with_a_configured_issuer_routes(osp_factory, companies,
                                                                                    wallet_fake):
    # README 6.3 last paragraph: with a non-empty ISSUER_ROUTES there is no entry for BRING_YOUR_OWN either
    # (rule 2: provider without entry -> 409 no-issuer-route); same answer as in the default configuration
    osp = osp_factory({"ISSUER_ROUTES": "SAP_DIV:CREDENTIAL_ISSUER,IDENTITY_HUB:ISSUER_SERVICE,CSP:ISSUER_SERVICE"})
    assert_problem(issue(osp, cid("u7_byo")), 409, "no-issuer-route", retryable=False)
    no_rows_created(cid("u7_byo"))
    assert orders() == [] and wallet_fake.holder_access_calls == []


def test_case_05_unknown_company_is_not_ready(osp_factory, companies, wallet_fake):
    # OPEN-QUESTION: README 8.1 is silent about an unknown company (C3-M1 answers 404, neighbour gives None);
    # TEAM3-PLAN 11 (C4-M1 #3) reads it as company-not-ready.
    osp = osp_factory()
    companies.remove(U1)
    assert_problem(issue(osp, U1), 409, "company-not-ready", retryable=False)
    no_rows_created(U1)


def test_case_05_company_is_checked_before_the_wallet(osp_factory, companies, wallet_fake):
    # README 8.1 Preconditions order: company first. U2 has no wallet at all but is reported as company-not-ready.
    osp = osp_factory()
    assert wallet_fake.wallets.get(cid("u2")) is None
    assert_problem(issue(osp, cid("u2")), 409, "company-not-ready", retryable=False)


def test_case_05_wallet_is_checked_before_the_route(osp_factory, companies, wallet_fake):
    # README 8.1 Preconditions order: wallet before route. A BYO wallet that is not ACTIVE is wallet-not-ready.
    # OPEN-QUESTION: see test_case_05_bring_your_own_wallet_has_no_issuer_route (CREDENTIAL_OFFER rejected before rule 2).
    osp = osp_factory()
    wallet_fake.set("u7_byo", status="REQUESTED")
    assert_problem(issue(osp, cid("u7_byo")), 409, "wallet-not-ready", retryable=False)


def test_case_05_rejected_company_is_not_ready(osp_factory, companies, wallet_fake):
    # README 12 company-not-ready: "not REQUESTED/ACTIVE"; REJECTED qualifies
    osp = osp_factory()
    companies.set_status(U1, "REJECTED")
    assert_problem(issue(osp, U1), 409, "company-not-ready", retryable=False)
    no_rows_created(U1)


def test_case_05_no_order_is_sent_when_a_precondition_fails(osp_factory, companies, wallet_fake):
    # README 8.1 step 1: preconditions are checked before anything is ordered
    osp = osp_factory()
    for key in ("u2", "u3", "u7_byo"):
        issue(osp, cid(key))
    assert orders() == []
    assert osp.events("CredentialsIssued") == [] and osp.events("CredentialIssuanceFailed") == []


# ------------------------------------------------------------------------------------------ case 17
def test_case_17_reactivation_orders_only_membership(osp_factory, companies, wallet_fake):
    # README 13 case 17, 6.2 last bullet, 8.1: after case 9 (BPN ISSUED, MEMBERSHIP REVOKED) and U1 ACTIVE
    osp = osp_factory()
    issue(osp, U1, 1)
    flush()
    revoke = osp.post("/api/c4-m1/steps/revoke-credentials", osp.service("svc-c4-m1"),
                      json=step_input(U1, 2, reason="COMPANY_DEACTIVATED"))
    assert revoke.status_code == 200, revoke.text
    assert [status_of(U1, t) for t in TYPES] == ["ISSUED", "REVOKED"]
    companies.set_status(U1, "ACTIVE")
    before = len(orders())
    r = issue(osp, U1, 3, credentialTypes=["MEMBERSHIP"])
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "RUNNING"
    assert orders()[before:] == [{"company_id": U1, "credential_type": "MEMBERSHIP", "bpn": U1_BPN, "attempt": 2}]
    membership = row_of(U1, "MEMBERSHIP")
    assert membership["status"] == "REQUESTED" and membership["attempt"] == 2
    assert membership["revocation_reason"] in (None, "COMPANY_DEACTIVATED")
    bpn_before = dict(row_of(U1, "BPN"))
    flush()
    evs = osp.events("CredentialsIssued")
    assert len(evs) == 2                                            # onboarding round and reactivation round
    assert evs[-1]["data"] == {"companyId": U1, "credentialTypes": ["MEMBERSHIP"]}
    assert status_of(U1, "MEMBERSHIP") == "ISSUED"
    assert row_of(U1, "BPN") == bpn_before                          # BPN unchanged: attempt 1, ISSUED
    assert row_of(U1, "BPN")["attempt"] == 1 and row_of(U1, "BPN")["status"] == "ISSUED"
    assert store().get_run(U1)["credential_types"] == ["MEMBERSHIP"]
    assert store().get_run(U1)["status"] == "DONE"
    assert history(U1, "MEMBERSHIP") == [("REQUESTED", 1), ("ISSUED", 1), ("REVOKED", 1),
                                         ("REQUESTED", 2), ("ISSUED", 2)]


def test_case_17_reactivation_with_active_company_status_is_accepted(osp_factory, companies, wallet_fake):
    # README 8.1 Preconditions: ACTIVE (reactivation) is as good as REQUESTED (onboarding)
    osp = osp_factory()
    companies.set_status(U1, "ACTIVE")
    assert issue(osp, U1, credentialTypes=["MEMBERSHIP"]).json()["state"] == "RUNNING"
    assert [o["credential_type"] for o in orders()] == ["MEMBERSHIP"]


def test_case_17_cancelled_and_failed_rows_are_ordered_again(osp_factory, companies, wallet_fake):
    # README 6.1 first row / 8.1 step 2: FAILED, CANCELLED, REVOKED -> REQUESTED with attempt + 1
    osp = osp_factory()
    put_row("u1", "BPN", "ISSUED", 1, issued_at=ts(1))
    put_row("u1", "MEMBERSHIP", "CANCELLED", 3)
    r = issue(osp, U1)
    assert r.json()["state"] == "RUNNING"
    assert orders() == [{"company_id": U1, "credential_type": "MEMBERSHIP", "bpn": U1_BPN, "attempt": 4}]


# ------------------------------------------------------------------------------------------ case 18
def test_case_18_inactive_company_gets_no_credentials(osp_factory, companies, wallet_fake):
    # README 13 case 18, 8.1 Preconditions "a deactivated company gets no credentials"
    osp = osp_factory()
    companies.set_status(cid("u5"), "INACTIVE")
    assert_problem(issue(osp, cid("u5")), 409, "company-not-ready", retryable=False)
    no_rows_created(cid("u5"))
    assert orders() == []


# ------------------------------------------------------------------------------------ README 8.1 step 5
@pytest.mark.parametrize("run_status", ["FAILED", None])
def test_readme_8_1_step_5_all_issued_with_failed_or_missing_run_is_done_without_event(
        osp_factory, companies, wallet_fake, run_status):
    # README 8.1 step 5: "All types ISSUED: DONE, without an event (there already was one, or the types were
    # issued before)". The run row is FAILED (late reports issued everything) or missing altogether.
    osp = osp_factory()
    for t in TYPES:
        put_row("u1", t, "ISSUED", 1, issued_at=ts(1))
    if run_status:
        store().put_run({"company_id": U1, "credential_types": TYPES, "status": run_status,
                         "process_id": step_input(U1)["processId"], "step_run_id": step_input(U1)["stepRunId"],
                         "started_at": ts(0), "finished_at": ts(2)})
    r = issue(osp, U1, 5)
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "DONE"
    assert store().get_run(U1)["status"] == "DONE"
    assert osp.events("CredentialsIssued") == [] and osp.events("CredentialIssuanceFailed") == []
    assert orders() == []
    assert [row_of(U1, t)["attempt"] for t in TYPES] == [1, 1]


def test_readme_8_1_note_reactivation_without_credential_types_names_both_types(osp_factory, companies, wallet_fake):
    # README 8.1 Input note: "Without it, the result would be the same, because the issued BPN credential is not
    # triggered again; but CredentialsIssued would then name both types." Documented behaviour, not a recommendation.
    osp = osp_factory()
    put_row("u1", "BPN", "ISSUED", 1, issued_at=ts(1))
    put_row("u1", "MEMBERSHIP", "REVOKED", 1, issued_at=ts(1), revoked_at=ts(3), revocation_reason="COMPANY_DEACTIVATED")
    companies.set_status(U1, "ACTIVE")
    assert issue(osp, U1).json()["state"] == "RUNNING"
    assert orders() == [{"company_id": U1, "credential_type": "MEMBERSHIP", "bpn": U1_BPN, "attempt": 2}]
    assert row_of(U1, "BPN")["attempt"] == 1 and status_of(U1, "BPN") == "ISSUED"
    assert store().get_run(U1)["credential_types"] == TYPES
    flush()
    evs = osp.events("CredentialsIssued")
    assert len(evs) == 1 and evs[0]["data"] == {"companyId": U1, "credentialTypes": TYPES}


# --------------------------------------------------------------------------- README 11.1, 11.2, 12, 8.1
def test_readme_11_1_company_query_failing_is_502_upstream_error_retryable(osp_factory, companies, wallet_fake,
                                                                           monkeypatch):
    # README 11.1 / 12: C3-M1 did not respond as expected (not a 404) -> 502 upstream-error, retryable true
    osp = osp_factory()

    def broken(**_kw):
        raise RuntimeError("C3-M1 is down")

    monkeypatch.setattr("modules.c3_m1.interface.query_company", broken)
    assert_problem(issue(osp, U1), 502, "upstream-error", retryable=True)
    no_rows_created(U1)
    assert orders() == []


def test_readme_11_2_wallet_query_failing_is_502_upstream_error_retryable(osp_factory, companies, wallet_fake,
                                                                          monkeypatch):
    # README 11.2 / 12: C4-M2 did not respond as expected (not a 404) -> 502 upstream-error, retryable true
    osp = osp_factory()

    def broken(**_kw):
        raise RuntimeError("C4-M2 is down")

    monkeypatch.setattr("modules.c4_m2.interface.get_wallet_info", broken)
    assert_problem(issue(osp, U1), 502, "upstream-error", retryable=True)
    no_rows_created(U1)
    assert orders() == []


@pytest.mark.parametrize("company_id", ["not-a-uuid", "12345", ""])
def test_readme_8_1_company_id_must_be_a_uuid(osp_factory, companies, wallet_fake, company_id):
    # README 8.1 Input companyId; openapi format uuid -> 400 validation (README 12), retryable false
    osp = osp_factory()
    assert_problem(issue(osp, company_id), 400, "validation", retryable=False)
    assert orders() == []


def test_readme_8_1_credential_issuer_route_needs_the_did_document_location(osp_factory, companies, wallet_fake,
                                                                            monkeypatch):
    # README 8.1 Preconditions C4-M2: "for the route CREDENTIAL_ISSUER also with the location of the DID document.
    # Otherwise 409 wallet-not-ready" - before any call (no holder access, no call to the issuer), no row
    calls: list[str] = []

    def record(method, url, *a, **kw):
        calls.append(url)
        return httpx.Response(200, json={"access_token": "t", "expires_in": 300}, request=httpx.Request(method, url))

    osp = osp_factory({"ISSUER_MODE": "OWN", "ISSUER_ROUTES": "SAP_DIV:CREDENTIAL_ISSUER",
                       "CREDENTIAL_ISSUER_URL": "http://cred-issuer.test",
                       "CREDENTIAL_ISSUER_TOKEN_URL": "http://cred-issuer.test/token",
                       "CREDENTIAL_ISSUER_CLIENT_ID": "m1", "CREDENTIAL_ISSUER_CLIENT_SECRET": "s",
                       "CALLBACK_BASE_URL": "http://osp.test"})
    tokens._load_jwks()   # load the IAM signing keys before the fake replaces portal_common.http.request
    monkeypatch.setattr(phttp, "request", record)
    wallet_fake.set("u4", didDocumentLocation=None)
    assert_problem(issue(osp, cid("u4")), 409, "wallet-not-ready", retryable=False)
    no_rows_created(cid("u4"))
    assert wallet_fake.holder_access_calls == []
    assert [u for u in calls if u.startswith("http://cred-issuer.test")] == []


# ------------------------------------------------------------------------------ README 12.3: interface.reset
def test_interface_reset_cancels_pending_stub_timers_and_empties_the_store(osp_factory, companies, wallet_fake):
    # TEAM3-PLAN 12.3: `interface.reset()` clears the store, cancels pending STUB timers, clears the routes state
    osp = osp_factory()
    issue(osp, U1)
    assert len(orders()) == 2                                       # two timers are pending
    seam("modules.c4_m1.interface").reset()
    flush()                                                         # nothing is left to fire
    assert store().list_credentials() == [] and store().get_run(U1) is None
    assert orders() == []
    assert osp.events("CredentialsIssued") == [] and osp.events("CredentialIssuanceFailed") == []


# ------------------------------------------------------------------------------------ README 8.1 step 2
def test_readme_8_1_revocation_pending_blocks_issuing_before_anything_is_sent(osp_factory, companies, wallet_fake):
    # README 8.1 step 2: REVOCATION_PENDING -> 409 invalid-state "before anything is sent"
    osp = osp_factory()
    put_row("u1", "BPN", "FAILED", 1, failure_reason="x")           # would be ordered again, but must not be
    put_row("u1", "MEMBERSHIP", "REVOCATION_PENDING", 1, revocation_reason="COMPANY_DEACTIVATED")
    assert_problem(issue(osp, U1), 409, "invalid-state", retryable=False)
    assert orders() == []
    assert status_of(U1, "BPN") == "FAILED" and row_of(U1, "BPN")["attempt"] == 1
    assert status_of(U1, "MEMBERSHIP") == "REVOCATION_PENDING"
    assert osp.events("CredentialsIssued") == []


# ----------------------------------------------------------------------------------------- README 6.6
def test_readme_6_6_concurrent_calls_for_one_company_produce_one_order_set(osp_factory, companies, wallet_fake):
    # README 6.6 / 8.1 step 1: steps for the same company run one after the other (advisory lock)
    osp = osp_factory()
    interface = seam("modules.c4_m1.interface")
    barrier = threading.Barrier(4)
    results: list[dict] = []
    errors: list[BaseException] = []

    def call(n: int) -> None:
        try:
            barrier.wait(timeout=10)
            results.append(interface.issue_credentials(step_input(U1, n + 1)))
        except BaseException as e:  # noqa: BLE001 - reported below
            errors.append(e)

    threads = [threading.Thread(target=call, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert errors == []
    assert [r["state"] for r in results] == ["RUNNING"] * 4
    assert len(orders()) == 2                                       # one order per type, not four
    assert [row_of(U1, t)["attempt"] for t in TYPES] == [1, 1]
    assert history(U1, "BPN") == [("REQUESTED", 1)]
    flush()
    assert len(osp.events("CredentialsIssued")) == 1


# --------------------------------------------------------------------------------------------- auth
def test_issue_step_needs_the_step_permission(osp_factory, companies, wallet_fake):
    # README 6.5: /steps needs execute_steps_c4_m1 (403 forbidden); no token 401
    osp = osp_factory()
    r = osp.post(STEP, json=step_input(U1))
    assert_problem(r, 401, "unauthorized")
    token = osp.service("sa-credential-issuer")                      # only report_credential_status
    assert_problem(osp.post(STEP, token, json=step_input(U1)), 403, "forbidden")
    no_rows_created(U1)
