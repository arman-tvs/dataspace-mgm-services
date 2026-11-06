#################################################################################
#  Copyright (c) 2026 Technovative Solutions
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
"""C3-M2 CSP Connection over HTTP: tokens and permissions of openapi.yaml, and the shared CSP
stand-in at `CSP_URL` (README 13 cases 4, 9 and 10)."""
import json
import uuid

import jwt
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from conftest import BASE, bearer, person_token
from modules.c3_m2 import interface, router, store
from portal_common import csp as csp_client
from portal_common import events
from portal_common import http as phttp
from portal_common.problems import Problem
from portal_common.standin import derive_bpn
from tools import test_iam
from tools.csp_standin.app import create_app as create_csp
from tools.keys import ec_jwk

CSP = "http://csp.test"
OSP_A, OSP_B = "22222222-2222-4222-8222-222222222222", "99a5685c-7397-402c-88de-b1b3a939ecc9"
OSP_COMPANY, OSP_COMPANY_BPN = "11111111-1111-4111-8111-111111111111", "BPNL00000000OSPA"
EBWOID = "EBWOID-DE-0000000001"
CONNECTOR, ENDPOINT = "7c1e5a2b-4d3f-4e6a-9b8c-0d1e2f3a4b5c", "https://edc.beispiel-maschinenbau.example/dsp"
COMPANY = "c0000001-0000-4000-8000-000000000001"    # Beispiel Maschinenbau GmbH (FRAMEWORK 7a)


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("CSP_URL", "")
    monkeypatch.delenv("CSP_STUB_FILE", raising=False)
    interface.reset()
    app = FastAPI()
    app.include_router(test_iam.router)   # the Portal IAM of OSP A: token endpoint and JWKS
    app.include_router(router.router)
    phttp.register_local(BASE, app)
    yield TestClient(app, base_url=BASE)
    interface.reset()


@pytest.fixture
def shared_csp(tmp_path, monkeypatch):
    """The shared CSP stand-in of the test tools at `CSP_URL`, with OSP A and OSP B in the trust list."""
    keys = {OSP_A: ec_jwk("osp-a"), OSP_B: ec_jwk("osp-b")}
    trust = {osp: {"name": name, "installationUrl": url, "jwk": keys[osp][1], "iamTokenUrl": f"{url}/token"}
             for osp, name, url in ((OSP_A, "OSP A", BASE), (OSP_B, "OSP B", "http://osp-b.test"))}
    (tmp_path / "trust.json").write_text(json.dumps(trust))
    (tmp_path / "osp-a-key.json").write_text(json.dumps(keys[OSP_A][0]))
    monkeypatch.setenv("CSP_TRUST_FILE", str(tmp_path / "trust.json"))
    monkeypatch.setenv("CSP_PUBLIC_URL", CSP)
    monkeypatch.setenv("CSP_CALLBACK_DELAY_SECONDS", "3600")   # callbacks are posted by the test itself
    monkeypatch.setenv("CSP_URL", f"{CSP}/v1")
    monkeypatch.setenv("CSP_TOKEN_URL", f"{CSP}/oauth/token")
    monkeypatch.setenv("OSP_SIGNING_KEY_FILE", str(tmp_path / "osp-a-key.json"))
    monkeypatch.setenv("CSP_JWKS_URL", f"{CSP}/.well-known/jwks.json")
    csp_client.reset()
    app = create_csp()
    phttp.register_local(CSP, app)
    interface.reset()
    yield {"client": TestClient(app, base_url=CSP), "public_key": keys[OSP_A][1]}
    phttp.unregister_local(CSP)
    csp_client.reset()


def service(client_id: str) -> dict:
    return bearer(test_iam.iam().client_token(client_id))


def step(**fields) -> dict:
    return {"processId": str(uuid.uuid4()), "stepRunId": str(uuid.uuid4()), "companyId": COMPANY} | fields


def maschinenbau(**fields) -> dict:
    return step(legalName="Beispiel Maschinenbau GmbH", country="DE", ebwoid=EBWOID) | fields


def published(type_: str) -> list[dict]:
    return [e["data"] for e in events.RELAY.log if e["type"] == type_ and e["source"] == "urn:c3-m2"]


