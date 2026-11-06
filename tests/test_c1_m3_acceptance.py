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
#################################################################################
"""C1-M3 Application Review: the acceptance cases of README 13 with the built-in stand-ins of
C1-M2, C3-M1 and C3-M2 (README 11, test data README 14)."""
import copy
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import BASE, bearer, person_token
from modules.c1_m3 import interface, router
from portal_common import events, problems, standin
from portal_common import http as phttp
from portal_common.problems import Problem
from tools import test_iam

R1 = "bbede0f3-fbc4-433b-b7ca-1982e8724912"
R2 = "ed9d901d-cdc3-4a86-8ab4-0b477318506c"
OSP_B = "99a5685c-7397-402c-88de-b1b3a939ecc9"

# 14.2: A1 in full
A1 = {
    "id": "05b53523-7794-456e-92aa-2e36524e546e", "companyId": "c0000001-0000-4000-8000-000000000001",
    "kind": "ONBOARDING", "existingCompany": False, "verification": "EBW",
    "applicant": {"sub": "5a1c0001-0000-4000-8000-000000000001", "givenName": "Erika", "familyName": "Mustermann"},
    "status": "SUBMITTED",
    "companyData": {
        "legalName": "Beispiel Maschinenbau GmbH", "shortName": "Beispiel Maschinenbau",
        "address": {"streetName": "Musterstraße 1", "streetNumber": None, "postalCode": "70569", "city": "Stuttgart",
                    "region": None, "countryCode": "DE"},
        "identifiers": [{"type": "EBWOID", "value": "EBWOID-DE-0000000001", "source": "ATTESTATION"},
                        {"type": "EUID", "value": "DEXX001T.HRB100001", "source": "ATTESTATION"},
                        {"type": "VAT_ID", "value": "DE123456789", "source": "APPLICANT"}]},
    "companyRoles": ["ACTIVE_PARTICIPANT"],
    "attestation": {
        "attestationId": "3f6c1e2a-7b4d-4e8f-9a51-2c0d6b8e4f17", "issuer": "https://ebw-connector.example.org",
        "keyId": "ebw-test-2026-1", "clientId": "demo-osp", "issuedAt": "2026-10-28T08:00:00Z",
        "expiresAt": "2026-11-27T08:00:00Z", "verifiedAt": "2026-10-28T08:00:00Z",
        "person": {"givenName": "Erika", "familyName": "Mustermann"},
        "representation": {"confirmed": True, "result": "CONFIRMED", "type": "legal_representative",
                           "role": "Geschäftsführerin", "validUntil": "2027-12-31",
                           "issuer": "https://register.test.example.org", "trust": "trust_list", "reasons": []},
        "company": {"legalName": "Beispiel Maschinenbau GmbH", "ebwoid": "EBWOID-DE-0000000001",
                    "euid": "DEXX001T.HRB100001", "countryCode": "DE",
                    "address": {"streetAddress": "Musterstraße 1", "postalCode": "70569", "locality": "Stuttgart",
                                "country": "DE"}},
        "evidence": [],
        "signatureCheck": {"result": "VALID", "checkedAt": "2026-10-28T08:30:00Z"}},
    "comparison": [{"field": f, "result": "FROM_ATTESTATION"}
                   for f in ("EBWOID", "EUID", "COUNTRY", "LEGAL_NAME", "STREET", "POSTAL_CODE", "CITY")],
    "documents": [], "representationDeclared": None,
    "consents": [{"agreementKey": k, "version": "1.0", "language": "de", "givenAt": "2026-10-28T08:20:00Z"}
                 for k in ("osp-terms", "terms-active-participant", "security-regulations")],
    "requiredAgreements": [{"agreementKey": k, "version": "1.0"}
                           for k in ("osp-terms", "terms-active-participant", "security-regulations")],
    "declineReason": None, "createdAt": "2026-10-28T08:10:00Z", "changedAt": "2026-10-28T08:20:00Z",
    "submittedAt": "2026-10-28T08:20:00Z", "withdrawnAt": None, "closedAt": None, "completedAt": None,
}

