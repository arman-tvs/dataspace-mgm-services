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
"""C4-M1 `revoke-credentials` (README 8.2, 6.1, 6.2, acceptance cases 9 and 10), route STUB.

`confirm-revocation` is not tested here. Seams (TEAM3-PLAN 12.3): `interface.store()`, `service.flush_timers()`,
`routes.stub_orders()`; imported lazily so that a missing seam fails the single test that needs it.
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from test_c4_m2_common import (
    COMPANIES,
    companies,  # noqa: F401 - fixture
    event_errors,
    osp_factory,  # noqa: F401 - fixture
    response_errors,
    seam,
    step_input,
    wallet_fake,  # noqa: F401 - fixture
)

U1 = COMPANIES["u1"]["id"]
U1_BPN = "BPNLIUK2REMLK3F4"
TYPES = ["BPN", "MEMBERSHIP"]
ISSUE = "/api/c4-m1/steps/issue-credentials"
REVOKE = "/api/c4-m1/steps/revoke-credentials"


# ------------------------------------------------------------------------------------------ helpers
def store():
    return seam("modules.c4_m1.interface").store()


def flush() -> None:
    seam("modules.c4_m1.service").flush_timers()


def orders() -> list[dict]:
    return seam("modules.c4_m1.routes").stub_orders()


def row_of(company_id: str, ctype: str) -> dict:
    row = store().get_credential(company_id, ctype)
    assert row is not None, f"no credential row for {ctype}"
    return row


def status_of(company_id: str, ctype: str) -> str:
    return row_of(company_id, ctype)["status"]


def history(company_id: str, ctype: str) -> list[tuple[str, int]]:
    return [(h["status"], h["attempt"]) for h in store().list_history(row_of(company_id, ctype)["id"])]


def snapshot(company_id: str, ctype: str) -> dict:
    return dict(row_of(company_id, ctype))


def issue(osp, n: int = 1):
    r = osp.post(ISSUE, osp.service("svc-c4-m1"), json=step_input(U1, n))
    assert r.status_code == 200 and r.json()["state"] == "RUNNING", r.text
    return r


def issue_all(osp, n: int = 1) -> None:
    """Both credentials ISSUED (round DONE, one CredentialsIssued)."""
    issue(osp, n)
    flush()
    assert [status_of(U1, t) for t in TYPES] == ["ISSUED", "ISSUED"]


def revoke(osp, company_id: str = U1, n: int = 90, reason: str | None = "COMPANY_DEACTIVATED", **extra):
    body = step_input(company_id, n, **extra)
    if reason is not None:
        body["reason"] = reason
    return osp.post(REVOKE, osp.service("svc-c4-m1"), json=body)


def done(r) -> dict:
    """200 DONE with a result that validates against openapi StepResultRevocation."""
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "DONE"                                   # README 8.2 Result
    assert response_errors("c4-m1", "post", "/steps/revoke-credentials", 200, body) == []
    return body["result"]


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


def issued_rows() -> None:
    """Both rows ISSUED, written through the store (no timers needed)."""
    for t in TYPES:
        put_row("u1", t, "ISSUED", 1, issued_at=ts(1))


def revoked_events(osp) -> list[dict]:
    return osp.events("CredentialRevoked")


# ------------------------------------------------------------------------------------------ case 9
def test_case_09_revoke_membership_by_default_keeps_the_bpn_credential(osp_factory, companies, wallet_fake):
    # README 13 case 9, 8.2: default ["MEMBERSHIP"]: REVOKED, one CredentialRevoked, BPN stays ISSUED
    osp = osp_factory()
    issue_all(osp)
    bpn_before = snapshot(U1, "BPN")
    result = done(revoke(osp))
    assert result["companyId"] == U1
    assert result["revoked"] == ["MEMBERSHIP"]
    assert result["cancelled"] == []
    assert result["manualRevocation"] == []                          # STUB can revoke (11.6)
    membership = row_of(U1, "MEMBERSHIP")
    assert membership["status"] == "REVOKED" and membership["revoked_at"]
    assert membership["revocation_reason"] == "COMPANY_DEACTIVATED"
    assert membership["attempt"] == 1
    assert history(U1, "MEMBERSHIP") == [("REQUESTED", 1), ("ISSUED", 1), ("REVOKED", 1)]
    assert row_of(U1, "BPN") == bpn_before                           # BPN credential stays (OP-07)
    assert status_of(U1, "BPN") == "ISSUED"
    evs = revoked_events(osp)
    assert len(evs) == 1
    assert event_errors("c4-m1", evs[0]) == []
    assert evs[0]["source"] == "urn:c4-m1"
    assert evs[0]["data"] == {"companyId": U1, "credentialType": "MEMBERSHIP",
                              "revocationReason": "COMPANY_DEACTIVATED"}


def test_case_09_repetition_changes_nothing_and_emits_nothing(osp_factory, companies, wallet_fake):
    # README 13 case 9: repetition: no change, no event (8.2: REVOKED -> nothing); still DONE
    osp = osp_factory()
    issue_all(osp)
    done(revoke(osp, n=90))
    before = (snapshot(U1, "BPN"), snapshot(U1, "MEMBERSHIP"), len(osp.events()))
    result = done(revoke(osp, n=91))
    assert result["companyId"] == U1
    assert result["revoked"] == [] and result["cancelled"] == []
    assert (snapshot(U1, "BPN"), snapshot(U1, "MEMBERSHIP"), len(osp.events())) == before
    assert len(revoked_events(osp)) == 1
    assert history(U1, "MEMBERSHIP") == [("REQUESTED", 1), ("ISSUED", 1), ("REVOKED", 1)]


def test_case_09_reason_other_is_stored_and_published(osp_factory, companies, wallet_fake):
    # README 8.2 Input `reason` OTHER; README 5 revocation_reason; README 10 revocationReason
    osp = osp_factory()
    issue_all(osp)
    done(revoke(osp, reason="OTHER"))
    assert row_of(U1, "MEMBERSHIP")["revocation_reason"] == "OTHER"
    assert revoked_events(osp)[0]["data"]["revocationReason"] == "OTHER"


def test_case_09_explicit_types_revoke_each_with_one_event(osp_factory, companies, wallet_fake):
    # README 8.2: optional credentialTypes; "Event: CredentialRevoked per revoked type"
    osp = osp_factory()
    issue_all(osp)
    result = done(revoke(osp, credentialTypes=["BPN", "MEMBERSHIP"]))
    assert sorted(result["revoked"]) == TYPES
    assert [status_of(U1, t) for t in TYPES] == ["REVOKED", "REVOKED"]
    assert sorted(e["data"]["credentialType"] for e in revoked_events(osp)) == TYPES


def test_case_09_only_the_given_type_is_touched(osp_factory, companies, wallet_fake):
    # README 8.2: "Per given credential type"; revoking only BPN leaves MEMBERSHIP ISSUED
    osp = osp_factory()
    issue_all(osp)
    result = done(revoke(osp, credentialTypes=["BPN"]))
    assert result["revoked"] == ["BPN"]
    assert [status_of(U1, t) for t in TYPES] == ["REVOKED", "ISSUED"]
    assert [e["data"]["credentialType"] for e in revoked_events(osp)] == ["BPN"]


def test_case_09_a_finished_round_stays_done(osp_factory, companies, wallet_fake):
    # README 8.2: only a *running* round is set to CANCELLED; a DONE round is left alone
    osp = osp_factory()
    issue_all(osp)
    done(revoke(osp))
    assert store().get_run(U1)["status"] == "DONE"


def test_case_09_interface_call_returns_the_step_reply(osp_factory, companies, wallet_fake):
    # README 8 (FRAMEWORK 4.4): result {stepRunId, state, result}, also in-process
    osp = osp_factory()
    issue_all(osp)
    interface = seam("modules.c4_m1.interface")
    reply = interface.revoke_credentials({**step_input(U1, 90), "reason": "OTHER"})
    assert reply["state"] == "DONE"
    assert reply["stepRunId"] == step_input(U1, 90)["stepRunId"]
    assert reply["result"] == {"companyId": U1, "revoked": ["MEMBERSHIP"], "cancelled": [], "manualRevocation": []}


# ---------------------------------------------------------------------------------- input validation
@pytest.mark.parametrize("reason", [None, "", "BECAUSE", "other", 7])
def test_readme_8_2_reason_is_required_and_must_be_known(osp_factory, companies, wallet_fake, reason):
    # README 8.2 Input: reason COMPANY_DEACTIVATED or OTHER, else 400 validation (retryable false, README 12)
    osp = osp_factory()
    issued_rows()
    body = step_input(U1, 90)
    if reason is not None:
        body["reason"] = reason
    r = osp.post(REVOKE, osp.service("svc-c4-m1"), json=body)
    assert_problem(r, 400, "validation", retryable=False)
    assert [status_of(U1, t) for t in TYPES] == ["ISSUED", "ISSUED"]
    assert revoked_events(osp) == []


@pytest.mark.parametrize("types", [["FOO"], [], ["BPN", "BPN"]])
def test_readme_8_2_invalid_credential_types_are_validation_errors(osp_factory, companies, wallet_fake, types):
    # openapi StepRevokeCredentials: credentialTypes enum BPN/MEMBERSHIP (README 8.2), minItems 1, unique
    osp = osp_factory()
    issued_rows()
    assert_problem(revoke(osp, credentialTypes=types), 400, "validation", retryable=False)
    assert [status_of(U1, t) for t in TYPES] == ["ISSUED", "ISSUED"]


def test_readme_8_2_company_id_is_required(osp_factory, companies, wallet_fake):
    # README 8.2 Input: companyId; openapi required
    osp = osp_factory()
    body = {"processId": step_input(U1)["processId"], "stepRunId": step_input(U1)["stepRunId"],
            "reason": "OTHER"}
    assert_problem(osp.post(REVOKE, osp.service("svc-c4-m1"), json=body), 400, "validation", retryable=False)


# ------------------------------------------------------------------------- cancelling open orders
def test_case_10_revoke_while_requested_cancels_without_event(osp_factory, companies, wallet_fake):
    # README 13 case 10, 6.1: REQUESTED -> CANCELLED, no event; 6.2: the running round becomes CANCELLED
    osp = osp_factory()
    issue(osp)
    result = done(revoke(osp))
    assert result["cancelled"] == ["MEMBERSHIP"] and result["revoked"] == [] and result["manualRevocation"] == []
    membership = row_of(U1, "MEMBERSHIP")
    assert membership["status"] == "CANCELLED"
    assert membership["revocation_reason"] == "COMPANY_DEACTIVATED"
    assert history(U1, "MEMBERSHIP") == [("REQUESTED", 1), ("CANCELLED", 1)]
    assert revoked_events(osp) == []
    assert osp.events("CredentialsIssued") == [] and osp.events("CredentialIssuanceFailed") == []
    assert status_of(U1, "BPN") == "REQUESTED"                       # not part of the default types
    assert store().get_run(U1)["status"] == "CANCELLED"


def test_case_10_late_success_report_of_the_timer_revokes_at_once(osp_factory, companies, wallet_fake):
    # README 13 case 10: a later success report revokes immediately: REVOKED, exactly one CredentialRevoked
    osp = osp_factory()
    issue(osp)
    done(revoke(osp))
    flush()                                                          # the STUB timers report SUCCESSFUL late
    membership = row_of(U1, "MEMBERSHIP")
    assert membership["status"] == "REVOKED" and membership["revoked_at"]
    assert membership["revocation_reason"] == "COMPANY_DEACTIVATED"
    assert history(U1, "MEMBERSHIP") == [("REQUESTED", 1), ("CANCELLED", 1), ("REVOKED", 1)]
    evs = revoked_events(osp)
    assert len(evs) == 1
    assert event_errors("c4-m1", evs[0]) == []
    assert evs[0]["data"] == {"companyId": U1, "credentialType": "MEMBERSHIP",
                              "revocationReason": "COMPANY_DEACTIVATED"}
    assert osp.events("CredentialsIssued") == []                     # MEMBERSHIP never ISSUED: round not DONE
    assert status_of(U1, "BPN") == "ISSUED"                          # BPN order was not cancelled
    assert store().get_run(U1)["status"] == "CANCELLED"
    flush()
    assert len(revoked_events(osp)) == 1                             # nothing more on a second flush


def test_case_10_late_success_report_over_http_revokes_at_once(osp_factory, companies, wallet_fake):
    # README 13 case 10 / 7.4: the late report arrives from the issuer's service account
    osp = osp_factory()
    issue(osp)
    done(revoke(osp, reason="OTHER"))
    r = osp.post("/api/c4-m1/issuer-callbacks/membership", osp.service("sa-credential-issuer"),
                 json={"bpn": U1_BPN, "status": "SUCCESSFUL"})
    assert r.status_code == 204, r.text
    assert status_of(U1, "MEMBERSHIP") == "REVOKED"
    evs = revoked_events(osp)
    assert len(evs) == 1 and evs[0]["data"]["revocationReason"] == "OTHER"


def test_readme_8_2_failed_row_becomes_cancelled_without_event(osp_factory, companies, wallet_fake):
    # README 8.2: REQUESTED, FAILED -> CANCELLED, no event
    osp = osp_factory()
    put_row("u1", "MEMBERSHIP", "FAILED", 2, failure_reason="declined", failed_at=ts(5))
    result = done(revoke(osp))
    assert result["cancelled"] == ["MEMBERSHIP"] and result["revoked"] == []
    row = row_of(U1, "MEMBERSHIP")
    assert row["status"] == "CANCELLED" and row["attempt"] == 2
    assert row["revocation_reason"] == "COMPANY_DEACTIVATED"
    assert history(U1, "MEMBERSHIP")[-1] == ("CANCELLED", 2)
    assert revoked_events(osp) == []


def test_readme_8_2_failed_round_is_not_a_running_round(osp_factory, companies, wallet_fake):
    # README 8.2: "Running round: CANCELLED" - a round that is FAILED keeps its status
    osp = osp_factory()
    issue(osp)
    r = osp.post("/api/c4-m1/issuer-callbacks/membership", osp.service("sa-credential-issuer"),
                 json={"bpn": U1_BPN, "status": "UNSUCCESSFUL", "message": "declined"})
    assert r.status_code == 204, r.text
    assert store().get_run(U1)["status"] == "FAILED"
    done(revoke(osp))
    assert status_of(U1, "MEMBERSHIP") == "CANCELLED"
    assert store().get_run(U1)["status"] == "FAILED"


def test_readme_8_2_mixed_types_are_revoked_and_cancelled_in_one_run(osp_factory, companies, wallet_fake):
    # README 8.2 per type: ISSUED -> revoked (event), REQUESTED -> cancelled (no event)
    osp = osp_factory()
    put_row("u1", "BPN", "ISSUED", 1, issued_at=ts(1))
    put_row("u1", "MEMBERSHIP", "REQUESTED", 2)
    result = done(revoke(osp, credentialTypes=["BPN", "MEMBERSHIP"]))
    assert result["revoked"] == ["BPN"] and result["cancelled"] == ["MEMBERSHIP"]
    assert [status_of(U1, t) for t in TYPES] == ["REVOKED", "CANCELLED"]
    assert [e["data"]["credentialType"] for e in revoked_events(osp)] == ["BPN"]


# ---------------------------------------------------------------------------- rows that stay as they are
@pytest.mark.parametrize("status", ["CANCELLED", "REVOCATION_PENDING", "REVOKED"])
def test_readme_8_2_cancelled_pending_and_revoked_rows_are_left_alone(osp_factory, companies, wallet_fake, status):
    # README 8.2: CANCELLED, REVOCATION_PENDING, REVOKED -> nothing (no change, no event); step is DONE
    osp = osp_factory()
    put_row("u1", "MEMBERSHIP", status, 1, revocation_reason="OTHER")
    before = (snapshot(U1, "MEMBERSHIP"), len(osp.events()))
    result = done(revoke(osp, reason="COMPANY_DEACTIVATED"))
    assert result["revoked"] == [] and result["cancelled"] == []
    assert (snapshot(U1, "MEMBERSHIP"), len(osp.events())) == before
    assert history(U1, "MEMBERSHIP") == []                           # put directly: no history was written


# ------------------------------------------------------------- routes that cannot revoke (manual revocation)
U4 = COMPANIES["u4"]["id"]


def put_issuer_row(ctype: str, status: str, attempt: int = 1, **fields) -> dict:
    """A row of the route CREDENTIAL_ISSUER (README 6.3 table: revocation not supported in 0.2), SAP DIV wallet."""
    return put_row("u4", ctype, status, attempt, route="CREDENTIAL_ISSUER", wallet_provider="SAP_DIV",
                   request_ref="", **fields)


def test_case_11_revoke_on_credential_issuer_route_is_revocation_pending_and_manual(osp_factory, companies,
                                                                                   wallet_fake):
    # README 13 case 11, 8.2 ISSUED bullet "route cannot: REVOCATION_PENDING, no event", 6.1 row 6, 6.3 table;
    # no test server is needed: the module must not call the Credential Issuer for a revocation at all
    osp = osp_factory()
    put_issuer_row("MEMBERSHIP", "ISSUED", issued_at=ts(1))
    result = done(revoke(osp, U4))
    assert result == {"companyId": U4, "revoked": [], "cancelled": [], "manualRevocation": ["MEMBERSHIP"]}
    row = row_of(U4, "MEMBERSHIP")
    assert row["status"] == "REVOCATION_PENDING" and row["route"] == "CREDENTIAL_ISSUER"
    assert row["revocation_reason"] == "COMPANY_DEACTIVATED" and not row["revoked_at"]
    assert history(U4, "MEMBERSHIP")[-1] == ("REVOCATION_PENDING", 1)          # README 6.1: every change has history
    assert revoked_events(osp) == []                                            # no event until OSP staff confirm


def test_case_11_second_revoke_leaves_revocation_pending_alone(osp_factory, companies, wallet_fake):
    # README 8.2: REVOCATION_PENDING -> nothing (no change, no event, no new history entry); the step is DONE
    # OPEN-QUESTION: whether `manualRevocation` of the repeated step still lists the pending type (README 8.2:
    # "types in REVOCATION_PENDING") is not tested; only that the row and the event log stay as they are.
    osp = osp_factory()
    put_issuer_row("MEMBERSHIP", "ISSUED", issued_at=ts(1))
    done(revoke(osp, U4, n=90))
    before = (snapshot(U4, "MEMBERSHIP"), len(osp.events()), history(U4, "MEMBERSHIP"))
    result = done(revoke(osp, U4, n=91))
    assert result["revoked"] == [] and result["cancelled"] == []
    assert (snapshot(U4, "MEMBERSHIP"), len(osp.events()), history(U4, "MEMBERSHIP")) == before
    assert status_of(U4, "MEMBERSHIP") == "REVOCATION_PENDING" and revoked_events(osp) == []


def test_case_11_issue_credentials_on_a_pending_revocation_is_invalid_state(osp_factory, companies, wallet_fake):
    # README 8.1 step 2: REVOCATION_PENDING -> 409 invalid-state before anything is sent (OSP staff confirm first)
    osp = osp_factory()
    put_issuer_row("BPN", "ISSUED", issued_at=ts(1))
    put_issuer_row("MEMBERSHIP", "ISSUED", issued_at=ts(1))
    done(revoke(osp, U4))
    r = osp.post(ISSUE, osp.service("svc-c4-m1"), json=step_input(U4, 91, credentialTypes=["MEMBERSHIP"]))
    assert_problem(r, 409, "invalid-state", retryable=False)
    assert status_of(U4, "MEMBERSHIP") == "REVOCATION_PENDING" and row_of(U4, "MEMBERSHIP")["attempt"] == 1
    assert orders() == []


def test_case_11_both_types_on_credential_issuer_route_are_pending_and_listed_as_manual(osp_factory, companies,
                                                                                       wallet_fake):
    # README 8.2 Result: manualRevocation = types in REVOCATION_PENDING (both given types here), no event
    osp = osp_factory()
    put_issuer_row("BPN", "ISSUED", issued_at=ts(1))
    put_issuer_row("MEMBERSHIP", "ISSUED", issued_at=ts(1))
    result = done(revoke(osp, U4, credentialTypes=["BPN", "MEMBERSHIP"]))
    assert result["revoked"] == [] and sorted(result["manualRevocation"]) == TYPES
    assert [status_of(U4, t) for t in TYPES] == ["REVOCATION_PENDING", "REVOCATION_PENDING"]
    assert revoked_events(osp) == []


def test_case_11_requested_row_on_credential_issuer_route_is_cancelled_not_pending(osp_factory, companies, wallet_fake):
    # README 8.2: REQUESTED, FAILED -> CANCELLED, no event (only the route CSP_ISSUER removes a grant first)
    osp = osp_factory()
    put_issuer_row("MEMBERSHIP", "REQUESTED")
    result = done(revoke(osp, U4))
    assert result["cancelled"] == ["MEMBERSHIP"] and result["manualRevocation"] == []
    assert status_of(U4, "MEMBERSHIP") == "CANCELLED" and revoked_events(osp) == []


# ----------------------------------------------------------------------- no credentials, preconditions
def test_readme_8_2_without_credentials_of_the_given_types_the_step_is_done_at_once(osp_factory, companies,
                                                                                   wallet_fake):
    # README 8.2 Preconditions: none; "without credentials of the given types, the step is DONE immediately"
    osp = osp_factory()
    result = done(revoke(osp))
    assert result == {"companyId": U1, "revoked": [], "cancelled": [], "manualRevocation": []}
    assert store().list_credentials(company_id=U1) == []             # a revocation creates no rows
    assert store().get_run(U1) is None
    assert osp.events("CredentialRevoked") == [] and osp.events("CredentialsIssued") == []


def test_readme_8_2_no_precondition_on_company_or_wallet(osp_factory, companies, wallet_fake):
    # README 8.2: "Preconditions: none": neither C3-M1 nor C4-M2 are asked; an INACTIVE company (the very case
    # of a deactivation) and a company unknown to C3-M1 both work
    osp = osp_factory()
    inactive = COMPANIES["inactive"]["id"]
    assert done(revoke(osp, inactive))["revoked"] == []
    unknown = str(uuid.UUID(int=12345))
    assert done(revoke(osp, unknown))["companyId"] == unknown
    companies.calls.clear()
    done(revoke(osp, U1, 91))
    assert companies.calls == [] and wallet_fake.holder_access_calls == []


def test_readme_8_2_revoking_an_inactive_company_still_revokes(osp_factory, companies, wallet_fake):
    # README 8.2 + FRAMEWORK 5.4: after CompanyDeactivated C3-M1 says INACTIVE; revocation must still work
    osp = osp_factory()
    issue_all(osp)
    companies.set_status(U1, "INACTIVE")
    assert done(revoke(osp))["revoked"] == ["MEMBERSHIP"]
    assert status_of(U1, "MEMBERSHIP") == "REVOKED"


def test_readme_8_2_revocation_is_per_company(osp_factory, companies, wallet_fake):
    # README 8.2: "Advisory lock on the companyId", objects found by companyId: U4's rows stay untouched
    osp = osp_factory()
    issue_all(osp)
    r = osp.post(ISSUE, osp.service("svc-c4-m1"), json=step_input(COMPANIES["u4"]["id"], 2))
    assert r.status_code == 200, r.text
    done(revoke(osp))
    assert status_of(COMPANIES["u4"]["id"], "MEMBERSHIP") == "REQUESTED"
    assert [e["data"]["companyId"] for e in revoked_events(osp)] == [U1]


# --------------------------------------------------------------------------------------------- auth
def test_readme_6_5_revoke_step_needs_the_step_permission(osp_factory, companies, wallet_fake):
    # README 6.5: /steps needs execute_steps_c4_m1: no token 401, issuer service account 403
    osp = osp_factory()
    issued_rows()
    body = {**step_input(U1, 90), "reason": "OTHER"}
    assert_problem(osp.post(REVOKE, json=body), 401, "unauthorized")
    assert_problem(osp.post(REVOKE, osp.service("sa-credential-issuer"), json=body), 403, "forbidden")
    assert status_of(U1, "MEMBERSHIP") == "ISSUED" and revoked_events(osp) == []
