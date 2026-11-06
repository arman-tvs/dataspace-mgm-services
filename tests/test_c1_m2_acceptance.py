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
"""C1-M2 Registration: the acceptance cases of README 13 with the built-in stand-ins of C3-M1 and C1-M3 and
with verification attestations that the tests sign themselves (README 14.4, 14.5)."""
import base64
import json
import threading
import time
import uuid

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import BASE, bearer, person_token
from modules.c1_m2 import attestation, interface, router
from portal_common import events, problems
from portal_common import http as phttp
from portal_common.problems import Problem
from tools import test_iam
from tools.keys import ec_jwk

ISSUER = "https://ebw-connector.example.org"
AUDIENCE = "portal-registration"
KID = "ebw-test-2026-1"
ERIKA = "5a1c0001-0000-4000-8000-000000000001"
BOUND = "d4fef928-56fe-4c94-a6c1-ffc6ea43704c"
NO_PERMISSIONS = "08f42539-b270-4ca0-805d-c2c8500f23cd"
WERKZEUGBAU, GIESSEREI = "cc080671-720e-42b6-95b2-0784c8314242", "6c71d54b-e689-4eb6-a1fa-ae196d8a5209"
OSP_COMPANY = "11111111-1111-4111-8111-111111111111"
PDF = b"%PDF-1.7 test"
CONSENTS = [{"agreementKey": k, "version": "1.0", "language": lang}
            for k, lang in (("osp-terms", "de"), ("terms-active-participant", "de"), ("security-regulations", "en"))]

# 14.5
STUB_COMPANIES = [
    {"id": WERKZEUGBAU, "name": "Beispiel Werkzeugbau GmbH", "address": {"countryCode": "DE"}, "status": "INACTIVE",
     "deactivationReason": "OTHER", "bpn": "BPNL00000000003C",
     "identifiers": [{"type": "EBWOID", "value": "EBWOID-DE-0000000003"}, {"type": "EUID", "value": "DEXX001T.HRB100003"}],
     "companyRoles": ["ACTIVE_PARTICIPANT"]},
    {"id": GIESSEREI, "name": "Beispiel Gießerei GmbH", "address": {"countryCode": "DE"}, "status": "INACTIVE",
     "deactivationReason": "TRANSFERRED", "bpn": "BPNL00000000004D",
     "identifiers": [{"type": "EBWOID", "value": "EBWOID-DE-0000000004"}],
     "companyRoles": ["ACTIVE_PARTICIPANT", "APP_PROVIDER"]},
    {"id": OSP_COMPANY, "name": "OSP A Beispiel GmbH", "address": {"countryCode": "DE"}, "status": "ACTIVE",
     "bpn": "BPNL00000000OSPA", "identifiers": [{"type": "EUID", "value": "DEXX001T.HRB100000"}],
     "companyRoles": ["ONBOARDING_SERVICE_PROVIDER"]},
]
COMPANIES = {
    "maschinenbau": {"legal_name": "Beispiel Maschinenbau GmbH", "ebwoid": "EBWOID-DE-0000000001", "euid": "DEXX001T.HRB100001"},
    "werkzeugbau": {"legal_name": "Beispiel Werkzeugbau GmbH", "ebwoid": "EBWOID-DE-0000000003", "euid": "DEXX001T.HRB100003"},
    "giesserei": {"legal_name": "Beispiel Gießerei GmbH", "ebwoid": "EBWOID-DE-0000000004", "euid": "DEXX001T.HRB100004"},
}


class Env:
    def __init__(self, tmp_path, monkeypatch):
        self.monkeypatch = monkeypatch
        self.private, public = ec_jwk(KID)
        self.other, _ = ec_jwk(KID)
        self.jwks = tmp_path / "jwks.json"
        self.jwks.write_text(json.dumps({"keys": [public]}), encoding="utf-8")
        self.companies = tmp_path / "stub-companies.json"
        self.reviews = tmp_path / "stub-reviews.json"
        self.write(self.companies, STUB_COMPANIES)
        self.write(self.reviews, [])

    @staticmethod
    def write(path, data) -> None:
        path.write_text(json.dumps(data), encoding="utf-8")

    def payload(self, company: str = "maschinenbau", person: tuple[str, str] = ("Erika", "Mustermann"), **over) -> dict:
        now = int(attestation.now())
        c = COMPANIES[company]
        body = {"iss": ISSUER, "sub": c["ebwoid"], "aud": AUDIENCE, "iat": now - 60, "exp": now + 29 * 86400,
                "jti": str(uuid.uuid4()), "attestation_version": "0.2", "purpose": "onboarding", "verified_at": now - 60,
                "client_id": "demo-osp", "person": {"given_name": person[0], "family_name": person[1]},
                "company": {**c, "country": "DE", "address": {"street_address": "Musterstraße 1", "postal_code": "70569",
                                                              "locality": "Stuttgart", "country": "DE"}},
                "representation": {"confirmed": True, "result": "CONFIRMED", "type": "legal_representative"},
                "evidence": [{"type": "PID", "vct": "urn:eudi:pid:1", "issuer": "https://pid.test.example.org",
                              "wallet": "EUDI_WALLET", "status_checked": False}]}
        return body | over

    def sign(self, payload: dict | None = None, key: dict | None = None, **over) -> str:
        return jwt.encode(payload or self.payload(**over), jwt.PyJWK(key or self.private).key, algorithm="ES256",
                          headers={"typ": "ebw-attestation+jwt", "kid": KID})