# 14.3
COMPANIES = [
    {"id": "c0000001-0000-4000-8000-000000000001", "status": "REQUESTED", "bpn": None,
     "identifiers": [{"type": "EUID", "value": "DEXX001T.HRB100001"}, {"type": "EBWOID", "value": "EBWOID-DE-0000000001"}]},
    {"id": "e0fbbb38-f0a7-4407-bc07-9b1991703a3a", "status": "ACTIVE", "bpn": "BPNL00000000009Z",
     "identifiers": [{"type": "EUID", "value": "DEXX001T.HRB654321"}]},
    {"id": "91d4a2b8-9045-48a8-8982-88131f6c7fae", "status": "REJECTED", "bpn": None,
     "identifiers": [{"type": "VAT_ID", "value": "DE123456789"}]},
    {"id": "cc080671-720e-42b6-95b2-0784c8314242", "status": "INACTIVE", "bpn": "BPNL00000000003C",
     "identifiers": [{"type": "EBWOID", "value": "EBWOID-DE-0000000003"}, {"type": "EUID", "value": "DEXX001T.HRB100003"}]},
]

# 14.4
CSP = [
    {"bpn": "BPNL00000000002B", "legalName": "Andere Beispiel AG", "country": "DE", "ebwoid": "EBWOID-DE-0000000002",
     "euid": None, "homeOspId": OSP_B, "homeOspName": "OSP B", "homeIsThisOsp": False, "memberActive": True},
    {"bpn": "BPNL00000000003C", "legalName": "Beispiel Werkzeugbau GmbH", "country": "DE",
     "ebwoid": "EBWOID-DE-0000000003", "euid": "DEXX001T.HRB100003",
     "homeOspId": "22222222-2222-4222-8222-222222222222", "homeOspName": "OSP A", "homeIsThisOsp": True,
     "memberActive": False},
]


def _copy(n: int, ebwoid: str | None = None, euid: str | None = "default", name: str | None = None, **top) -> dict:
    """A copy of A1 with its own IDs, EBWOID and EUID (14.2); IDs are derived, not invented per run."""
    a = copy.deepcopy(A1)
    a["id"], a["companyId"] = standin.stable_id("c1-m3 test", n), standin.stable_id("c1-m3 company", n)
    a["attestation"]["attestationId"] = standin.stable_id("c1-m3 attestation", n)
    ebwoid = ebwoid or f"EBWOID-DE-10000000{n:02d}"
    euid = f"DEXX001T.HRB2000{n:02d}" if euid == "default" else euid
    ids = [{"type": "EBWOID", "value": ebwoid, "source": "ATTESTATION"}]
    ids += [{"type": "EUID", "value": euid, "source": "ATTESTATION"}] if euid else []
    a["companyData"]["identifiers"] = ids + [i for i in a["companyData"]["identifiers"] if i["type"] == "VAT_ID"]
    a["attestation"]["company"].update(ebwoid=ebwoid, euid=euid)
    if name:
        a["companyData"]["legalName"] = a["attestation"]["company"]["legalName"] = name
    a.update(top)
    return a