# ---------------------------------------------------------------- tokens and permissions
def test_steps_over_http_need_execute_steps(api):
    assert api.post("/api/c3-m2/steps/register-company", json=maschinenbau()).status_code == 401
    r = api.post("/api/c3-m2/steps/register-company", json=maschinenbau(), headers=bearer(person_token("lieschen")))
    assert r.status_code == 403 and r.json()["type"] == "urn:c3-m2:problem:forbidden"
    r = api.post("/api/c3-m2/steps/register-company", json=maschinenbau(), headers=service("svc-c12-m1"))
    assert r.status_code == 200 and r.json()["result"]["bpn"] == derive_bpn(EBWOID)


def test_step_validation_is_400_problem(api):
    r = api.post("/api/c3-m2/steps/register-company", json=step(legalName="X", country="DE"),
                 headers=service("svc-c12-m1"))
    assert r.status_code == 400
    assert r.json()["type"] == "urn:c3-m2:problem:validation" and r.json()["retryable"] is False


def test_find_companies_over_http(api):
    api.post("/api/c3-m2/steps/register-company", json=maschinenbau(), headers=service("svc-c12-m1"))
    r = api.get("/api/c3-m2/internal/find-companies", params={"ebwoid": EBWOID}, headers=service("svc-c1-m3"))
    assert r.status_code == 200 and r.json()[0]["homeIsThisOsp"] is True
    r = api.get("/api/c3-m2/internal/find-companies", headers=service("svc-c1-m3"))
    assert r.status_code == 400


def test_status_for_osp_admin(api):
    r = api.get(f"/api/c3-m2/companies/{OSP_COMPANY}", headers=bearer(person_token("otto")))
    assert r.status_code == 200 and r.json()["bpn"] == OSP_COMPANY_BPN and r.json()["status"] == "REGISTERED"
    assert api.get(f"/api/c3-m2/companies/{COMPANY}", headers=bearer(person_token("otto"))).status_code == 404
    assert api.get(f"/api/c3-m2/companies/{OSP_COMPANY}", headers=bearer(person_token("lieschen"))).status_code == 403


def test_9_notification_needs_report_csp_notification(api):
    note = {"notificationId": "n1", "type": "CompanyTransferredAway", "bpn": OSP_COMPANY_BPN}
    r = api.post("/api/c3-m2/csp-notifications", json=note, headers=service("svc-c12-m1"))
    assert r.status_code == 403
    assert interface.get_csp_registration(companyId=OSP_COMPANY)["status"] == "REGISTERED"
    r = api.post("/api/c3-m2/csp-notifications", json={"type": "CompanyTransferredAway"}, headers=service("sa-csp"))
    assert r.status_code == 400


# ---------------------------------------------------------------- shared CSP stand-in
def test_4_running_then_callback_completes_once(api, shared_csp):
    shared_csp["client"].put("/admin/config", json={"asyncOperations": True})
    r = api.post("/api/c3-m2/steps/register-company", json=maschinenbau(), headers=service("svc-c12-m1"))
    assert r.status_code == 200 and r.json()["state"] == "RUNNING"
    again = api.post("/api/c3-m2/steps/register-company", json=maschinenbau(), headers=service("svc-c12-m1"))
    assert again.json()["state"] == "RUNNING"
    assert sum(1 for a in store.audit if a.operation == "register-company") == 1   # no second operation
    operation = store.registrations[COMPANY].pending_operation_id
    bpn = derive_bpn(EBWOID)
    note = {"notificationId": str(uuid.uuid4()), "type": "OperationCompleted", "operationId": operation,
            "outcome": "SUCCEEDED", "bpn": bpn}
    for _ in range(2):
        r = api.post("/api/c3-m2/csp-notifications", json=note, headers=service("sa-csp"))
        assert r.status_code == 200
    assert interface.get_csp_registration(companyId=COMPANY)["status"] == "REGISTERED"
    assert published("CompanyRegisteredAtCsp") == [{"companyId": COMPANY, "bpn": bpn}]


def test_operation_failed_by_callback(api, shared_csp):
    shared_csp["client"].put("/admin/config", json={"asyncOperations": True})
    api.post("/api/c3-m2/steps/register-company", json=maschinenbau(), headers=service("svc-c12-m1"))
    operation = store.registrations[COMPANY].pending_operation_id
    note = {"notificationId": "n-failed", "type": "OperationCompleted", "operationId": operation, "outcome": "FAILED",
            "reason": "REJECTED_BY_CSP"}
    assert api.post("/api/c3-m2/csp-notifications", json=note, headers=service("sa-csp")).status_code == 200
    assert interface.get_csp_registration(companyId=COMPANY)["failureReason"] == "REJECTED_BY_CSP"
    assert published("CompanyRegistrationAtCspFailed") == [{"companyId": COMPANY, "reason": "REJECTED_BY_CSP"}]