@pytest.fixture
def env(tmp_path, monkeypatch):
    e = Env(tmp_path, monkeypatch)
    for target in ("C3_M1_URL", "C1_M3_URL"):
        monkeypatch.setenv(target, "")   # empty address: built-in stand-in (FRAMEWORK 4.7)
    for var in ("ATTESTATION_AUDIENCE", "ATTESTATION_ALGORITHMS", "ATTESTATION_CLIENT_IDS", "ATTESTATION_MAX_AGE",
                "ATTESTATION_JWKS_URL", "DOCUMENTS_ENABLED", "DOCUMENT_MAX_BYTES", "DOCUMENT_MAX_COUNT", "CATALOG_FILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ATTESTATION_ISSUER", ISSUER)
    monkeypatch.setenv("ATTESTATION_JWKS_FILE", str(e.jwks))
    monkeypatch.setenv("STUB_COMPANIES_FILE", str(e.companies))
    monkeypatch.setenv("STUB_REVIEWS_FILE", str(e.reviews))
    router.reset()
    iam = test_iam.iam()
    iam.first_login(BOUND, "Bea", "Bound", key="bound")   # bound account of 14.1, not in testdata/
    iam.bind(BOUND, OSP_COMPANY, "BPNL00000000OSPA")
    return e


@pytest.fixture
def client(env):
    app = FastAPI()
    app.include_router(test_iam.router)
    app.include_router(router.router)
    problems.install(app)
    phttp.register_local(BASE, app)
    return TestClient(app, base_url=BASE)


def _h(person: str) -> dict:
    return bearer(person_token(person))


def api(path: str) -> str:
    return "/api/c1-m2" + path


def onboarding(token: str, **over) -> dict:
    return {"kind": "ONBOARDING", "verification": "EBW", "attestation": token,
            "companyData": {"shortName": "Beispiel Maschinenbau", "identifiers": [{"type": "VAT_ID", "value": "DE123456789"}]},
            "companyRoles": ["ACTIVE_PARTICIPANT"]} | over


def documents_body(**over) -> dict:
    return {"kind": "ONBOARDING", "verification": "DOCUMENTS",
            "companyData": {"legalName": "Beispiel Feinmechanik GmbH",
                            "address": {"streetName": "Musterweg", "streetNumber": "5", "postalCode": "70569",
                                        "city": "Stuttgart", "countryCode": "DE"},
                            "identifiers": [{"type": "COMMERCIAL_REG_NUMBER", "value": "HRB 100005"}]},
            "companyRoles": ["ACTIVE_PARTICIPANT"]} | over


def created(client, env, applicant: str = "erika", **over) -> dict:
    r = client.post(api("/applications"), headers=_h(applicant), json=onboarding(env.sign(**over)))
    assert r.status_code == 201, r.text
    return r.json()


def submit(client, app_id: str, person: str = "erika", consents=None, **body):
    return client.post(api(f"/applications/{app_id}/submit"), headers=_h(person),
                       json={"consents": CONSENTS if consents is None else consents} | body)


def upload(client, app_id: str, content: bytes = PDF, name: str = "extract.pdf", doc_type: str = "COMMERCIAL_REGISTER_EXTRACT"):
    return client.post(api(f"/applications/{app_id}/documents"), headers=_h("erika"),
                       files={"file": (name, content, "application/pdf")}, data={"documentType": doc_type})


def events_of(event_type: str) -> list[dict]:
    return [e["data"] for e in events.RELAY.log if e["type"] == event_type]


def step(fn, app_id: str, **over) -> dict:
    return fn({"processId": str(uuid.uuid4()), "stepRunId": str(uuid.uuid4()), "applicationId": app_id} | over)


# ------------------------------------------------------------------------- 1 to 3: attestation
def test_01_create(client, env):
    r = client.post(api("/applications"), headers=_h("erika"), json=onboarding(env.sign()))
    assert r.status_code == 201 and r.headers["Location"].endswith(r.json()["id"])
    a = r.json()
    assert a["status"] == "CREATED" and a["kind"] == "ONBOARDING" and a["existingCompany"] is False and a["companyId"]
    data = a["companyData"]
    assert data["legalName"] == "Beispiel Maschinenbau GmbH" and data["address"]["city"] == "Stuttgart"
    assert {(i["type"], i["source"]) for i in data["identifiers"]} == {("EBWOID", "ATTESTATION"), ("EUID", "ATTESTATION"), ("VAT_ID", "APPLICANT")}
    assert {c["result"] for c in a["comparison"]} == {"FROM_ATTESTATION"}
    assert {c["field"] for c in a["comparison"]} == {"EBWOID", "EUID", "COUNTRY", "LEGAL_NAME", "STREET", "POSTAL_CODE", "CITY"}
    assert a["applicant"] == {"sub": ERIKA, "givenName": "Erika", "familyName": "Mustermann"}
    assert "keyId" not in a["attestation"] and "signatureCheck" not in a["attestation"]
    assert events_of("ApplicationCreated") == [{"applicationId": a["id"], "companyId": a["companyId"], "kind": "ONBOARDING",
                                                "existingCompany": False}]