def _applications() -> dict[str, dict]:
    apps = {"A1": copy.deepcopy(A1)}
    apps["A2"] = _copy(2)
    apps["A2"]["companyData"]["legalName"] = "Beispiel Maschinenbau AG"
    apps["A2"]["comparison"][3]["result"] = "MISMATCH"
    apps["A3"] = _copy(3)
    apps["A3"]["attestation"]["representation"].update(confirmed=False, result="NOT_CONFIRMED", reasons=["COMPANY_MISMATCH"])
    apps["A4"] = _copy(4, euid="DEXX001T.HRB654321")
    apps["A5"] = _copy(5)
    apps["A5"]["consents"] = [c for c in apps["A5"]["consents"] if c["agreementKey"] != "osp-terms"]
    apps["A6"] = _copy(6)
    apps["A6"]["attestation"]["signatureCheck"]["result"] = "INVALID"
    apps["A7"] = _copy(7, status="CREATED", submittedAt=None, consents=[], requiredAgreements=[])
    apps["A8"] = _copy(8)
    apps["A8"]["attestation"]["expiresAt"] = "2026-10-28T08:15:00Z"
    apps["A9"] = _copy(9)
    apps["A10"] = _copy(10, ebwoid="EBWOID-DE-0000000002", euid=None, name="Andere Beispiel AG")
    apps["A11"] = _copy(11, ebwoid="EBWOID-DE-0000000002", euid=None, name="Andere Beispiel AG", kind="TRANSFER")
    apps["A12"] = _copy(12, ebwoid="EBWOID-DE-0000000003", euid="DEXX001T.HRB100003", name="Beispiel Werkzeugbau GmbH",
                        kind="REACTIVATION", existingCompany=True, companyId="cc080671-720e-42b6-95b2-0784c8314242")
    apps["A13"] = _copy(13, kind="TRANSFER")
    apps["A14"] = _copy(14, verification="DOCUMENTS", attestation=None, comparison=[], representationDeclared=True,
                        documents=[{"documentId": standin.stable_id("c1-m3 document", 14),
                                    "type": "COMMERCIAL_REGISTER_EXTRACT"}])
    apps["A14"]["companyData"]["legalName"] = "Beispiel Feinmechanik GmbH"
    apps["A14"]["companyData"]["identifiers"] = [{"type": "COMMERCIAL_REG_NUMBER", "value": "HRB 100005",
                                                  "source": "APPLICANT"}]
    apps["A15"] = _copy(15)
    apps["A15"]["applicant"]["sub"] = R1
    apps["A16"] = _copy(16, status="WITHDRAWN", withdrawnAt="2026-10-28T09:00:00Z")
    apps["A17"] = _copy(17, name="Andere Beispiel AG", kind="TRANSFER")
    return apps


APPS = _applications()


class Env:
    def __init__(self, tmp_path, monkeypatch):
        self.files = {k: tmp_path / f"stub-{k}.json" for k in ("applications", "companies", "csp")}
        self.monkeypatch = monkeypatch
        self.write("applications", list(APPS.values()))
        self.write("companies", COMPANIES)
        self.write("csp", CSP)

    def write(self, which: str, data) -> None:
        self.files[which].write_text(json.dumps(data), encoding="utf-8")

    def set_status(self, key: str, status: str) -> None:
        apps = [dict(a, status=status) if a["id"] == APPS[key]["id"] else a for a in APPS.values()]
        self.write("applications", apps)

    def env(self, **values) -> None:
        for k, v in values.items():
            self.monkeypatch.setenv(k, v)


@pytest.fixture
def env(tmp_path, monkeypatch):
    for target in ("C1_M2_URL", "C3_M1_URL", "C3_M2_URL"):
        monkeypatch.setenv(target, "")   # empty address: built-in stand-in (FRAMEWORK 4.7)
    for var in ("ENABLED_CHECKS", "FOUR_EYES_CASES", "AUTO_APPROVE_KINDS", "DUPLICATE_CHECK_IDENTIFIER_TYPES"):
        monkeypatch.delenv(var, raising=False)
    e = Env(tmp_path, monkeypatch)
    e.env(STUB_APPLICATIONS_FILE=str(e.files["applications"]), STUB_COMPANIES_FILE=str(e.files["companies"]),
          STUB_CSP_FILE=str(e.files["csp"]))
    router.reset()
    return e


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(test_iam.router)
    app.include_router(router.router)
    problems.install(app)
    phttp.register_local(BASE, app)
    return TestClient(app, base_url=BASE)


def _h(person: str) -> dict:
    return bearer(person_token(person))


def step(name: str, key: str, n: int = 1) -> dict:
    fn = interface.open_review if name == "open" else interface.close_review
    body = {"processId": standin.stable_id("process", key), "stepRunId": standin.stable_id("run", key, name, n),
            "applicationId": APPS[key]["id"]}
    if name == "close":
        body["reason"] = "WITHDRAWN"
    return fn(body)


