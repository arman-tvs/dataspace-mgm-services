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
"""C4-M1 status reports of issuers: `POST /api/c4-m1/issuer-callbacks/{credentialKind}`
(README 7.4 table, 6.1, 6.2, 5 `audit_entry`, acceptance cases 6 and 7).

Rows are brought into their state with the step `issue-credentials` (route STUB, delay 5 s so the timers stay
pending), with reports over HTTP, or with `store().put_credential(...)` (README 5 keys, TEAM3-PLAN 12.3).
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from test_c4_m2_common import (
    COMPANIES,
    companies,  # noqa: F401 - fixture
    event_errors,
    osp_factory,  # noqa: F401 - fixture
    seam,
    step_input,
    wallet_fake,  # noqa: F401 - fixture
)

from portal_common import http as phttp

U1 = COMPANIES["u1"]["id"]
U4 = COMPANIES["u4"]["id"]
U1_BPN = "BPNLIUK2REMLK3F4"
U4_BPN = "BPNL0000000000U4"
TYPES = ["BPN", "MEMBERSHIP"]
STEP = "/api/c4-m1/steps/issue-credentials"
SERVICE_ACCOUNT = "sa-credential-issuer"


# ------------------------------------------------------------------------------------------ helpers
def store():
    return seam("modules.c4_m1.interface").store()


def row_of(company_id: str, ctype: str) -> dict:
    row = store().get_credential(company_id, ctype)
    assert row is not None, f"no credential row for {ctype}"
    return row


def status_of(company_id: str, ctype: str) -> str:
    return row_of(company_id, ctype)["status"]


def history(company_id: str, ctype: str) -> list[tuple[str, int]]:
    return [(h["status"], h["attempt"]) for h in store().list_history(row_of(company_id, ctype)["id"])]


def start_round(osp, company_id: str = U1, n: int = 1, **extra) -> None:
    """Issue step with the pending STUB timers: both rows REQUESTED, round RUNNING."""
    r = osp.post(STEP, osp.service("svc-c4-m1"), json=step_input(company_id, n, **extra))
    assert r.status_code == 200 and r.json()["state"] == "RUNNING", r.text


def report(osp, kind: str, bpn: str, status: str = "SUCCESSFUL", message: str | None = None, token=None, body=None):
    payload = body if body is not None else {"bpn": bpn, "status": status}
    if message is not None and body is None:
        payload["message"] = message
    token = token if token is not None else osp.service(SERVICE_ACCOUNT)
    return osp.post(f"/api/c4-m1/issuer-callbacks/{kind}", token, json=payload)


def assert_problem(r, status: int, name: str) -> dict:
    assert r.status_code == status, r.text
    body = r.json()
    assert body["type"] == f"urn:c4-m1:problem:{name}", body
    return body


def assert_204(r) -> None:
    assert r.status_code == 204, r.text
    assert r.content == b""                                          # README 7.4 step 5: no body


def ts(minutes: int = 0) -> dt.datetime:
    """Store rows hold tz-aware datetimes (TEAM3-PLAN 12.3: `service.now() -> datetime`)."""
    return dt.datetime(2026, 11, 6, 9, 0, tzinfo=dt.UTC) + dt.timedelta(minutes=minutes)


def put_row(company_key: str, ctype: str, status: str, attempt: int = 1, **fields) -> dict:
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


def snapshot(company_id: str, ctype: str) -> dict:
    return dict(row_of(company_id, ctype))


# ----------------------------------------------------------------------------- 7.4 REQUESTED rows
def test_case_06_successful_report_issues_the_row_and_answers_204_without_body(osp_factory, companies, wallet_fake):
    # README 13 case 6, 7.4: REQUESTED + SUCCESSFUL -> ISSUED, response 204 (no body)
    osp = osp_factory()
    start_round(osp)
    r = report(osp, "bpn", U1_BPN, "SUCCESSFUL", "credential handed to the wallet")
    assert_204(r)
    row = row_of(U1, "BPN")
    assert row["status"] == "ISSUED" and row["issued_at"] and row["attempt"] == 1
    assert status_of(U1, "MEMBERSHIP") == "REQUESTED"               # the other type is untouched
    assert history(U1, "BPN") == [("REQUESTED", 1), ("ISSUED", 1)]   # README 6.1: every change has history
    assert osp.events("CredentialsIssued") == []                    # round not complete yet (6.2)
    assert store().get_run(U1)["status"] == "RUNNING"


def test_case_06_last_successful_report_completes_the_round_with_one_event(osp_factory, companies, wallet_fake):
    # README 6.2: round DONE as soon as all types are ISSUED; exactly one CredentialsIssued with the round's types
    osp = osp_factory()
    start_round(osp)
    assert_204(report(osp, "bpn", U1_BPN))
    assert_204(report(osp, "membership", U1_BPN))
    evs = osp.events("CredentialsIssued")
    assert len(evs) == 1
    assert event_errors("c4-m1", evs[0]) == []
    assert evs[0]["data"] == {"companyId": U1, "credentialTypes": TYPES}
    run = store().get_run(U1)
    assert run["status"] == "DONE" and run["finished_at"]


def test_case_06_event_names_only_the_types_of_the_round(osp_factory, companies, wallet_fake):
    # README 6.2 / 8.1: CredentialsIssued carries the types of the round, not all rows
    osp = osp_factory()
    put_row("u1", "BPN", "ISSUED", 1, issued_at=ts(1))
    start_round(osp, credentialTypes=["MEMBERSHIP"])
    assert_204(report(osp, "membership", U1_BPN))
    evs = osp.events("CredentialsIssued")
    assert [e["data"]["credentialTypes"] for e in evs] == [["MEMBERSHIP"]]


def test_case_06_audit_entry_has_sub_azp_operation_object_and_result(osp_factory, companies, wallet_fake):
    # README 13 case 6, 7.4 step 5, 5 audit_entry: sub, client_id (= azp), company_id, operation, object_ref, result
    osp = osp_factory()
    start_round(osp)
    assert_204(report(osp, "membership", U1_BPN))
    audit = store().list_audit()
    assert len(audit) == 1
    e = audit[0]
    assert e["operation"] == "REPORT_CREDENTIAL_STATUS"
    assert e["client_id"] == SERVICE_ACCOUNT                         # azp of the service account
    assert e["sub"] == f"service-account-{SERVICE_ACCOUNT}"          # tools/test_iam.py client_token
    assert U1_BPN in e["object_ref"] and "MEMBERSHIP" in e["object_ref"]   # README 5: BPN and credential type
    assert e["result"] == "204"                                      # README 5: HTTP status as text
    # OPEN-QUESTION: README 5 `result` = "HTTP status of the response" and 7.4 step 5 (audit entry) comes after the
    # row handling, so a 404/409 callback could imply an entry with result 404/409 too. The tests assert audit
    # entries only for 204 reports (and none for a 403); what is written for 404/409 is left to the implementation.
    assert e["id"] and e["occurred_at"]
    # OPEN-QUESTION: README 5 says `company_id` is "from the token, if present"; a service-account token has
    # none, so None is expected; the company of the credential is accepted too.
    assert e["company_id"] in (None, U1)


def test_case_06_every_report_writes_one_audit_entry_also_duplicates(osp_factory, companies, wallet_fake):
    # README 7.4 step 5 / 5: one entry per report over HTTP
    osp = osp_factory()
    start_round(osp)
    assert_204(report(osp, "bpn", U1_BPN))
    assert_204(report(osp, "bpn", U1_BPN))
    audit = store().list_audit()
    assert [(a["operation"], a["result"]) for a in audit] == [("REPORT_CREDENTIAL_STATUS", "204")] * 2


def test_case_06_duplicate_successful_report_changes_nothing_and_emits_nothing(osp_factory, companies, wallet_fake):
    # README 13 case 6 / 7.4: ISSUED + SUCCESSFUL -> nothing (duplicate report), 204, no event
    osp = osp_factory()
    start_round(osp)
    assert_204(report(osp, "bpn", U1_BPN))
    assert_204(report(osp, "membership", U1_BPN))
    before = (snapshot(U1, "BPN"), snapshot(U1, "MEMBERSHIP"), len(osp.events()))
    assert_204(report(osp, "membership", U1_BPN))
    assert_204(report(osp, "bpn", U1_BPN))
    assert (snapshot(U1, "BPN"), snapshot(U1, "MEMBERSHIP"), len(osp.events())) == before
    assert len(osp.events("CredentialsIssued")) == 1
    assert history(U1, "MEMBERSHIP") == [("REQUESTED", 1), ("ISSUED", 1)]


def test_readme_7_4_unsuccessful_report_fails_the_row_the_round_and_publishes_one_event(
        osp_factory, companies, wallet_fake):
    # README 7.4: REQUESTED + UNSUCCESSFUL -> FAILED with message; CredentialIssuanceFailed; round FAILED
    osp = osp_factory()
    start_round(osp)
    assert_204(report(osp, "membership", U1_BPN.lower(), "UNSUCCESSFUL", "wallet refused the request"))
    row = row_of(U1, "MEMBERSHIP")
    assert row["status"] == "FAILED" and row["failure_reason"] == "wallet refused the request"
    assert row["failed_at"]
    assert history(U1, "MEMBERSHIP") == [("REQUESTED", 1), ("FAILED", 1)]
    assert status_of(U1, "BPN") == "REQUESTED"
    evs = osp.events("CredentialIssuanceFailed")
    assert len(evs) == 1
    assert event_errors("c4-m1", evs[0]) == []
    assert evs[0]["data"] == {"companyId": U1, "credentialType": "MEMBERSHIP", "reason": "wallet refused the request"}
    assert osp.events("CredentialsIssued") == []
    assert store().get_run(U1)["status"] == "FAILED"


def test_readme_7_4_one_failure_event_per_failed_type(osp_factory, companies, wallet_fake):
    # README 6.2 / 10: a CredentialIssuanceFailed for each type that fails
    osp = osp_factory()
    start_round(osp)
    assert_204(report(osp, "bpn", U1_BPN, "UNSUCCESSFUL", "no"))
    assert_204(report(osp, "membership", U1_BPN, "UNSUCCESSFUL", "no"))
    assert sorted(e["data"]["credentialType"] for e in osp.events("CredentialIssuanceFailed")) == TYPES
    assert store().get_run(U1)["status"] == "FAILED"


def test_readme_7_4_message_is_truncated_to_1000_in_the_row_and_200_in_the_event(osp_factory, companies, wallet_fake):
    # README 7.4 last paragraph: stored truncated to 1000; README 10: event reason truncated to 200
    osp = osp_factory()
    start_round(osp)
    message = "".join(chr(ord("a") + i % 26) for i in range(1500))
    assert_204(report(osp, "membership", U1_BPN, "UNSUCCESSFUL", message))
    assert row_of(U1, "MEMBERSHIP")["failure_reason"] == message[:1000]
    ev = osp.events("CredentialIssuanceFailed")[0]
    assert ev["data"]["reason"] == message[:200]
    assert event_errors("c4-m1", ev) == []
    assert all(len(h["note"] or "") <= 1000 for h in store().list_history(row_of(U1, "MEMBERSHIP")["id"]))


# --------------------------------------------------------------------------------- 7.4 other rows
def test_case_07_unsuccessful_after_issued_is_invalid_state(osp_factory, companies, wallet_fake):
    # README 13 case 7 / 7.4: ISSUED + UNSUCCESSFUL -> 409 invalid-state, nothing changes
    osp = osp_factory()
    start_round(osp)
    assert_204(report(osp, "bpn", U1_BPN))
    before = (snapshot(U1, "BPN"), len(osp.events()))
    assert_problem(report(osp, "bpn", U1_BPN, "UNSUCCESSFUL", "too late"), 409, "invalid-state")
    assert (snapshot(U1, "BPN"), len(osp.events())) == before


def test_case_07_late_success_after_failed_completes_the_round(osp_factory, companies, wallet_fake):
    # README 13 case 7, 6.2: FAILED + SUCCESSFUL -> ISSUED; a later success of all types still ends in DONE
    osp = osp_factory()
    start_round(osp)
    assert_204(report(osp, "bpn", U1_BPN, "UNSUCCESSFUL", "first try failed"))
    assert_204(report(osp, "membership", U1_BPN))
    assert osp.events("CredentialsIssued") == []
    assert store().get_run(U1)["status"] == "FAILED"
    assert_204(report(osp, "bpn", U1_BPN, "SUCCESSFUL", "late report"))
    row = row_of(U1, "BPN")
    assert row["status"] == "ISSUED" and row["issued_at"] and row["attempt"] == 1
    assert history(U1, "BPN") == [("REQUESTED", 1), ("FAILED", 1), ("ISSUED", 1)]
    evs = osp.events("CredentialsIssued")
    assert len(evs) == 1
    assert evs[0]["data"] == {"companyId": U1, "credentialTypes": TYPES}
    assert store().get_run(U1)["status"] == "DONE"
    assert len(osp.events("CredentialIssuanceFailed")) == 1


def test_case_07_late_success_after_failed_without_complete_round_has_no_event(osp_factory, companies, wallet_fake):
    # README 7.4: FAILED + SUCCESSFUL -> ISSUED, "check the round": the other type is still REQUESTED
    osp = osp_factory()
    start_round(osp)
    assert_204(report(osp, "bpn", U1_BPN, "UNSUCCESSFUL", "x"))
    assert_204(report(osp, "bpn", U1_BPN, "SUCCESSFUL"))
    assert status_of(U1, "BPN") == "ISSUED"
    assert osp.events("CredentialsIssued") == []


def test_readme_7_4_unsuccessful_after_failed_does_nothing(osp_factory, companies, wallet_fake):
    # README 7.4: FAILED + UNSUCCESSFUL -> nothing (204, no second event, reason stays)
    osp = osp_factory()
    start_round(osp)
    assert_204(report(osp, "bpn", U1_BPN, "UNSUCCESSFUL", "first reason"))
    before = (snapshot(U1, "BPN"), len(osp.events()))
    assert_204(report(osp, "bpn", U1_BPN, "UNSUCCESSFUL", "second reason"))
    assert (snapshot(U1, "BPN"), len(osp.events())) == before
    assert row_of(U1, "BPN")["failure_reason"] == "first reason"


@pytest.mark.parametrize("status", ["REVOCATION_PENDING", "REVOKED"])
@pytest.mark.parametrize("report_status", ["SUCCESSFUL", "UNSUCCESSFUL"])
def test_readme_7_4_revocation_pending_and_revoked_rows_ignore_reports(osp_factory, companies, wallet_fake,
                                                                       status, report_status):
    # README 7.4: REVOCATION_PENDING, REVOKED -> nothing, for both statuses (204)
    osp = osp_factory()
    put_row("u1", "MEMBERSHIP", status, 1, revocation_reason="COMPANY_DEACTIVATED")
    before = (snapshot(U1, "MEMBERSHIP"), len(osp.events()))
    assert_204(report(osp, "membership", U1_BPN, report_status, "ignored"))
    assert (snapshot(U1, "MEMBERSHIP"), len(osp.events())) == before


def test_readme_7_4_cancelled_row_with_successful_report_is_revoked_at_once(osp_factory, companies, wallet_fake):
    # README 7.4 / 6.1 last row: CANCELLED + SUCCESSFUL -> revoked immediately: REVOKED + CredentialRevoked
    osp = osp_factory()
    put_row("u1", "BPN", "ISSUED", 1, issued_at=ts(1))                # the other type of the round is ISSUED ...
    put_row("u1", "MEMBERSHIP", "CANCELLED", 1, revocation_reason="COMPANY_DEACTIVATED")
    store().put_run({"company_id": U1, "credential_types": TYPES, "status": "CANCELLED",   # ... the round CANCELLED
                     "process_id": None, "step_run_id": None, "started_at": ts(0), "finished_at": ts(2)})
    assert_204(report(osp, "membership", U1_BPN))
    row = row_of(U1, "MEMBERSHIP")
    assert row["status"] == "REVOKED" and row["revoked_at"]
    assert row["revocation_reason"] == "COMPANY_DEACTIVATED"
    assert history(U1, "MEMBERSHIP")[-1] == ("REVOKED", 1)
    evs = osp.events("CredentialRevoked")
    assert len(evs) == 1
    assert event_errors("c4-m1", evs[0]) == []
    assert evs[0]["data"] == {"companyId": U1, "credentialType": "MEMBERSHIP",
                              "revocationReason": "COMPANY_DEACTIVATED"}
    assert osp.events("CredentialsIssued") == []                    # a late report must not complete a CANCELLED round
    assert store().get_run(U1)["status"] == "CANCELLED"
    assert_204(report(osp, "membership", U1_BPN))                   # the second identical report: nothing
    assert len(osp.events("CredentialRevoked")) == 1


def test_readme_7_4_cancelled_row_on_a_route_that_cannot_revoke_becomes_revocation_pending(
        osp_factory, companies, wallet_fake):
    # README 7.4 table (CANCELLED + SUCCESSFUL) / 6.1 last row: "revoked immediately: REVOKED or REVOCATION_PENDING";
    # route CREDENTIAL_ISSUER cannot revoke (6.3) -> REVOCATION_PENDING, and no CredentialRevoked (only with REVOKED)
    osp = osp_factory()
    put_row("u4", "MEMBERSHIP", "CANCELLED", 1, route="CREDENTIAL_ISSUER", wallet_provider="SAP_DIV", request_ref="",
            revocation_reason="COMPANY_DEACTIVATED")
    assert_204(report(osp, "membership", U4_BPN))
    row = row_of(U4, "MEMBERSHIP")
    assert row["status"] == "REVOCATION_PENDING" and not row["revoked_at"]
    assert history(U4, "MEMBERSHIP")[-1] == ("REVOCATION_PENDING", 1)
    assert osp.events("CredentialRevoked") == [] and osp.events("CredentialsIssued") == []
    assert_204(report(osp, "membership", U4_BPN))                   # a second report: nothing
    assert row_of(U4, "MEMBERSHIP")["status"] == "REVOCATION_PENDING"


def test_readme_7_4_cancelled_row_with_unsuccessful_report_does_nothing(osp_factory, companies, wallet_fake):
    # README 7.4: CANCELLED + UNSUCCESSFUL -> nothing
    osp = osp_factory()
    put_row("u1", "MEMBERSHIP", "CANCELLED", 1, revocation_reason="OTHER")
    before = (snapshot(U1, "MEMBERSHIP"), len(osp.events()))
    assert_204(report(osp, "membership", U1_BPN, "UNSUCCESSFUL", "x"))
    assert (snapshot(U1, "MEMBERSHIP"), len(osp.events())) == before


def test_readme_7_4_technical_revocation_failure_answers_502_and_keeps_cancelled(osp_factory, companies,
                                                                                 wallet_fake):
    # README 7.4: if the revocation fails technically the credential stays CANCELLED and the response is 502,
    # so that the sender reports again. OPEN-QUESTION: TEAM3-PLAN 12.3 has no seam to make a STUB revoke fail,
    # so the row is on route CSP_ISSUER (README 11.5) and the CSP issuer API answers 503 to the DELETE.
    down = FastAPI()

    @down.api_route("/{path:path}", methods=["GET", "PUT", "POST", "DELETE"])
    async def always_503(request: Request, path: str):
        return JSONResponse({"type": "about:blank", "title": "down", "status": 503}, status_code=503)

    osp = osp_factory({"ISSUER_MODE": "CSP", "CSP_ISSUER_URL": "http://csp-issuer-down.test/issuer/v1"}, csp=True)
    phttp.register_local("http://csp-issuer-down.test", down)
    put_row("u1", "MEMBERSHIP", "CANCELLED", 1, route="CSP_ISSUER", issuer_did="did:web:issuer.csp.example.org",
            wallet_provider="CSP", revocation_reason="COMPANY_DEACTIVATED")
    before = snapshot(U1, "MEMBERSHIP")
    r = report(osp, "membership", U1_BPN)
    assert_problem(r, 502, "upstream-error")
    assert snapshot(U1, "MEMBERSHIP") == before
    assert row_of(U1, "MEMBERSHIP")["status"] == "CANCELLED"
    assert osp.events("CredentialRevoked") == []


# ---------------------------------------------------------------------------------- errors and lookup
def test_case_06_unknown_bpn_is_unknown_request(osp_factory, companies, wallet_fake):
    # README 13 case 6 / 7.4 step 3: no row -> 404 unknown-request
    osp = osp_factory()
    start_round(osp)
    assert_problem(report(osp, "bpn", "BPNL000000000000"), 404, "unknown-request")


def test_readme_7_4_lookup_is_per_bpn_and_credential_type(osp_factory, companies, wallet_fake):
    # README 7.4 step 3: (BPN upper case, type); a row of the other type does not match -> unknown-request
    osp = osp_factory()
    put_row("u1", "BPN", "REQUESTED", 1)
    assert_problem(report(osp, "membership", U1_BPN), 404, "unknown-request")
    assert status_of(U1, "BPN") == "REQUESTED"
    assert_204(report(osp, "bpn", U1_BPN))


def test_readme_7_4_unknown_request_for_company_without_any_order(osp_factory, companies, wallet_fake):
    # README 7.4 step 3: nothing ordered yet at all -> unknown-request, no row is created by a report
    osp = osp_factory()
    assert_problem(report(osp, "bpn", U1_BPN), 404, "unknown-request")
    assert store().list_credentials(company_id=U1) == []


def test_case_06_unknown_credential_kind_is_not_found(osp_factory, companies, wallet_fake):
    # README 13 case 6 / 7.4 step 2: kind `foo` -> 404 not-found (not unknown-request)
    osp = osp_factory()
    start_round(osp)
    assert_problem(report(osp, "foo", U1_BPN), 404, "not-found")


@pytest.mark.parametrize("bpn", ["BPNX0000000000U1", "BPNL12345", "BPNL0000000000U1X", "BPNL000000000-U1",
                                 "", "0000BPNL0000000U1", None, 12345])
def test_readme_7_4_invalid_bpn_is_a_validation_error(osp_factory, companies, wallet_fake, bpn):
    # README 7.4 step 2: bpn must be BPNL + 12 letters or digits, else 400 validation
    osp = osp_factory()
    start_round(osp)
    body = {"status": "SUCCESSFUL"} if bpn is None else {"bpn": bpn, "status": "SUCCESSFUL"}
    assert_problem(report(osp, "bpn", "", body=body), 400, "validation")
    assert status_of(U1, "BPN") == "REQUESTED"


@pytest.mark.parametrize("status", ["DONE", "successful", "", None, 1])
def test_readme_7_4_invalid_status_is_a_validation_error(osp_factory, companies, wallet_fake, status):
    # README 7.4 step 2: status must be SUCCESSFUL or UNSUCCESSFUL, else 400 validation
    osp = osp_factory()
    start_round(osp)
    body = {"bpn": U1_BPN} if status is None else {"bpn": U1_BPN, "status": status}
    assert_problem(report(osp, "bpn", "", body=body), 400, "validation")
    assert status_of(U1, "BPN") == "REQUESTED"


def test_readme_7_4_validation_comes_before_the_row_lookup(osp_factory, companies, wallet_fake):
    # README 7.4 steps 2 before 3: an invalid bpn is 400 validation even though no row exists
    osp = osp_factory()
    assert_problem(report(osp, "bpn", "NOT-A-BPN"), 400, "validation")


def test_readme_7_4_kind_is_checked_before_the_body(osp_factory, companies, wallet_fake):
    # README 7.4 step 2: unknown kind -> 404 not-found even with an invalid body
    osp = osp_factory()
    assert_problem(report(osp, "foo", "x", body={"bpn": "x", "status": "?"}), 404, "not-found")


def test_case_06_report_without_token_is_unauthorized(osp_factory, companies, wallet_fake):
    # README 7.4 step 1: no token -> 401
    osp = osp_factory()
    start_round(osp)
    r = osp.post("/api/c4-m1/issuer-callbacks/bpn", json={"bpn": U1_BPN, "status": "SUCCESSFUL"})
    assert_problem(r, 401, "unauthorized")
    assert status_of(U1, "BPN") == "REQUESTED"


def test_case_06_unknown_kind_without_token_is_unauthorized_first(osp_factory, companies, wallet_fake):
    # README 7.4 step 1 before step 2: token missing and kind `foo` -> 401, not 404
    osp = osp_factory()
    r = osp.post("/api/c4-m1/issuer-callbacks/foo", json={"bpn": U1_BPN, "status": "SUCCESSFUL"})
    assert_problem(r, 401, "unauthorized")
    assert store().list_audit() == []


def test_case_06_report_without_permission_is_forbidden(osp_factory, companies, wallet_fake):
    # README 13 case 6 / 6.5: token without report_credential_status -> 403 forbidden, nothing changes
    osp = osp_factory()
    start_round(osp)
    token = osp.service("sa-query-only", ["query_c4_m1"])
    assert_problem(report(osp, "bpn", U1_BPN, token=token), 403, "forbidden")
    assert status_of(U1, "BPN") == "REQUESTED"
    assert store().list_audit() == []


def test_readme_7_4_permission_is_checked_before_kind_and_body(osp_factory, companies, wallet_fake):
    # README 7.4 step 1 before step 2: no permission and kind `foo` -> 403, not 404
    osp = osp_factory()
    token = osp.service("sa-query-only", ["query_c4_m1"])
    assert_problem(report(osp, "foo", "x", token=token, body={"bpn": "x"}), 403, "forbidden")


def test_readme_6_5_step_account_cannot_report(osp_factory, companies, wallet_fake):
    # README 6.5: only issuer service accounts report; the step account svc-c4-m1 has no such permission
    osp = osp_factory()
    start_round(osp)
    assert_problem(report(osp, "bpn", U1_BPN, token=osp.service("svc-c4-m1")), 403, "forbidden")


# ------------------------------------------------------------------------------ BPN matching, two companies
def test_readme_7_4_bpn_is_matched_case_insensitively(osp_factory, companies, wallet_fake):
    # README 7.4 step 2/3: format check is case-insensitive, the lookup uses the upper-case BPN
    osp = osp_factory()
    start_round(osp)
    assert_204(report(osp, "bpn", U1_BPN.lower()))
    assert status_of(U1, "BPN") == "ISSUED"
    assert_204(report(osp, "membership", "bpnL" + U1_BPN[4:].lower()))
    assert status_of(U1, "MEMBERSHIP") == "ISSUED"


def test_readme_7_4_report_reaches_the_right_company_when_two_companies_have_rows(osp_factory, companies,
                                                                                   wallet_fake):
    # README 7.4: the report is assigned by BPN and credential type; U1 and U4 both have REQUESTED rows
    osp = osp_factory()
    start_round(osp, U1, 1)
    start_round(osp, U4, 2)
    assert_204(report(osp, "bpn", U4_BPN.lower()))
    assert [status_of(U4, t) for t in TYPES] == ["ISSUED", "REQUESTED"]
    assert [status_of(U1, t) for t in TYPES] == ["REQUESTED", "REQUESTED"]
    assert_204(report(osp, "membership", U4_BPN))
    evs = osp.events("CredentialsIssued")
    assert [e["data"]["companyId"] for e in evs] == [U4]
    assert store().get_run(U1)["status"] == "RUNNING"
    assert store().get_run(U4)["status"] == "DONE"
    assert_204(report(osp, "bpn", U1_BPN, "UNSUCCESSFUL", "only U1 fails"))
    assert status_of(U1, "BPN") == "FAILED" and status_of(U4, "BPN") == "ISSUED"
    assert [e["data"]["companyId"] for e in osp.events("CredentialIssuanceFailed")] == [U1]