@pytest.mark.parametrize("change,reason", [
    ("issuer", "issuer"), ("key", "signature"), ("none", "algorithm"), ("aud", "audience"), ("expired", "expired"),
    ("ebwoid", "claims"), ("version", "version"), ("purpose", "purpose"), ("client", "client")])
def test_02_invalid_attestations(client, env, monkeypatch, change, reason):
    now = int(attestation.now())
    token = {
        "issuer": lambda: env.sign(iss="https://other.example.org"),
        "key": lambda: env.sign(key=env.other),
        "none": lambda: jwt.encode(env.payload(), None, algorithm="none", headers={"typ": "ebw-attestation+jwt", "kid": KID}),
        "aud": lambda: env.sign(aud="other"),
        "expired": lambda: env.sign(exp=now - 3600),
        "ebwoid": lambda: env.sign(payload=env.payload() | {"company": {"legal_name": "Beispiel Maschinenbau GmbH", "country": "DE"}}),
        "version": lambda: env.sign(attestation_version="0.1"),
        "purpose": lambda: env.sign(purpose="delegation"),
        "client": lambda: env.sign(client_id="other-client"),
    }[change]()
    if change == "client":
        monkeypatch.setenv("ATTESTATION_CLIENT_IDS", "demo-osp")
    r = client.post(api("/applications"), headers=_h("erika"), json=onboarding(token))
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:attestation-invalid"
    assert r.json()["reason"] == reason and not interface.applications


def test_02_jwks_not_reachable_is_502(client, env, monkeypatch):
    monkeypatch.delenv("ATTESTATION_JWKS_FILE")
    monkeypatch.setenv("ATTESTATION_JWKS_URL", f"{BASE}/ebw/jwks-missing")
    r = client.post(api("/applications"), headers=_h("erika"), json=onboarding(env.sign()))
    assert r.status_code == 502 and r.json()["type"] == "urn:c1-m2:problem:upstream-error"


def test_03_person_binding(client, env):
    r = client.post(api("/applications"), headers=_h("erika"), json=onboarding(env.sign(person=("Max", "Mustermann"))))
    assert r.status_code == 400 and r.json()["reason"] == "person"
    assert created(client, env, person=(" ERIKA ", "mustermann"))["status"] == "CREATED"


# ------------------------------------------------------------------------ 4 to 9: applications
def test_04_bound_account(client, env):
    r = client.post(api("/applications"), headers=_h("bound"), json=onboarding(env.sign()))
    assert r.status_code == 403 and r.json()["type"] == "urn:c1-m2:problem:account-bound" and not interface.applications
    assert client.get(api("/applications"), headers=_h("bound")).status_code == 200


def test_05_repetition_and_single_use(client, env):
    token = env.sign()
    first = client.post(api("/applications"), headers=_h("erika"), json=onboarding(token))
    again = client.post(api("/applications"), headers=_h("erika"), json=onboarding(token))
    assert first.status_code == 201 and again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert len(events_of("ApplicationCreated")) == 1
    r = client.post(api("/applications"), headers=_h("erika"), json=onboarding(env.sign()))
    assert r.status_code == 409 and r.json()["existingApplicationId"] == first.json()["id"]
    assert client.post(api(f"/applications/{first.json()['id']}/withdraw"), headers=_h("erika")).status_code == 200
    r = client.post(api("/applications"), headers=_h("erika"), json=onboarding(token))
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m2:problem:attestation-used"


def test_06_fixed_and_compared_fields(client, env):
    body = onboarding(env.sign(), companyData={"identifiers": [{"type": "EUID", "value": "DEXX001T.HRB999999"}]})
    r = client.post(api("/applications"), headers=_h("erika"), json=body)
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:attestation-mismatch" and r.json()["fields"] == ["EUID"]
    body = onboarding(env.sign(), companyData={"legalName": "Beispiel Maschinenbau AG"})
    r = client.post(api("/applications"), headers=_h("erika"), json=body)
    assert r.status_code == 201
    assert {c["field"]: c["result"] for c in r.json()["comparison"]}["LEGAL_NAME"] == "MISMATCH"
    assert r.json()["companyData"]["legalName"] == "Beispiel Maschinenbau AG"


@pytest.mark.parametrize("body", [
    documents_body(companyData={"legalName": "Example Inc", "address": {"streetName": "Main", "city": "Detroit", "countryCode": "US"},
                                "identifiers": [{"type": "LEI_CODE", "value": "ABCDEFGHIJ0123456789"}]}),
    documents_body(companyData={"legalName": "Beispiel GmbH", "address": {"streetName": "Weg", "city": "Ulm", "countryCode": "DE"},
                                "identifiers": [{"type": "VAT_ID", "value": "DE12345"}]}),
    documents_body(companyRoles=["ONBOARDING_SERVICE_PROVIDER"])])