def checks_of(key: str) -> dict:
    case = interface.cases[interface.by_application[APPS[key]["id"]]]
    return {c["checkKey"]: c for c in interface.view(case)["checks"]}


def case_id(key: str) -> str:
    return interface.by_application[APPS[key]["id"]]


def events_of(event_type: str) -> list[dict]:
    return [e["data"] for e in events.RELAY.log if e["type"] == event_type]


def approve(client, key: str, person: str, comment: str | None = None):
    return client.post(f"/api/c1-m3/review-cases/{case_id(key)}/approve", headers=_h(person),
                       json={"comment": comment} if comment else None)


def decline(client, key: str, person: str, reason: str | None = "Company data could not be confirmed"):
    return client.post(f"/api/c1-m3/review-cases/{case_id(key)}/decline", headers=_h(person),
                       json={"reason": reason} if reason else {})


def problem(exc: pytest.ExceptionInfo) -> dict:
    return exc.value.body() | {"status": exc.value.status}


# ------------------------------------------------------------------------------ 1, 2: open-review
def test_01_02_open_review_six_checks_passed_and_idempotent(env):
    r = step("open", "A1")
    assert r["state"] == "DONE" and r["result"]["status"] == "OPEN"
    assert [c["checkKey"] for c in r["result"]["checks"]] == interface.checks.ORDER
    assert {c["result"] for c in r["result"]["checks"]} == {"PASSED"}
    again = step("open", "A1", 2)
    assert again["result"] == r["result"]
    assert {c["attempts"] for c in checks_of("A1").values()} == {1}
    assert len(interface.cases) == 1


# -------------------------------------------------------------------------- 3 to 7: single checks
def test_03_company_data_mismatch(env):
    step("open", "A2")
    c = checks_of("A2")["COMPANY_DATA_MATCH"]
    assert c["result"] == "FAILED" and c["details"]["mismatchedFields"] == ["LEGAL_NAME"]


def test_04_representation_not_confirmed(env):
    step("open", "A3")
    c = checks_of("A3")["REPRESENTATION_CONFIRMED"]
    assert c["result"] == "FAILED" and c["details"]["representationReasons"] == ["COMPANY_MISMATCH"]


def test_05_duplicate_in_installation(env):
    step("open", "A4")
    c = checks_of("A4")["NO_DUPLICATE"]
    assert c["result"] == "FAILED"
    assert c["details"]["duplicates"] == [{"companyId": "e0fbbb38-f0a7-4407-bc07-9b1991703a3a",
                                           "companyStatus": "ACTIVE", "matchedOn": ["EUID"]}]
    step("open", "A1")   # finds only itself (excluded) and a rejected company
    assert checks_of("A1")["NO_DUPLICATE"]["result"] == "PASSED"


def test_06_consent_missing(env):
    step("open", "A5")
    c = checks_of("A5")["CONSENTS_COMPLETE"]
    assert c["result"] == "FAILED" and c["details"]["missing"] == [{"agreementKey": "osp-terms", "version": "1.0"}]


def test_07_attestation_invalid_and_expired(env):
    step("open", "A6")
    assert checks_of("A6")["ATTESTATION_VALID"]["result"] == "FAILED"
    step("open", "A8")
    c = checks_of("A8")["ATTESTATION_VALID"]
    assert c["result"] == "FAILED" and c["details"]["expiredAtSubmission"] is True


# ----------------------------------------------------------------------------- 8, 9: open-review errors
def test_08_not_submitted_and_unknown(env):
    with pytest.raises(Problem) as e:
        step("open", "A7")
    assert problem(e)["status"] == 409 and problem(e)["type"] == "urn:c1-m3:problem:invalid-state"
    assert problem(e)["retryable"] is False and not interface.cases
    with pytest.raises(Problem) as e:
        interface.open_review({"processId": "p", "stepRunId": "s", "applicationId": standin.stable_id("unknown")})
    assert problem(e)["status"] == 404 and problem(e)["retryable"] is False