def test_9_csp_not_reachable_is_retryable(api, monkeypatch, tmp_path):
    (tmp_path / "key.json").write_text(json.dumps(ec_jwk("osp-a")[0]))
    down = FastAPI()

    @down.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def unavailable(path: str):
        return JSONResponse({"title": "maintenance"}, status_code=503)

    phttp.register_local("http://csp-down.test", down)
    monkeypatch.setenv("CSP_URL", "http://csp-down.test/v1")
    monkeypatch.setenv("CSP_TOKEN_URL", "http://csp-down.test/oauth/token")
    monkeypatch.setenv("OSP_SIGNING_KEY_FILE", str(tmp_path / "key.json"))
    csp_client.reset()
    try:
        r = api.post("/api/c3-m2/steps/register-company", json=maschinenbau(), headers=service("svc-c12-m1"))
    finally:
        phttp.unregister_local("http://csp-down.test")
    assert r.status_code == 502
    assert r.json()["type"] == "urn:c3-m2:problem:upstream-error" and r.json()["retryable"] is True
    assert COMPANY not in store.registrations or store.registrations[COMPANY].status is None


def test_missing_signing_key_is_retryable_upstream_error(api, monkeypatch):
    monkeypatch.setenv("CSP_URL", "http://csp-down.test/v1")
    monkeypatch.setenv("CSP_TOKEN_URL", "http://csp-down.test/oauth/token")
    monkeypatch.setenv("OSP_SIGNING_KEY_FILE", "/nonexistent/key.json")
    csp_client.reset()
    r = api.post("/api/c3-m2/steps/register-company", json=maschinenbau(), headers=service("svc-c12-m1"))
    assert r.status_code == 502 and r.json()["retryable"] is True
    assert "/nonexistent" not in r.text


def test_10_client_assertion_signed_with_the_osp_key(shared_csp):
    r = interface.register_company(maschinenbau())   # accepted by the CSP: the assertion was valid
    assert r["result"]["bpn"] == derive_bpn(EBWOID)
    assertion = csp_client.client_assertion(f"{CSP}/oauth/token")
    claims = jwt.decode(assertion, jwt.PyJWK(shared_csp["public_key"]).key, algorithms=["ES256"],
                        audience=f"{CSP}/oauth/token")
    assert claims["iss"] == claims["sub"] == OSP_A


def test_13_osp_company_connector_at_the_shared_csp(shared_csp):
    r = interface.register_connector(step(companyId=OSP_COMPANY, connectorId=CONNECTOR, endpointUrl=ENDPOINT))
    assert r["result"] == {"bpn": OSP_COMPANY_BPN, "connectorId": CONNECTOR}
    discovery = shared_csp["client"].get("/admin/companies").json()
    osp = next(c for c in discovery if c["bpn"] == OSP_COMPANY_BPN)
    assert osp["connectors"] == {CONNECTOR: ENDPOINT}



# ---------------------------------------------------------------- API contract (schemas.py = openapi.yaml)
def test_body_schema_errors_are_400_problems_with_the_field(api):
    r = api.post("/api/c3-m2/steps/register-company", json=maschinenbau(country="de"), headers=service("svc-c12-m1"))
    assert r.status_code == 400
    body = r.json()
    assert body["type"] == "urn:c3-m2:problem:validation" and body["retryable"] is False
    assert [e["field"] for e in body["errors"]] == ["body.country"]
    r = api.post("/api/c3-m2/steps/register-did", json=step(), headers=service("svc-c12-m1"))
    assert r.status_code == 400 and [e["field"] for e in r.json()["errors"]] == ["body.did"]
    r = api.post("/api/c3-m2/steps/register-membership", json={"companyId": "not-a-uuid"},
                 headers=service("svc-c12-m1"))
    assert r.status_code == 400
    assert {e["field"] for e in r.json()["errors"]} == {"body.processId", "body.stepRunId", "body.companyId"}