def test_07_reference_data(client, env, body):
    r = client.post(api("/applications"), headers=_h("erika"), json=body)
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:validation" and r.json()["errors"]


def test_08_other_people_see_nothing(client, env):
    aid = created(client, env)["id"]
    url, h = api(f"/applications/{aid}"), _h("max")
    responses = [client.get(url, headers=h), client.patch(url, headers=h, json={"shortName": "x"}),
                 client.post(url + "/submit", headers=h, json={"consents": CONSENTS}), client.post(url + "/withdraw", headers=h)]
    assert [r.status_code for r in responses] == [404, 404, 404, 404]


def test_09_change_only_before_submission(client, env):
    aid = created(client, env)["id"]
    url = api(f"/applications/{aid}")
    r = client.patch(url, headers=_h("erika"), json={"companyRoles": ["ACTIVE_PARTICIPANT", "APP_PROVIDER"]})
    assert r.status_code == 200 and r.json()["companyRoles"] == ["ACTIVE_PARTICIPANT", "APP_PROVIDER"]
    r = client.patch(url, headers=_h("erika"), json={"companyRoles": ["ACTIVE_PARTICIPANT"]})
    assert r.status_code == 200
    assert submit(client, aid).status_code == 200
    r = client.patch(url, headers=_h("erika"), json={"companyRoles": ["APP_PROVIDER"]})
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m2:problem:invalid-state"


# ------------------------------------------------------------------------ 10 to 12: submission
def test_10_submit(client, env):
    aid = created(client, env)["id"]
    r = submit(client, aid, consents=[c for c in CONSENTS if c["agreementKey"] != "osp-terms"])
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:consents-incomplete"
    assert r.json()["missing"] == [{"agreementKey": "osp-terms", "version": "1.0"}]
    r = submit(client, aid)
    assert r.status_code == 200 and r.json()["status"] == "SUBMITTED" and r.json()["submittedAt"]
    assert {c["language"] for c in r.json()["consents"]} == {"de", "en"}
    records = interface.applications[aid]["_consentRecords"]
    assert {x["givenBySub"] for x in records} == {ERIKA}
    assert {x["attestationId"] for x in records} == {interface.applications[aid]["_attestation"]["attestationId"]}
    assert events_of("ApplicationSubmitted")[0]["applicantSub"] == ERIKA
    assert submit(client, aid).status_code == 200 and len(events_of("ApplicationSubmitted")) == 1


def test_11_too_old_at_submission_and_replacement(client, env, monkeypatch):
    now = int(time.time())
    old = env.sign(exp=now + 60 * 86400)
    a = client.post(api("/applications"), headers=_h("erika"), json=onboarding(old)).json()
    monkeypatch.setattr(attestation, "now", lambda: now + 31 * 86400)
    r = submit(client, a["id"])
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m2:problem:attestation-expired"
    url = api(f"/applications/{a['id']}/attestation")
    assert client.put(url, headers=_h("erika"), json={"attestation": env.sign()}).status_code == 200
    r = client.put(url, headers=_h("erika"), json={"attestation": old})   # the old `jti` stays used
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m2:problem:attestation-used"
    assert submit(client, a["id"]).status_code == 200


def test_12_replacement_of_another_company(client, env):
    aid = created(client, env)["id"]
    url = api(f"/applications/{aid}/attestation")
    r = client.put(url, headers=_h("erika"), json={"attestation": env.sign(company="werkzeugbau")})
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:attestation-mismatch" and "EBWOID" in r.json()["fields"]
    assert client.post(api(f"/applications/{aid}/withdraw"), headers=_h("erika")).status_code == 200
    doc = client.post(api("/applications"), headers=_h("erika"), json=documents_body()).json()
    r = client.put(api(f"/applications/{doc['id']}/attestation"), headers=_h("erika"), json={"attestation": env.sign()})
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m2:problem:invalid-state"


# ------------------------------------------------------------------------ 13 to 15: existing companies
def _reactivation(env, company=WERKZEUGBAU, name="werkzeugbau", person=("Erika", "Mustermann"), **over) -> dict:
    return {"kind": "REACTIVATION", "verification": "EBW", "companyId": company,
            "attestation": env.sign(company=name, person=person)} | over