@pytest.mark.parametrize("which,key", [("companies", "NO_DUPLICATE"), ("csp", "CSP_MATCH_EXPECTED")])
def test_09_neighbour_not_reachable_then_repeated(env, client, which, key):
    original = COMPANIES if which == "companies" else CSP
    env.write(which, "unavailable")
    with pytest.raises(Problem) as e:
        step("open", "A9")
    assert problem(e)["status"] == 502 and problem(e)["retryable"] is True
    assert checks_of("A9")[key]["result"] == "ERROR" and checks_of("A9")[key]["details"]["error"]
    r = approve(client, "A9", "rolf")
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m3:problem:checks-incomplete"
    assert r.json()["pendingChecks"] == [key]
    env.write(which, original)
    assert step("open", "A9", 2)["state"] == "DONE"
    attempts = {k: c["attempts"] for k, c in checks_of("A9").items()}
    assert checks_of("A9")[key]["result"] == "PASSED"
    assert attempts == {k: 2 if k == key else 1 for k in attempts}


def test_09_rejected_request_is_not_retryable(env, monkeypatch):
    rejected = Problem("c1-m3", 502, "neighbour-rejected", detail="c3-m1 answered 400", retryable=False)

    def reject(*_args):
        raise rejected
    monkeypatch.setattr(interface.calls, "identifier_matches", reject)
    with pytest.raises(Problem) as e:
        step("open", "A9")
    assert problem(e)["status"] == 502 and problem(e)["type"] == "urn:c1-m3:problem:neighbour-rejected"
    assert problem(e)["retryable"] is False and problem(e)["pendingChecks"] == ["NO_DUPLICATE"]
    check = checks_of("A9")["NO_DUPLICATE"]
    assert check["result"] == "ERROR" and check["details"] == {"error": "C3-M1 rejected the request"}
    assert "_rejected" not in interface.view(interface.cases[case_id("A9")])

    env.write("csp", "unavailable")   # together with a temporary error, a repetition can still help
    interface.cases[case_id("A9")]["checks"].pop("CSP_MATCH_EXPECTED")
    with pytest.raises(Problem) as e:
        step("open", "A9", 2)
    assert problem(e)["type"] == "urn:c1-m3:problem:upstream-error" and problem(e)["retryable"] is True

    env.write("csp", CSP)
    monkeypatch.undo()
    monkeypatch.setenv("C1_M2_URL", "")
    monkeypatch.setenv("C3_M1_URL", "")
    monkeypatch.setenv("C3_M2_URL", "")
    env.env(STUB_APPLICATIONS_FILE=str(env.files["applications"]), STUB_COMPANIES_FILE=str(env.files["companies"]),
            STUB_CSP_FILE=str(env.files["csp"]))
    assert step("open", "A9", 3)["state"] == "DONE"
    assert not interface.cases[case_id("A9")]["_rejected"]


# ------------------------------------------------------------------------------ 10 to 13: CSP match
def test_10_onboarding_registered_at_other_osp(env):
    step("open", "A10")
    c = checks_of("A10")["CSP_MATCH_EXPECTED"]
    assert c["result"] == "FAILED" and c["details"]["cspOutcome"] == "REGISTERED_AT_OTHER_OSP"
    [m] = c["details"]["cspMatches"]
    assert (m["bpn"], m["homeOspId"], m["expected"]) == ("BPNL00000000002B", OSP_B, False)


def test_11_transfer_expected_match_and_approval(env, client):
    step("open", "A11")
    c = checks_of("A11")["CSP_MATCH_EXPECTED"]
    assert c["result"] == "PASSED" and c["details"]["cspOutcome"] == "EXPECTED_MATCH"
    r = approve(client, "A11", "rolf")
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"
    [ev] = events_of("ApplicationApproved")
    assert (ev["kind"], ev["existingCompany"], ev["bpn"]) == ("TRANSFER", False, "BPNL00000000002B")