def test_openapi_shows_the_contract_of_the_spec(api):
    doc = api.app.openapi()
    op = doc["paths"]["/api/c3-m2/steps/register-company"]["post"]
    assert op["operationId"] == "stepRegisterCompany"
    ref = op["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema = doc["components"]["schemas"][ref.rsplit("/", 1)[1]]
    assert {"processId", "stepRunId", "companyId", "legalName", "country"} <= set(schema["required"])
    assert {"ebwoid", "euid", "identifiers", "address"} <= set(schema["properties"])
    result = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert result.endswith("/StepResult")


def test_running_step_answer_matches_step_result(api, shared_csp):
    shared_csp["client"].put("/admin/config", json={"asyncOperations": True})
    r = api.post("/api/c3-m2/steps/register-company", json=maschinenbau(), headers=service("svc-c12-m1"))
    assert r.status_code == 200 and r.json()["state"] == "RUNNING"
    assert set(r.json()) <= {"stepRunId", "state", "result"}


# ---------------------------------------------------------------- second review (review-module, 2026-11-06)
def test_incomplete_csp_match_is_502_not_500_over_http(api, monkeypatch):
    from modules.c3_m2 import csp_client
    monkeypatch.setattr(csp_client, "call", lambda *a, **k: (200, [{
        "bpn": "BPNL00000000002B", "legalName": None, "country": "DE", "matchedBy": "EBWOID", "homeOspId": OSP_B}]))
    r = api.get("/api/c3-m2/internal/find-companies", params={"ebwoid": "EBWOID-DE-0000000002"},
                headers=service("svc-c1-m3"))
    assert r.status_code == 502
    assert r.json()["type"] == "urn:c3-m2:problem:upstream-error" and r.json()["retryable"] is True


def test_malformed_company_id_is_400_validation(api):
    r = api.get("/api/c3-m2/companies/not-a-uuid", headers=bearer(person_token("otto")))
    assert r.status_code == 400
    assert r.json()["type"] == "urn:c3-m2:problem:validation"
    assert [e["field"] for e in r.json()["errors"]] == ["path.companyId"]


# ---------------------------------------------------------------- independent review (review-module, 2026-11-06)
def test_a_rejected_csp_token_is_replaced_for_the_retry(shared_csp):
    """README 4 and 12: a 401 is retryable, so the retry must not send the same rejected token again."""
    interface.register_company(maschinenbau())                       # fetches and caches a valid token
    token_url = f"{CSP}/oauth/token"
    csp_client._token[token_url] = ("rejected-token", 4102444800.0)   # the CSP no longer accepts it
    with pytest.raises(Problem) as e:
        interface.register_membership(step())
    assert (e.value.status, e.value.name, e.value.ext["retryable"]) == (502, "upstream-error", True)
    assert interface.register_membership(step())["state"] == "DONE"   # the retry of C12 works
    assert csp_client._token[token_url][0] != "rejected-token"


def test_unusable_signing_key_is_502_upstream_error(api, shared_csp, tmp_path, monkeypatch):
    """OPEN-QUESTIONS 11: a key file that is JSON but no usable key is no token for the CSP."""
    (tmp_path / "half-key.json").write_text(json.dumps({"kty": "EC", "crv": "P-256"}))
    monkeypatch.setenv("OSP_SIGNING_KEY_FILE", str(tmp_path / "half-key.json"))
    csp_client.reset()
    r = api.post("/api/c3-m2/steps/register-company", json=maschinenbau(), headers=service("svc-c12-m1"))
    assert r.status_code == 502
    assert r.json()["type"] == "urn:c3-m2:problem:upstream-error" and r.json()["retryable"] is True
    assert "half-key" not in r.text



# ---------------------------------------------------------------- team review (2026-11-06)
def test_broken_stub_file_is_502_not_500_over_http(api, tmp_path, monkeypatch):
    (tmp_path / "bad-stub.json").write_text("{not json")
    monkeypatch.setenv("CSP_STUB_FILE", str(tmp_path / "bad-stub.json"))
    interface.reset()
    r = api.post("/api/c3-m2/steps/register-company", json=maschinenbau(), headers=service("svc-c12-m1"))
    assert r.status_code == 502
    assert r.json()["type"] == "urn:c3-m2:problem:upstream-error" and r.json()["retryable"] is True
    assert str(tmp_path) not in r.text