def test_13_reactivation(client, env):
    r = client.post(api("/applications"), headers=_h("erika"), json=_reactivation(env))
    assert r.status_code == 201
    a = r.json()
    assert a["existingCompany"] is True and a["companyId"] == WERKZEUGBAU and a["companyRoles"] == ["ACTIVE_PARTICIPANT"]
    client.post(api(f"/applications/{a['id']}/withdraw"), headers=_h("erika"))
    body = {"kind": "REACTIVATION", "verification": "EBW", "bpn": "BPNL00000000003C", "attestation": env.sign(company="werkzeugbau")}
    r = client.post(api("/applications"), headers=_h("erika"), json=body)
    assert r.status_code == 201 and r.json()["companyId"] == WERKZEUGBAU
    client.post(api(f"/applications/{r.json()['id']}/withdraw"), headers=_h("erika"))
    r = client.post(api("/applications"), headers=_h("erika"), json=_reactivation(env, company=OSP_COMPANY, name="maschinenbau"))
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m2:problem:company-not-eligible" and r.json()["companyStatus"] == "ACTIVE"
    r = client.post(api("/applications"), headers=_h("erika"), json=_reactivation(env, name="maschinenbau"))
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:attestation-mismatch" and "EBWOID" in r.json()["fields"]
    r = client.post(api("/applications"), headers=_h("erika"), json=onboarding(env.sign(), companyId=WERKZEUGBAU))
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:validation"
    env.write(env.companies, "unavailable")
    r = client.post(api("/applications"), headers=_h("erika"), json=_reactivation(env))
    assert r.status_code == 502 and r.json()["type"] == "urn:c1-m2:problem:upstream-error"


def test_14_transfer(client, env):
    body = {"kind": "TRANSFER", "verification": "EBW", "attestation": env.sign(), "companyRoles": ["ACTIVE_PARTICIPANT"]}
    r = client.post(api("/applications"), headers=_h("erika"), json=body)
    assert r.status_code == 201 and r.json()["existingCompany"] is False
    client.post(api(f"/applications/{r.json()['id']}/withdraw"), headers=_h("erika"))
    body = {"kind": "TRANSFER", "verification": "EBW", "companyId": GIESSEREI, "attestation": env.sign(company="giesserei")}
    r = client.post(api("/applications"), headers=_h("erika"), json=body)
    assert r.status_code == 201 and r.json()["existingCompany"] is True and r.json()["companyId"] == GIESSEREI
    client.post(api(f"/applications/{r.json()['id']}/withdraw"), headers=_h("erika"))
    r = client.post(api("/applications"), headers=_h("erika"), json=_reactivation(env, company=GIESSEREI, name="giesserei"))
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m2:problem:company-not-eligible"


def test_15_one_open_application_per_company(client, env):
    assert client.post(api("/applications"), headers=_h("erika"), json=_reactivation(env)).status_code == 201
    r = client.post(api("/applications"), headers=_h("max"), json=_reactivation(env, person=("Max", "Mustermann")))
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m2:problem:company-has-open-application"


# ------------------------------------------------------------------------ 16, 17: documents
def test_16_documents_path(client, env, monkeypatch):
    bad = documents_body(companyData={**documents_body()["companyData"], "identifiers": [{"type": "EBWOID", "value": "EBWOID-DE-1"}]})
    assert client.post(api("/applications"), headers=_h("erika"), json=bad).status_code == 400
    r = client.post(api("/applications"), headers=_h("erika"), json=documents_body(attestation=env.sign()))
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:validation"
    r = client.post(api("/applications"), headers=_h("erika"), json=documents_body())
    assert r.status_code == 201 and r.json()["comparison"] == []
    a = r.json()
    assert {i["source"] for i in a["companyData"]["identifiers"]} == {"APPLICANT"} and a["attestation"] is None
    r = submit(client, a["id"], representationDeclared=True)
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:documents-incomplete"
    assert r.json()["missingDocumentTypes"] == ["COMMERCIAL_REGISTER_EXTRACT"]
    u = upload(client, a["id"])
    assert u.status_code == 201 and u.json()["contentType"] == "application/pdf" and "Location" in u.headers
    assert upload(client, a["id"], content=b"not a pdf").status_code == 400
    monkeypatch.setenv("DOCUMENT_MAX_BYTES", "5")
    assert upload(client, a["id"]).status_code == 400
    monkeypatch.delenv("DOCUMENT_MAX_BYTES")
    for _ in range(9):
        assert upload(client, a["id"]).status_code == 201
    assert upload(client, a["id"]).status_code == 400   # the eleventh
    r = submit(client, a["id"])
    assert r.status_code == 400 and r.json()["representationDeclarationMissing"] is True
    r = submit(client, a["id"], representationDeclared=True)
    assert r.status_code == 200 and r.json()["representationDeclared"] is True


def test_17_documents_disabled(client, env, monkeypatch):
    monkeypatch.setenv("DOCUMENTS_ENABLED", "false")
    r = client.post(api("/applications"), headers=_h("erika"), json=documents_body())
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:documents-disabled"


# ------------------------------------------------------------------------ 18, 19: withdrawal, review status
def test_18_withdraw(client, env):
    aid = created(client, env)["id"]
    r = client.post(api(f"/applications/{aid}/withdraw"), headers=_h("erika"))
    assert r.json()["status"] == "WITHDRAWN" and not events_of("ApplicationWithdrawn")
    aid = created(client, env)["id"]
    submit(client, aid)
    url = api(f"/applications/{aid}/withdraw")
    env.write(env.reviews, [{"applicationId": aid, "status": "APPROVED"}])
    r = client.post(url, headers=_h("erika"))
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m2:problem:already-decided" and r.json()["reviewStatus"] == "APPROVED"
    env.write(env.reviews, "unavailable")
    r = client.post(url, headers=_h("erika"))
    assert r.status_code == 502 and interface.applications[aid]["status"] == "SUBMITTED"
    env.write(env.reviews, [{"applicationId": aid, "status": "OPEN"}])
    assert client.post(url, headers=_h("erika")).json()["status"] == "WITHDRAWN"
    [ev] = events_of("ApplicationWithdrawn")
    assert ev["kind"] == "ONBOARDING" and ev["existingCompany"] is False
    assert client.post(url, headers=_h("erika")).status_code == 200 and len(events_of("ApplicationWithdrawn")) == 1