def test_12_reactivation_expected_match_and_approval(env, client):
    step("open", "A12")
    assert checks_of("A12")["NO_DUPLICATE"]["result"] == "PASSED"
    c = checks_of("A12")["CSP_MATCH_EXPECTED"]
    assert c["result"] == "PASSED" and [m["bpn"] for m in c["details"]["cspMatches"] if m["expected"]] == ["BPNL00000000003C"]
    assert approve(client, "A12", "rolf").status_code == 200
    [ev] = events_of("ApplicationApproved")
    assert (ev["kind"], ev["existingCompany"], ev["bpn"]) == ("REACTIVATION", True, "BPNL00000000003C")


def test_13_transfer_without_expected_match(env, client):
    step("open", "A13")
    c = checks_of("A13")["CSP_MATCH_EXPECTED"]
    assert c["result"] == "FAILED" and c["details"]["cspOutcome"] == "NO_MATCH"
    r = approve(client, "A13", "rolf", "checked by phone")
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m3:problem:csp-match-required"
    assert r.json()["cspOutcome"] == "NO_MATCH"
    step("open", "A17")
    assert checks_of("A17")["CSP_MATCH_EXPECTED"]["details"]["cspOutcome"] == "NAME_MATCH_ONLY"
    assert checks_of("A17")["CSP_MATCH_EXPECTED"]["result"] == "FAILED"


# ------------------------------------------------------------------------- 14 to 18: decisions
def test_14_approve_once(env, client):
    step("open", "A1")
    r = approve(client, "A1", "rolf")
    assert r.status_code == 200 and r.json()["status"] == "APPROVED" and "application" not in r.json()
    [ev] = events_of("ApplicationApproved")
    assert {k: ev[k] for k in ("applicationId", "companyId", "kind", "existingCompany")} == \
        {"applicationId": A1["id"], "companyId": A1["companyId"], "kind": "ONBOARDING", "existingCompany": False}
    assert "bpn" not in ev
    assert approve(client, "A1", "rolf").status_code == 200 and len(events_of("ApplicationApproved")) == 1
    r = decline(client, "A1", "rolf")
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m3:problem:invalid-state"


def test_15_four_eyes_after_failed_check(env, client):
    step("open", "A2")
    r = approve(client, "A2", "rolf")
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m3:problem:comment-required"
    assert r.json()["failedChecks"] == ["COMPANY_DATA_MATCH"]
    r = approve(client, "A2", "rolf", "AG is the new legal form, checked in the register")
    assert r.json()["status"] == "AWAITING_SECOND_APPROVAL" and r.json()["firstApproval"]["fourEyesReasons"] == ["CHECK_FAILED"]
    assert not events_of("ApplicationApproved")
    r = approve(client, "A2", "rolf")
    assert r.status_code == 200 and r.json()["status"] == "AWAITING_SECOND_APPROVAL"
    r = approve(client, "A2", "renate")
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"
    assert len(events_of("ApplicationApproved")) == 1
    assert r.json()["firstApproval"]["approvedBy"] == R1 and r.json()["decision"]["decidedBy"] == R2


def test_16_documents_path(env, client):
    env.env(AUTO_APPROVE_KINDS="ONBOARDING")
    r = step("open", "A14")
    results = {c["checkKey"]: c["result"] for c in r["result"]["checks"]}
    assert results == {"ATTESTATION_VALID": "NOT_APPLICABLE", "REPRESENTATION_CONFIRMED": "NOT_APPLICABLE",
                       "COMPANY_DATA_MATCH": "NOT_APPLICABLE", "NO_DUPLICATE": "PASSED",
                       "CSP_MATCH_EXPECTED": "PASSED", "CONSENTS_COMPLETE": "PASSED"}
    assert r["result"]["status"] == "OPEN"
    r = approve(client, "A14", "rolf")
    assert r.json()["status"] == "AWAITING_SECOND_APPROVAL" and r.json()["firstApproval"]["fourEyesReasons"] == ["DOCUMENTS"]
    assert approve(client, "A14", "renate").json()["status"] == "APPROVED"


