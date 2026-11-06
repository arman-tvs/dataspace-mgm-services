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
"""C4-M1 read side: README 7.1 (company view), 7.2 (OSP list), 7.3 (confirm revocation), 9.1 (internal
query); acceptance cases 8 and 20 (README 13).

Rows are seeded through the store seam of TEAM3-PLAN 12.3
(`seam("modules.c4_m1.interface").store().put_credential(row)`), with timezone-aware datetimes in the
timestamp fields (OPEN-QUESTION: the contract names the keys but not the Python type of the timestamps;
datetimes follow `service.now() -> datetime` of 12.3).
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest

from test_c4_m2_common import (
    COMPANIES,
    Clock,
    companies,  # noqa: F401  (fixture)
    event_errors,
    osp_factory,  # noqa: F401  (fixture)
    response_errors,
    seam,
)

U1, U4 = COMPANIES["u1"], COMPANIES["u4"]
T0 = dt.datetime(2026, 11, 5, 8, 0, tzinfo=dt.UTC)
P = "/api/c4-m1"
PROBLEM = "urn:c4-m1:problem:"


# ------------------------------------------------------------------------------------------ helpers
def t(hours: float) -> dt.datetime:
    return T0 + dt.timedelta(hours=hours)


def parse(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def store():
    return seam("modules.c4_m1.interface").store()


def row(company: dict, ctype: str, status: str, changed: float = 0, **kw) -> dict:
    """A `credential` row with the spec keys of TEAM3-PLAN 12.3."""
    r = {"id": str(uuid.uuid4()), "company_id": company["id"], "credential_type": ctype, "status": status,
         "route": "STUB", "issuer_did": None, "wallet_provider": "STUB", "bpn": company["bpn"],
         "holder_did": f"did:web:wallet.example.org:{company['bpn']}", "request_ref": "stub-1", "attempt": 1,
         "requested_at": t(changed - 1), "issued_at": None, "failed_at": None, "revoked_at": None,
         "failure_reason": None, "revocation_reason": None, "created_at": t(changed - 1), "changed_at": t(changed)}
    r.update(kw)
    return r


def seed(*rows: dict) -> list[dict]:
    s = store()
    for r in rows:
        s.put_credential(r)
    return list(rows)


def problem_type(r) -> str:
    return r.json()["type"]


def admin(osp):  # P2 of README 14: OSP staff
    return osp.person("p2-osp-staff", ["OSP Admin"])


def company_admin(osp, company=U1):  # P1 of README 14
    return osp.person("p1-erika", ["Company Admin"], company_id=company["id"], bpn=company["bpn"])


# ----------------------------------------------------------------- README 7.1 / case 8: company view
VIEW_FIELDS = {"credentialType", "status", "requestedAt", "issuedAt", "revokedAt"}


def test_case_08_company_admin_reads_own_credentials_without_internal_fields(osp_factory, companies):
    # README 7.1, 13 case 8: no messages of the issuer, no routes
    osp = osp_factory()
    bpn, ms = seed(
        row(U1, "BPN", "ISSUED", issued_at=t(0), route="CSP_ISSUER", issuer_did="did:web:issuer.csp.example.org",
            request_ref="u1:BPN:1"),
        row(U1, "MEMBERSHIP", "FAILED", failed_at=t(0), failure_reason="Issuance declined by the stand-in"))
    r = osp.get(f"{P}/companies/{U1['id']}/credentials", company_admin(osp))
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list) and len(body) == 2
    assert response_errors("c4-m1", "GET", "/companies/{companyId}/credentials", 200, body) == []
    for item in body:
        assert set(item) <= VIEW_FIELDS, f"internal fields leaked: {set(item) - VIEW_FIELDS}"
    by_type = {i["credentialType"]: i for i in body}
    assert by_type["BPN"]["status"] == "ISSUED" and parse(by_type["BPN"]["issuedAt"]) == t(0)
    assert parse(by_type["BPN"]["requestedAt"]) == bpn["requested_at"]
    assert by_type["MEMBERSHIP"]["status"] == "FAILED"
    assert "Issuance declined" not in r.text and "did:web:issuer" not in r.text and "CSP_ISSUER" not in r.text


def test_case_08_types_without_a_row_appear_as_none(osp_factory, companies):
    # README 7.1: types of ONBOARDING_CREDENTIAL_TYPES without a row appear with status NONE
    osp = osp_factory({"ONBOARDING_CREDENTIAL_TYPES": "BPN,MEMBERSHIP"})
    seed(row(U1, "BPN", "ISSUED", issued_at=t(0)))
    r = osp.get(f"{P}/companies/{U1['id']}/credentials", company_admin(osp))
    assert r.status_code == 200
    by_type = {i["credentialType"]: i for i in r.json()}
    assert set(by_type) == {"BPN", "MEMBERSHIP"}
    assert by_type["BPN"]["status"] == "ISSUED"
    assert by_type["MEMBERSHIP"]["status"] == "NONE"
    assert not by_type["MEMBERSHIP"].get("requestedAt") and not by_type["MEMBERSHIP"].get("issuedAt")
    assert response_errors("c4-m1", "GET", "/companies/{companyId}/credentials", 200, r.json()) == []


def test_case_08_company_without_any_row_shows_every_onboarding_type_as_none(osp_factory, companies):
    osp = osp_factory({"ONBOARDING_CREDENTIAL_TYPES": "BPN,MEMBERSHIP"})
    r = osp.get(f"{P}/companies/{U1['id']}/credentials", company_admin(osp))
    assert r.status_code == 200
    assert sorted((i["credentialType"], i["status"]) for i in r.json()) == [("BPN", "NONE"), ("MEMBERSHIP", "NONE")]


def test_case_08_none_follows_onboarding_credential_types(osp_factory, companies):
    # README 7.1 names ONBOARDING_CREDENTIAL_TYPES as the source of the NONE entries
    osp = osp_factory({"ONBOARDING_CREDENTIAL_TYPES": "BPN"})
    r = osp.get(f"{P}/companies/{U1['id']}/credentials", company_admin(osp))
    assert r.status_code == 200
    assert [(i["credentialType"], i["status"]) for i in r.json()] == [("BPN", "NONE")]


def test_case_08_revoked_row_keeps_its_status_and_times(osp_factory, companies):
    osp = osp_factory()
    seed(row(U1, "MEMBERSHIP", "REVOKED", issued_at=t(1), revoked_at=t(5), revocation_reason="COMPANY_DEACTIVATED"))
    r = osp.get(f"{P}/companies/{U1['id']}/credentials", company_admin(osp))
    ms = next(i for i in r.json() if i["credentialType"] == "MEMBERSHIP")
    assert ms["status"] == "REVOKED" and parse(ms["revokedAt"]) == t(5) and parse(ms["issuedAt"]) == t(1)
    assert "revocationReason" not in ms and "COMPANY_DEACTIVATED" not in r.text


def test_case_08_other_company_is_404_not_found(osp_factory, companies):
    # README 6.5, 13 case 8: P1 (company U1) asks for U4
    osp = osp_factory()
    seed(row(U4, "BPN", "ISSUED", issued_at=t(0)))
    r = osp.get(f"{P}/companies/{U4['id']}/credentials", company_admin(osp))
    assert r.status_code == 404 and problem_type(r) == PROBLEM + "not-found"
    assert U4["bpn"] not in r.text


def test_case_08_person_without_company_id_is_404(osp_factory, companies):
    # README 6.5: "otherwise 404 not-found, also if the token has no company_id".
    # OPEN-QUESTION (spec inconsistency, case 8 vs 6.5 order): README 13 case 8 expects 404 for "Person P3 without
    # company_id", and README 14 makes P3 a person of portal role `Applicant`, which has no view_credentials; but 6.5
    # fixes the order token (401), permission (403), company scope (404), so P3 as defined would get 403. We follow
    # 6.5: P3 carries `Company Admin` (permission present) but no company_id -> 404; the 403 of the real P3 is
    # asserted in test_case_08_permission_is_checked_before_company_scope.
    osp = osp_factory()
    token = osp.person("p3-no-company", ["Company Admin"], company_id=None)
    r = osp.get(f"{P}/companies/{U1['id']}/credentials", token)
    assert r.status_code == 404 and problem_type(r) == PROBLEM + "not-found"


def test_case_08_member_without_permission_is_403(osp_factory, companies):
    # README 13 case 8: P4 (U1, role Member, no view_credentials)
    osp = osp_factory()
    token = osp.person("p4-member", ["Member"], company_id=U1["id"], bpn=U1["bpn"])
    r = osp.get(f"{P}/companies/{U1['id']}/credentials", token)
    assert r.status_code == 403 and problem_type(r) == PROBLEM + "forbidden"


def test_case_08_permission_is_checked_before_company_scope(osp_factory, companies):
    # README 6.5 order: token (401), permission (403), company scope (404)
    osp = osp_factory()
    token = osp.person("p4-member", ["Member"], company_id=U1["id"], bpn=U1["bpn"])
    r = osp.get(f"{P}/companies/{U4['id']}/credentials", token)
    assert r.status_code == 403 and problem_type(r) == PROBLEM + "forbidden"
    applicant = osp.person("p3-applicant", [], company_id=None)
    assert osp.get(f"{P}/companies/{U1['id']}/credentials", applicant).status_code == 403


def test_case_08_it_admin_has_view_credentials_too(osp_factory, companies):
    # README 6.5: proposal portal roles `Company Admin`, `IT Admin`
    osp = osp_factory()
    token = osp.person("p5-it", ["IT Admin"], company_id=U1["id"], bpn=U1["bpn"])
    assert osp.get(f"{P}/companies/{U1['id']}/credentials", token).status_code == 200


def test_case_08_without_token_is_401(osp_factory, companies):
    osp = osp_factory()
    r = osp.get(f"{P}/companies/{U1['id']}/credentials")
    assert r.status_code == 401 and problem_type(r) == PROBLEM + "unauthorized"


# --------------------------------------------------------------- README 9.1 / case 20: internal query
INTERNAL = "/internal/companies/{companyId}/credentials"


def test_internal_query_returns_credentials_and_last_round(osp_factory, companies):
    # README 9.1, openapi CompanyCredentialsInternal
    osp = osp_factory()
    seed(row(U1, "BPN", "ISSUED", issued_at=t(0)), row(U1, "MEMBERSHIP", "REQUESTED", requested_at=t(1)))
    seam("modules.c4_m1.interface").store().put_run({
        "company_id": U1["id"], "credential_types": ["BPN", "MEMBERSHIP"], "status": "RUNNING",
        "process_id": str(uuid.uuid4()), "step_run_id": str(uuid.uuid4()), "started_at": t(1), "finished_at": None})
    r = osp.get(f"{P}/internal/companies/{U1['id']}/credentials", osp.service("svc-c4-m1"))
    assert r.status_code == 200
    body = r.json()
    assert response_errors("c4-m1", "GET", INTERNAL, 200, body) == []
    assert body["companyId"] == U1["id"]
    assert {c["credentialType"]: c["status"] for c in body["credentials"]} == {"BPN": "ISSUED", "MEMBERSHIP": "REQUESTED"}
    assert body["run"]["status"] == "RUNNING" and body["run"]["credentialTypes"] == ["BPN", "MEMBERSHIP"]
    assert parse(body["run"]["startedAt"]) == t(1) and body["run"]["finishedAt"] is None
    assert set(body["run"]) == {"status", "credentialTypes", "startedAt", "finishedAt"}   # no process ids


def test_internal_query_finished_round_has_finished_at(osp_factory, companies):
    osp = osp_factory()
    seed(row(U1, "BPN", "ISSUED"), row(U1, "MEMBERSHIP", "ISSUED"))
    seam("modules.c4_m1.interface").store().put_run({
        "company_id": U1["id"], "credential_types": ["BPN", "MEMBERSHIP"], "status": "DONE", "process_id": None,
        "step_run_id": None, "started_at": t(1), "finished_at": t(2)})
    body = osp.get(f"{P}/internal/companies/{U1['id']}/credentials", osp.service("svc-c4-m1")).json()
    assert body["run"]["status"] == "DONE" and parse(body["run"]["finishedAt"]) == t(2)


def test_internal_query_company_with_rows_but_no_round_has_run_null(osp_factory, companies):
    osp = osp_factory()
    seed(row(U1, "BPN", "ISSUED"))
    body = osp.get(f"{P}/internal/companies/{U1['id']}/credentials", osp.service("svc-c4-m1")).json()
    assert "run" in body and body["run"] is None
    assert [c["credentialType"] for c in body["credentials"]] == ["BPN"]


def test_case_20_unknown_company_is_200_with_empty_list_and_run_null(osp_factory, companies):
    # README 9.1 / 13 case 20
    osp = osp_factory()
    unknown = "00000000-0000-4000-8000-0000deadbeef"
    r = osp.get(f"{P}/internal/companies/{unknown}/credentials", osp.service("svc-c4-m1"))
    assert r.status_code == 200
    assert r.json() == {"companyId": unknown, "credentials": [], "run": None}
    assert response_errors("c4-m1", "GET", INTERNAL, 200, r.json()) == []


def test_case_20_interface_function_returns_a_dict_and_never_raises(osp_factory, companies):
    osp_factory()
    unknown = "00000000-0000-4000-8000-0000deadbeef"
    out = seam("modules.c4_m1.interface").query_company_credentials(companyId=unknown)
    assert out == {"companyId": unknown, "credentials": [], "run": None}


def test_case_20_neighbour_query_of_an_unknown_company_is_not_none(osp_factory, companies):
    # neighbours.query turns a 404 Problem into None; the contract says 200 with an empty list instead
    from portal_common import neighbours
    osp_factory()
    unknown = "00000000-0000-4000-8000-0000deadbeef"
    out = neighbours.query("c4-m2", "c4-m1", "query_company_credentials", companyId=unknown)
    assert out is not None
    assert out["credentials"] == [] and out["run"] is None


def test_internal_query_needs_query_c4_m1(osp_factory, companies):
    # README 6.5 / 9: over HTTP with the permission query_c4_m1
    osp = osp_factory()
    path = f"{P}/internal/companies/{U1['id']}/credentials"
    assert osp.get(path).status_code == 401
    r = osp.get(path, osp.service("sa-csp-issuer"))   # only report_credential_status
    assert r.status_code == 403 and problem_type(r) == PROBLEM + "forbidden"
    assert osp.get(path, osp.service("svc-c4-m1")).status_code == 200


# ------------------------------------------------------------------------------- README 7.2: OSP list
def _seed_list() -> dict[str, dict]:
    """Five rows over three companies; `changed` hours decide the order (newest first: d, b, e, a, c)."""
    u1, u4, u6 = COMPANIES["u1"], COMPANIES["u4"], COMPANIES["u6"]
    rows = {
        "a": row(u1, "BPN", "ISSUED", changed=1, issued_at=t(1)),
        "b": row(u1, "MEMBERSHIP", "REQUESTED", changed=4, requested_at=t(3)),
        "c": row(u4, "BPN", "FAILED", changed=0, route="CREDENTIAL_ISSUER", wallet_provider="SAP_DIV",
                 failure_reason="credential issuer answered 500", failed_at=t(0), requested_at=t(-1)),
        "d": row(u4, "MEMBERSHIP", "REVOCATION_PENDING", changed=5, route="CREDENTIAL_ISSUER",
                 wallet_provider="SAP_DIV", requested_at=t(-5), issued_at=t(-4), revocation_reason="COMPANY_DEACTIVATED"),
        "e": row(u6, "MEMBERSHIP", "FAILED", changed=2, route="CSP_ISSUER", wallet_provider="CSP",
                 issuer_did="did:web:issuer.csp.example.org", request_ref=f"{u6['id']}:MEMBERSHIP:2", attempt=2,
                 failure_reason="declined", failed_at=t(2), requested_at=t(1.5)),
    }
    seed(*rows.values())
    return rows


def _list(osp, **params):
    return osp.get(f"{P}/credentials", admin(osp), params=params)


def _ids(r) -> list[str]:
    return [i["id"] for i in r.json()["items"]]


def test_osp_admin_lists_all_rows_sorted_by_changed_at_descending(osp_factory, companies):
    osp = osp_factory()
    rows = _seed_list()
    r = _list(osp)
    assert r.status_code == 200
    body = r.json()
    assert response_errors("c4-m1", "GET", "/credentials", 200, body) == []
    assert body["total"] == 5 and body["page"] == 0
    assert _ids(r) == [rows[k]["id"] for k in "dbeac"]
    changed = [parse(i["changedAt"]) for i in body["items"]]
    assert changed == sorted(changed, reverse=True)


def test_osp_list_items_carry_failure_reason_route_issuer_did_attempt_and_request_ref(osp_factory, companies):
    # README 7.2: "all fields except secrets, also failureReason, route, issuerDid, attempt, requestRef"
    osp = osp_factory()
    rows = _seed_list()
    items = {i["id"]: i for i in _list(osp).json()["items"]}
    e = items[rows["e"]["id"]]
    assert e["failureReason"] == "declined" and e["route"] == "CSP_ISSUER" and e["attempt"] == 2
    assert e["issuerDid"] == "did:web:issuer.csp.example.org"
    assert e["requestRef"] == f"{COMPANIES['u6']['id']}:MEMBERSHIP:2"
    assert e["companyId"] == COMPANIES["u6"]["id"] and e["credentialType"] == "MEMBERSHIP"
    assert e["walletProvider"] == "CSP" and e["bpn"] == COMPANIES["u6"]["bpn"] and e["status"] == "FAILED"
    d = items[rows["d"]["id"]]
    assert d["revocationReason"] == "COMPANY_DEACTIVATED" and d["route"] == "CREDENTIAL_ISSUER"
    assert d["holderDid"] == rows["d"]["holder_did"]


def test_osp_list_filter_status_is_repeatable(osp_factory, companies):
    osp = osp_factory()
    rows = _seed_list()
    assert _ids(_list(osp, status="FAILED")) == [rows[k]["id"] for k in "ec"]
    r = osp.get(f"{P}/credentials?status=FAILED&status=REVOCATION_PENDING", admin(osp))
    assert r.status_code == 200 and r.json()["total"] == 3
    assert _ids(r) == [rows[k]["id"] for k in "dec"]


@pytest.mark.parametrize("params,expected", [
    ({"credentialType": "BPN"}, "ac"),
    ({"credentialType": "MEMBERSHIP"}, "dbe"),
    ({"companyId": COMPANIES["u4"]["id"]}, "dc"),
    ({"route": "CREDENTIAL_ISSUER"}, "dc"),
    ({"route": "CSP_ISSUER"}, "e"),
    ({"route": "STUB"}, "ba"),
    ({"companyId": COMPANIES["u4"]["id"], "credentialType": "BPN", "status": "FAILED"}, "c"),
])
def test_osp_list_filters(osp_factory, companies, params, expected):
    osp = osp_factory()
    rows = _seed_list()
    r = _list(osp, **params)
    assert r.status_code == 200
    assert _ids(r) == [rows[k]["id"] for k in expected]
    assert r.json()["total"] == len(expected)


def test_osp_list_filter_requested_before_finds_open_orders(osp_factory, companies):
    # README 7.2: requestedBefore "to find open orders"; orders sent strictly before this time
    osp = osp_factory()
    rows = _seed_list()
    # requested_at: a=T0-1+1-... see row(): a t(0), b t(3), c t(-1), d t(-5), e t(1.5)
    cut = t(1.5).isoformat()
    r = _list(osp, requestedBefore=cut)
    assert r.status_code == 200
    assert sorted(_ids(r)) == sorted(rows[k]["id"] for k in "acd")


def test_osp_list_paging_is_stable_and_total_counts_all(osp_factory, companies):
    osp = osp_factory()
    rows = _seed_list()
    order = [rows[k]["id"] for k in "dbeac"]
    p0 = _list(osp, page=0, size=2)
    p1 = _list(osp, page=1, size=2)
    p2 = _list(osp, page=2, size=2)
    assert [_ids(p) for p in (p0, p1, p2)] == [order[0:2], order[2:4], order[4:5]]
    assert p1.json()["page"] == 1 and p1.json()["size"] == 2 and p1.json()["total"] == 5
    assert _list(osp, page=3, size=2).json()["items"] == []


def test_osp_list_default_size_is_20(osp_factory, companies):
    # openapi parameter Size: default 20
    osp = osp_factory()
    _seed_list()
    assert _list(osp).json()["size"] == 20


def test_osp_list_needs_manage_credentials(osp_factory, companies):
    # README 6.5: scope osp; Company Admin has only view_credentials
    osp = osp_factory()
    _seed_list()
    r = osp.get(f"{P}/credentials", company_admin(osp))
    assert r.status_code == 403 and problem_type(r) == PROBLEM + "forbidden"
    assert osp.get(f"{P}/credentials").status_code == 401


@pytest.mark.parametrize("params", [
    {"status": "BOGUS"}, {"credentialType": "PASSPORT"}, {"companyId": "not-a-uuid"}, {"route": "TELEPATHY"},
    {"requestedBefore": "yesterday"}, {"size": 0}, {"size": 101}, {"page": -1}, {"size": "many"},
])
def test_osp_list_invalid_filter_is_400_validation(osp_factory, companies, params):
    osp = osp_factory()
    r = _list(osp, **params)
    assert r.status_code == 400 and problem_type(r) == PROBLEM + "validation"


# --------------------------------------------------------------------- README 7.3: confirm revocation
def _confirm(osp, cid, token, body=None):
    return osp.post(f"{P}/credentials/{cid}/confirm-revocation", token, json={"note": "revoked by hand, ticket 4711"}
                    if body is None else body)


def _pending(**kw) -> dict:
    return row(U4, "MEMBERSHIP", "REVOCATION_PENDING", route="CREDENTIAL_ISSUER", wallet_provider="SAP_DIV",
               issued_at=t(0), revocation_reason="COMPANY_DEACTIVATED", **kw)


def test_confirm_revocation_unknown_credential_is_404(osp_factory, companies):
    osp = osp_factory()
    r = _confirm(osp, str(uuid.uuid4()), admin(osp))
    assert r.status_code == 404 and problem_type(r) == PROBLEM + "not-found"


def test_confirm_revocation_of_a_revoked_credential_is_200_without_change(osp_factory, companies):
    # README 7.3 step 2: status REVOKED: 200 without a change
    osp = osp_factory()
    (c,) = seed(row(U4, "MEMBERSHIP", "REVOKED", revoked_at=t(2), revocation_reason="OTHER"))
    before = dict(store().get_credential_by_id(c["id"]))
    r = _confirm(osp, c["id"], admin(osp))
    assert r.status_code == 200
    assert r.json()["status"] == "REVOKED" and r.json()["id"] == c["id"]
    assert response_errors("c4-m1", "POST", "/credentials/{credentialId}/confirm-revocation", 200, r.json()) == []
    assert store().get_credential_by_id(c["id"]) == before
    assert store().list_history(c["id"]) == [] and store().list_audit() == []
    assert osp.events("CredentialRevoked") == []


@pytest.mark.parametrize("status", ["REQUESTED", "ISSUED", "FAILED", "CANCELLED"])
def test_confirm_revocation_in_another_status_is_409_invalid_state(osp_factory, companies, status):
    # README 7.3 step 2
    osp = osp_factory()
    (c,) = seed(row(U4, "MEMBERSHIP", status))
    r = _confirm(osp, c["id"], admin(osp))
    assert r.status_code == 409 and problem_type(r) == PROBLEM + "invalid-state"
    assert store().get_credential_by_id(c["id"])["status"] == status
    assert osp.events("CredentialRevoked") == [] and store().list_audit() == []


def test_confirm_revocation_success_changes_row_history_audit_and_event(osp_factory, companies, monkeypatch):
    # README 7.3 step 3 and 4, 13 case 11 (second half)
    osp = osp_factory()
    clock = Clock(dt.datetime(2026, 11, 6, 12, 30, tzinfo=dt.UTC)).install(monkeypatch, "modules.c4_m1.service")
    (c,) = seed(_pending())
    token = osp.person("p2-osp-staff", ["OSP Admin"], given="Olga", family="Staffer")
    note = "revoked at the Credential Issuer, ticket 4711"
    r = _confirm(osp, c["id"], token, {"note": note})
    assert r.status_code == 200
    body = r.json()
    assert response_errors("c4-m1", "POST", "/credentials/{credentialId}/confirm-revocation", 200, body) == []
    assert body["id"] == c["id"] and body["status"] == "REVOKED" and parse(body["revokedAt"]) == clock()
    assert body["revocationReason"] == "COMPANY_DEACTIVATED"
    row_ = store().get_credential_by_id(c["id"])
    assert row_["status"] == "REVOKED" and row_["revoked_at"] == clock()
    # history with the note
    hist = store().list_history(c["id"])
    assert [(h["status"], h["note"], h["attempt"]) for h in hist] == [("REVOKED", note, 1)]
    assert hist[0]["credential_id"] == c["id"] and hist[0]["occurred_at"] == clock()
    # audit entry with sub of the person, no names (README 5 audit_entry)
    audit = store().list_audit()
    assert len(audit) == 1
    a = audit[0]
    assert a["sub"] == "p2-osp-staff" and a["operation"] == "CONFIRM_REVOCATION" and a["object_ref"] == c["id"]
    assert a["client_id"] == "portal-ui" and str(a["result"]) == "200" and a["occurred_at"] == clock()
    assert a.get("company_id") in (None, "")   # OSP staff token carries no company_id
    assert "Olga" not in str(store().dump()) and "Staffer" not in str(store().dump())
    # exactly one CredentialRevoked
    evs = osp.events("CredentialRevoked")
    assert len(evs) == 1 and evs[0]["source"] == "urn:c4-m1"
    assert evs[0]["data"] == {"companyId": U4["id"], "credentialType": "MEMBERSHIP",
                              "revocationReason": "COMPANY_DEACTIVATED"}
    assert event_errors("c4-m1", evs[0]) == []


def test_confirm_revocation_twice_is_idempotent(osp_factory, companies):
    # README 7.3: second confirmation is "REVOKED: 200 without a change": still one event, one audit entry
    osp = osp_factory()
    (c,) = seed(_pending())
    token = admin(osp)
    assert _confirm(osp, c["id"], token).status_code == 200
    again = _confirm(osp, c["id"], token)
    assert again.status_code == 200 and again.json()["status"] == "REVOKED"
    assert len(osp.events("CredentialRevoked")) == 1
    assert len(store().list_history(c["id"])) == 1 and len(store().list_audit()) == 1


def test_confirm_revocation_needs_manage_credentials_and_leaves_the_row(osp_factory, companies):
    osp = osp_factory()
    (c,) = seed(_pending())
    r = _confirm(osp, c["id"], company_admin(osp, U4))
    assert r.status_code == 403 and problem_type(r) == PROBLEM + "forbidden"
    assert store().get_credential_by_id(c["id"])["status"] == "REVOCATION_PENDING"
    assert _confirm(osp, c["id"], None).status_code == 401
    assert osp.events("CredentialRevoked") == []


def test_confirm_revocation_permission_comes_before_the_lookup(osp_factory, companies):
    osp = osp_factory()
    r = _confirm(osp, str(uuid.uuid4()), company_admin(osp))
    assert r.status_code == 403


@pytest.mark.parametrize("body", [{}, {"note": ""}, {"note": "x" * 501}, {"note": 7}, {"note": None}, {"other": "x"}])
def test_confirm_revocation_bad_note_is_400_validation(osp_factory, companies, body):
    # README 7.3: note 1 to 500 characters
    osp = osp_factory()
    (c,) = seed(_pending())
    r = _confirm(osp, c["id"], admin(osp), body)
    assert r.status_code == 400 and problem_type(r) == PROBLEM + "validation"
    assert store().get_credential_by_id(c["id"])["status"] == "REVOCATION_PENDING"
    assert osp.events("CredentialRevoked") == []


@pytest.mark.parametrize("note", ["x", "n" * 500])
def test_confirm_revocation_note_boundaries_are_accepted(osp_factory, companies, note):
    osp = osp_factory()
    (c,) = seed(_pending())
    r = _confirm(osp, c["id"], admin(osp), {"note": note})
    assert r.status_code == 200
    assert store().list_history(c["id"])[0]["note"] == note