def test_19_review_status(client, env):
    aid = created(client, env)["id"]
    url = api(f"/applications/{aid}")
    env.write(env.reviews, "unavailable")
    assert client.get(url, headers=_h("erika")).json()["reviewStatus"] == "NONE"   # no request in CREATED
    env.write(env.reviews, [{"applicationId": aid, "status": "OPEN"}])
    submit(client, aid)
    assert client.get(url, headers=_h("erika")).json()["reviewStatus"] == "OPEN"
    env.write(env.reviews, "unavailable")
    r = client.get(url, headers=_h("erika"))
    assert r.status_code == 200 and r.json()["reviewStatus"] == "UNKNOWN"


# ------------------------------------------------------------------------ 20, 21: OSP staff, terms
def test_20_osp_staff(client, env):
    aid = client.post(api("/applications"), headers=_h("erika"), json=documents_body()).json()["id"]
    doc = upload(client, aid).json()["documentId"]
    assert client.get(api("/osp/applications"), headers=_h("rolf")).json()["total"] == 1
    assert client.get(api(f"/osp/applications/{aid}"), headers=_h("rolf")).json()["reviewStatus"] == "NONE"
    r = client.get(api(f"/osp/applications/{aid}/documents/{doc}"), headers=_h("rolf"))
    assert r.status_code == 200 and r.content == PDF and r.headers["x-content-type-options"] == "nosniff"
    assert "attachment" in r.headers["content-disposition"]
    assert any(x["operation"] == "getAnyDocument" and x["objectId"] == doc for x in interface.audit_log)
    assert client.get(api("/osp/applications"), headers=_h("erika")).status_code == 403
    iam = test_iam.iam()
    iam.first_login(NO_PERMISSIONS, "Nora", "Norights", key="norights")   # 14.1, not in testdata/
    iam.users[NO_PERMISSIONS]["roles"].clear()   # the test IAM keeps `Applicant` otherwise
    assert client.get(api(f"/applications/{aid}"), headers=_h("norights")).status_code == 403


def test_21_new_version_of_terms(client, env):
    aid = created(client, env)["id"]
    body = {"agreementKey": "osp-terms", "version": "1.1", "party": "OSP", "scope": "ALL",
            "title": {"de": "Nutzungsbedingungen", "en": "Terms of use"}, "documentUrls": {"en": "https://osp-a.example.org/t.pdf"},
            "reconsentRequired": True, "reconsentDueAt": "2099-01-01T00:00:00Z"}
    r = client.post(api("/osp/agreements"), headers=_h("otto"), json=body)
    assert r.status_code == 201 and r.json()["status"] == "ACTIVE"
    versions = client.get(api("/osp/agreements?agreementKey=osp-terms"), headers=_h("otto")).json()["items"]
    assert {v["version"]: v["status"] for v in versions} == {"1.0": "INACTIVE", "1.1": "ACTIVE"}
    assert events_of("AgreementVersionActivated")[0]["version"] == "1.1"
    r = submit(client, aid)
    assert r.status_code == 400 and r.json()["missing"] == [{"agreementKey": "osp-terms", "version": "1.1"}]
    r = client.post(api("/osp/agreements"), headers=_h("otto"), json=body)
    assert r.status_code == 409 and r.json()["type"] == "urn:c1-m2:problem:conflict"
    assert client.post(api("/osp/agreements"), headers=_h("rolf"), json=body).status_code == 403


# ------------------------------------------------------------------------ 22 to 24: steps, queries
def test_22_complete(client, env):
    aid = created(client, env)["id"]
    with pytest.raises(Problem) as e:
        step(interface.complete_application, aid)
    assert e.value.status == 409 and e.value.body()["retryable"] is False
    submit(client, aid)
    r = step(interface.complete_application, aid)
    assert r["state"] == "DONE" and r["result"]["status"] == "COMPLETED"
    [ev] = events_of("ApplicationCompleted")
    assert ev["kind"] == "ONBOARDING" and ev["applicationId"] == aid
    assert step(interface.complete_application, aid)["state"] == "DONE" and len(events_of("ApplicationCompleted")) == 1
    with pytest.raises(Problem) as e:
        step(interface.complete_application, str(uuid.uuid4()))
    assert e.value.status == 404 and e.value.body()["retryable"] is False