def test_17_decline_needs_reason(env, client):
    step("open", "A3")
    r = decline(client, "A3", "rolf", reason=None)
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m3:problem:validation"
    r = decline(client, "A3", "rolf")
    assert r.status_code == 200 and r.json()["status"] == "DECLINED"
    [ev] = events_of("ApplicationDeclined")
    assert ev["reason"] == "Company data could not be confirmed" and ev["kind"] == "ONBOARDING"
    assert ev["existingCompany"] is False
    assert decline(client, "A3", "rolf").status_code == 200 and len(events_of("ApplicationDeclined")) == 1


def test_18_own_application(env, client):
    step("open", "A15")
    for r in (approve(client, "A15", "rolf"), decline(client, "A15", "rolf")):
        assert r.status_code == 403 and r.json()["type"] == "urn:c1-m3:problem:own-application"
    assert approve(client, "A15", "renate").status_code == 200


# ----------------------------------------------------------------------- 19, 20: withdrawal
def test_19_close_review(env, client):
    step("open", "A9")
    r = step("close", "A9")
    assert r["state"] == "DONE" and r["result"]["status"] == "CLOSED" and not events.RELAY.log
    assert step("close", "A9", 2)["result"] == r["result"]
    r = approve(client, "A9", "rolf")
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m3:problem:invalid-state"
    r = step("close", "A16")
    assert r["result"]["status"] == "CLOSED"
    r = step("open", "A16")
    assert r["state"] == "DONE" and r["result"]["status"] == "CLOSED" and r["result"]["checks"] == []
    step("open", "A1")
    approve(client, "A1", "rolf")
    with pytest.raises(Problem) as e:
        step("close", "A1")
    assert problem(e)["status"] == 409 and problem(e)["retryable"] is False


def test_19_open_review_of_a_withdrawn_application_without_a_case(env):
    r = step("open", "A16")   # 8.1 step 2: a closed review case, no checks, DONE
    assert r["state"] == "DONE" and r["result"]["status"] == "CLOSED" and r["result"]["checks"] == []
    case = interface.cases[case_id("A16")]
    assert case["closure"]["reason"] == "WITHDRAWN" and not events.RELAY.log
    assert step("open", "A16", 2)["result"] == r["result"] and len(interface.cases) == 1


def test_20_withdrawn_before_close_review(env, client):
    step("open", "A9")
    env.set_status("A9", "WITHDRAWN")
    for r in (approve(client, "A9", "rolf"), decline(client, "A9", "rolf")):
        assert r.status_code == 409 and r.json()["type"] == "urn:c1-m3:problem:application-withdrawn"


# ---------------------------------------------------------------------- 21 to 23: reading, permissions
def test_21_list(env, client):
    for key in ("A1", "A11", "A2", "A3"):
        step("open", key)
    approve(client, "A1", "rolf")
    decline(client, "A3", "rolf")
    r = client.get("/api/c1-m3/review-cases", headers=_h("rolf")).json()
    assert [i["applicationId"] for i in r["items"]] == [APPS["A11"]["id"], APPS["A2"]["id"]]
    assert r["items"][0]["application"]["legalName"] == "Andere Beispiel AG"
    assert r["items"][0]["application"]["countryCode"] == "DE" and r["total"] == 2
    assert r["items"][1]["checkCounts"] == {"passed": 5, "failed": 1, "notApplicable": 0, "error": 0}
    r = client.get("/api/c1-m3/review-cases?kind=TRANSFER", headers=_h("rolf")).json()
    assert [i["kind"] for i in r["items"]] == ["TRANSFER"]
    r = client.get("/api/c1-m3/review-cases?status=APPROVED&status=DECLINED", headers=_h("rolf")).json()
    assert {i["status"] for i in r["items"]} == {"APPROVED", "DECLINED"} and r["total"] == 2


def test_22_details(env, client):
    step("open", "A4")
    r = client.get(f"/api/c1-m3/review-cases/{case_id('A4')}", headers=_h("rolf")).json()
    assert len(r["checks"]) == 6 and r["checks"][3]["details"]["duplicates"]
    assert r["application"]["applicant"]["sub"] == A1["applicant"]["sub"]