def test_23_close(client, env):
    aid = created(client, env)["id"]
    submit(client, aid)
    assert step(interface.close_application, aid, reason="Register extract too old")["result"]["status"] == "DECLINED"
    assert client.get(api(f"/applications/{aid}"), headers=_h("erika")).json()["declineReason"] == "Register extract too old"
    step(interface.close_application, aid, reason="Another reason")
    assert interface.applications[aid]["declineReason"] == "Register extract too old"
    other = created(client, env)["id"]
    client.post(api(f"/applications/{other}/withdraw"), headers=_h("erika"))
    r = step(interface.close_application, other, reason="x")
    assert r["state"] == "DONE" and r["result"]["status"] == "WITHDRAWN"


def test_24_internal_query(client, env):
    aid = created(client, env)["id"]
    a = interface.get_application_internal(applicationId=aid)
    assert a["attestation"]["signatureCheck"]["result"] == "VALID" and a["applicant"]["sub"] == ERIKA
    assert a["attestation"]["keyId"] == KID and a["requiredAgreements"] == []
    token = test_iam.iam().client_token("svc-c1-m2")
    assert client.get(api(f"/internal/applications/{aid}"), headers=bearer(token)).status_code == 200
    r = client.get(api(f"/internal/applications?applicationId={aid}"), headers=bearer(token))
    assert [x["id"] for x in r.json()] == [aid]
    env.write(env.jwks, {"keys": []})
    attestation.reset()
    assert interface.get_application_internal(applicationId=aid)["attestation"]["signatureCheck"]["result"] == "INVALID"


def test_25_required_terms(client, env):
    r = client.get(api("/agreements?companyRole=ACTIVE_PARTICIPANT"), headers=_h("erika"))
    assert {a["agreementKey"] for a in r.json()} == {"osp-terms", "terms-active-participant", "security-regulations"}
    assert all(a["party"] and a["documentUrls"] for a in r.json())
    assert client.get(api("/agreements?companyRole=OPERATOR"), headers=_h("erika")).status_code == 400
    assert [a["agreementKey"] for a in client.get(api("/agreements"), headers=_h("erika")).json()] == ["osp-terms"]
    assert [c["code"] for c in client.get(api("/countries"), headers=_h("erika")).json()] == ["DE", "US"]
    assert client.get(api("/countries/XX/identifier-types"), headers=_h("erika")).status_code == 404


def test_26_audit_and_no_personal_data(client, env):
    token = env.sign()
    aid = client.post(api("/applications"), headers=_h("erika"), json=onboarding(token)).json()["id"]
    submit(client, aid)
    step(interface.complete_application, aid)
    ops = [(x["operation"], x["sub"], x["companyId"]) for x in interface.audit_log]
    company = interface.applications[aid]["companyId"]
    assert ops == [("createApplication", ERIKA, company), ("submitApplication", ERIKA, company),
                   ("stepCompleteApplication", None, company)]
    text = json.dumps(events.RELAY.log) + json.dumps(interface.audit_log)
    for secret in (token, "Mustermann", "Erika"):
        assert secret not in text
    assert token not in json.dumps(client.get(api(f"/applications/{aid}"), headers=_h("erika")).json())
    assert token not in json.dumps(interface.get_application_internal(applicationId=aid))


# ------------------------------------------------------------- findings of the module review
@pytest.mark.parametrize("change", [{"identifiers": []}, {"identifiers": None}, {"legalName": None}, {"address": None}])
def test_patch_keeps_required_company_data(client, env, change):
    aid = client.post(api("/applications"), headers=_h("erika"), json=documents_body()).json()["id"]
    before = json.dumps(interface.applications[aid]["companyData"])
    r = client.patch(api(f"/applications/{aid}"), headers=_h("erika"), json=change)
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:validation"
    assert json.dumps(interface.applications[aid]["companyData"]) == before


def test_patch_without_identifiers_of_the_person_on_the_ebw_path(client, env):
    aid = created(client, env)["id"]
    r = client.patch(api(f"/applications/{aid}"), headers=_h("erika"), json={"identifiers": []})
    assert r.status_code == 200
    assert {i["type"] for i in r.json()["companyData"]["identifiers"]} == {"EBWOID", "EUID"}