def test_23_permissions(env, client):
    step("open", "A1")
    cid = case_id("A1")
    for method, path in (("GET", "/review-cases"), ("GET", f"/review-cases/{cid}"),
                         ("POST", f"/review-cases/{cid}/approve"), ("POST", f"/review-cases/{cid}/decline")):
        assert client.request(method, "/api/c1-m3" + path, headers=_h("erika"), json={"reason": "x"}).status_code == 403
    assert client.get("/api/c1-m3/review-cases", headers=_h("otto")).status_code == 200
    assert approve(client, "A1", "otto").status_code == 403
    assert client.get("/api/c1-m3/review-cases").status_code == 401


# --------------------------------------------------------------------- 24, 25: configuration
def test_24_auto_approval(env):
    env.env(AUTO_APPROVE_KINDS="ONBOARDING")
    r = step("open", "A1")
    assert r["result"]["status"] == "APPROVED"
    assert interface.cases[case_id("A1")]["decision"]["autoApproved"] is True
    assert len(events_of("ApplicationApproved")) == 1
    assert step("open", "A2")["result"]["status"] == "OPEN"
    assert step("open", "A12")["result"]["status"] == "OPEN"
    router.reset()
    env.env(FOUR_EYES_CASES="ALWAYS")
    assert step("open", "A1")["result"]["status"] == "OPEN"
    env.env(AUTO_APPROVE_KINDS="REACTIVATION")
    with pytest.raises(ValueError, match="REACTIVATION"):
        router.on_startup()


def test_25_enabled_checks(env):
    env.env(ENABLED_CHECKS="ATTESTATION_VALID,REPRESENTATION_CONFIRMED,COMPANY_DATA_MATCH,CONSENTS_COMPLETE")
    env.write("companies", "unavailable")   # a call to C3-M1 or C3-M2 would give ERROR
    env.write("csp", "unavailable")
    r = step("open", "A1")
    assert [c["checkKey"] for c in r["result"]["checks"]] == \
        ["ATTESTATION_VALID", "REPRESENTATION_CONFIRMED", "COMPANY_DATA_MATCH", "CONSENTS_COMPLETE"]
    env.write("csp", CSP)
    r = step("open", "A11")
    assert "CSP_MATCH_EXPECTED" in [c["checkKey"] for c in r["result"]["checks"]]


# ------------------------------------------------------------------------- 26, 27: query, audit
def test_26_query(env, client):
    step("open", "A1")
    assert interface.get_review_status_by_application(applicationId=A1["id"])["status"] == "OPEN"
    with pytest.raises(Problem) as e:
        interface.get_review_status_by_application(applicationId=APPS["A7"]["id"])
    assert e.value.status == 404
    token = test_iam.iam().client_token("svc-c1-m3")
    r = client.get(f"/api/c1-m3/internal/review-cases?applicationId={A1['id']}", headers=bearer(token))
    assert r.status_code == 200 and r.json()["reviewCaseId"] == case_id("A1")


def test_27_audit_log_and_no_personal_data(env, client):
    step("open", "A2")
    approve(client, "A2", "rolf", "checked")
    decline(client, "A2", "renate")
    ops = [(a["operation"], a["sub"], a["processId"] is not None) for a in interface.audit_log]
    assert ops == [("open-review", None, True), ("approve", R1, False), ("decline", R2, False)]
    text = json.dumps([c["details"] for c in checks_of("A2").values()]) + json.dumps(events.RELAY.log)
    for value in ("Erika", "Mustermann", "EBWOID-DE-1000000002", "DEXX001T.HRB200002", "DE123456789"):
        assert value not in text


def test_step_over_http_with_service_token(env, client):
    token = test_iam.iam().client_token("svc-c1-m3")
    body = {"processId": standin.stable_id("p"), "stepRunId": standin.stable_id("s"), "applicationId": A1["id"]}
    r = client.post("/api/c1-m3/steps/open-review", headers=bearer(token), json=body)
    assert r.status_code == 200 and r.json()["result"]["status"] == "OPEN"
    assert client.post("/api/c1-m3/steps/open-review", headers=_h("rolf"), json=body).status_code == 403