def test_token_with_alg_that_is_not_text(client, env):
    def part(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    token = part({"alg": 123, "typ": "ebw-attestation+jwt", "kid": KID}) + "." + part(env.payload()) + ".AAAA"
    r = client.post(api("/applications"), headers=_h("erika"), json=onboarding(token))
    assert r.status_code == 400 and r.json()["reason"] == "algorithm"


@pytest.mark.parametrize("reference", [{"companyId": "not-a-uuid"}, {"companyId": 12}, {"bpn": "x"}])
def test_reference_in_a_wrong_format(client, env, reference):
    body = {"kind": "REACTIVATION", "verification": "EBW", "attestation": env.sign(company="werkzeugbau")} | reference
    r = client.post(api("/applications"), headers=_h("erika"), json=body)
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:validation"


@pytest.mark.parametrize("over", [
    {"evidence": ["x"]}, {"evidence": [{"type": "PID"}]},
    {"company": {**COMPANIES["maschinenbau"], "country": "DE", "address": "Weg 1"}},
    {"company": {**COMPANIES["maschinenbau"], "country": "DE", "euid": 123}},
    {"representation": {"confirmed": True, "reasons": "x"}}])
def test_signed_attestation_with_malformed_claims(client, env, over):
    r = client.post(api("/applications"), headers=_h("erika"), json=onboarding(env.sign(payload=env.payload() | over)))
    assert r.status_code == 400 and r.json()["reason"] == "claims" and not interface.applications


def test_issuer_not_configured_names_the_variable(client, env, monkeypatch):
    monkeypatch.delenv("ATTESTATION_ISSUER")
    r = client.post(api("/applications"), headers=_h("erika"), json=onboarding(env.sign()))
    assert r.status_code == 502 and "ATTESTATION_ISSUER" in r.json()["detail"]


# ------------------------------------------------------------- findings of the pull request review
def test_postal_code_reported_as_from_attestation_is_stored(client, env):
    address = {"streetName": "Musterstraße", "streetNumber": "1", "city": "Stuttgart", "countryCode": "DE"}
    r = client.post(api("/applications"), headers=_h("erika"), json=onboarding(env.sign(), companyData={"address": address}))
    assert r.status_code == 201
    assert {c["field"]: c["result"] for c in r.json()["comparison"]}["POSTAL_CODE"] == "FROM_ATTESTATION"
    assert r.json()["companyData"]["address"]["postalCode"] == "70569"


def _without_euid(env) -> dict:
    return env.payload(company="maschinenbau") | {"company": {"legal_name": "Beispiel Maschinenbau GmbH",
                                                              "ebwoid": "EBWOID-DE-0000000001", "country": "DE",
                                                              "address": {"street_address": "Musterstraße 1", "postal_code": "70569",
                                                                          "locality": "Stuttgart", "country": "DE"}}}


def test_replacement_checks_the_new_identifiers(client, env):
    body = onboarding(env.sign(payload=_without_euid(env)))
    aid = client.post(api("/applications"), headers=_h("erika"), json=body).json()["id"]
    wrong_country = env.payload() | {"company": {**_without_euid(env)["company"], "euid": "FRXX001T.HRB100001"}}
    r = client.put(api(f"/applications/{aid}/attestation"), headers=_h("erika"), json={"attestation": env.sign(payload=wrong_country)})
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:validation"
    assert [i["type"] for i in interface.applications[aid]["companyData"]["identifiers"]] == ["EBWOID", "VAT_ID"]


def test_replacement_checks_the_existing_company(client, env):
    no_euid = env.payload(company="werkzeugbau")
    no_euid["company"] = {k: v for k, v in no_euid["company"].items() if k != "euid"}
    body = {"kind": "REACTIVATION", "verification": "EBW", "companyId": WERKZEUGBAU, "attestation": env.sign(payload=no_euid)}
    aid = client.post(api("/applications"), headers=_h("erika"), json=body).json()["id"]
    other = env.payload(company="werkzeugbau")
    other["company"] = {**other["company"], "euid": "DEXX001T.HRB999999"}
    r = client.put(api(f"/applications/{aid}/attestation"), headers=_h("erika"), json={"attestation": env.sign(payload=other)})
    assert r.status_code == 400 and r.json()["type"] == "urn:c1-m2:problem:attestation-mismatch" and r.json()["fields"] == ["EUID"]


def test_upload_reads_at_most_the_limit_plus_one_byte(client, env, monkeypatch):
    aid = client.post(api("/applications"), headers=_h("erika"), json=documents_body()).json()["id"]
    monkeypatch.setenv("DOCUMENT_MAX_BYTES", "10")
    seen = []
    original = interface.upload_document

    def recording(application_id, sub, document_type, file_name, content):
        seen.append(len(content))
        return original(application_id, sub, document_type, file_name, content)
    monkeypatch.setattr(interface, "upload_document", recording)
    assert upload(client, aid, content=PDF + b"x" * 1000).status_code == 400
    assert seen == [11]


def _during_submission(env, client, action) -> list:
    """The document request waits for the lock while the application is submitted: the state is read under the lock."""
    outcome = []

    def run():
        try:
            outcome.append(action())
        except Problem as p:
            outcome.append(p)
    return outcome, threading.Thread(target=run)


def test_document_changes_cannot_follow_a_submission(client, env):
    aid = client.post(api("/applications"), headers=_h("erika"), json=documents_body()).json()["id"]
    doc = upload(client, aid).json()["documentId"]
    actions = [lambda: interface.upload_document(aid, ERIKA, "OTHER", "late.pdf", PDF),
               lambda: interface.delete_document(aid, doc, ERIKA)]
    for action in actions:
        interface.applications[aid]["status"] = "CREATED"
        outcome, thread = _during_submission(env, client, action)
        with interface._lock:
            thread.start()
            time.sleep(0.2)
            interface.applications[aid]["status"] = "SUBMITTED"
        thread.join(5)
        assert isinstance(outcome[0], Problem) and outcome[0].status == 409
    assert [d["documentId"] for d in interface.applications[aid]["documents"]] == [doc]
