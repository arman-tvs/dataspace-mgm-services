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
"""C6-M1 Connectors: acceptance cases of README 13 with the test data of README 14 / FRAMEWORK 7a,
over HTTP with person and service tokens, plus the interface functions in-process."""
import threading

import pytest
from conftest import BASE, bearer, person_token
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.c6_m1 import interface
from modules.c6_m1 import router as c6
from portal_common import events, problems, tokens
from portal_common import http as phttp
from tools import test_iam

PROVIDER = "11111111-1111-4111-8111-111111111111"      # company of OSP A, Company Admin pia (FRAMEWORK 7a)
HOST = "c0000001-0000-4000-8000-000000000001"          # Beispiel Maschinenbau GmbH (FRAMEWORK 7a)
TU = "c3d4e5f6-a7b8-4c9d-8e0f-1a2b3c4d5e6f"            # technical user of the host (README 14)
SUB = "d4e5f6a7-b8c9-4d0e-9f1a-2b3c4d5e6f70"           # subscription of a service of the provider (README 14)
ENDPOINT = "https://edc.beispiel-maschinenbau.example/dsp"
OTHER = "c0000002-0000-4000-8000-000000000002"
PROCESS = "9f0e1d2c-3b4a-4c5d-8e6f-7a8b9c0d1e2f"
RUN_1 = "1a2b3c4d-0000-4000-8000-000000000001"
RUN_2 = "1a2b3c4d-0000-4000-8000-000000000002"
BASE_PATH = "/api/c6-m1"


@pytest.fixture
def api(monkeypatch):
    for target in ("C3_M1_URL", "C2_M3_URL", "C10_M1_URL"):   # built-in stand-ins of README 11
        monkeypatch.setenv(target, "")
    app = FastAPI()
    problems.install(app)
    app.include_router(test_iam.router)
    app.include_router(c6.router)
    phttp.register_local(BASE, app)
    c6.reset()
    iam = test_iam.iam()
    iam.bind(iam.find("erika"), HOST, "BPNLIUK2REMLK3F4")
    iam.add_portal_roles(iam.find("erika"), ["Company Admin"])
    iam.bind(iam.find("max"), OTHER, None)
    iam.add_portal_roles(iam.find("max"), ["Company Admin"])
    with TestClient(app, base_url=BASE) as client:
        yield client
    phttp.unregister_local(BASE)


def h(person: str) -> dict:
    return bearer(person_token(person))


def svc(module: str) -> dict:
    return bearer(tokens.service_token(module))


def published(type_: str) -> list[dict]:
    return [e["data"] for e in events.RELAY.log if e["type"] == type_ and e["source"] == "urn:c6-m1"]


def register(api, person="erika", **fields):
    body = {"name": "edc-beispiel", "endpoint": ENDPOINT, "location": "DE"} | fields
    return api.post(f"{BASE_PATH}/connectors", headers=h(person), json=body)


def register_caas(api, person="pia", **fields):
    body = {"name": "edc-service", "endpoint": "https://edc.provider.example/dsp", "location": "DE",
            "offerSubscriptionId": SUB} | fields
    return api.post(f"{BASE_PATH}/connectors/as-a-service", headers=h(person), json=body)


def problem(r, status: int, name: str) -> bool:
    return r.status_code == status and r.json()["type"] == f"urn:c6-m1:problem:{name}"


# ---------------------------------------------------------------- README 13
def test_1_register_company_connector(api):
    r = register(api, technicalUserId=TU)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["status"] == "ACTIVE" and c["type"] == "COMPANY_CONNECTOR" and c["technicalUserId"] == TU
    assert c["providerCompanyId"] == c["hostCompanyId"] == HOST and c["offerSubscriptionId"] is None
    assert published("ConnectorRegistered") == [{"connectorId": c["connectorId"], "companyId": HOST,
                                                 "providerCompanyId": HOST, "type": "COMPANY_CONNECTOR",
                                                 "endpoint": ENDPOINT, "location": "DE"}]
    assert interface.audit[-1]["operation"] == "register-connector" and interface.audit[-1]["companyId"] == HOST


def test_2_duplicate_and_technical_user_in_use(api):
    assert register(api, technicalUserId=TU).status_code == 201
    assert problem(register(api), 409, "duplicate")
    assert problem(register(api, name="edc-2", technicalUserId=TU), 409, "technical-user-not-usable")
    assert len(published("ConnectorRegistered")) == 1


def test_3_host_company_not_active_and_no_bpn_check(api):
    interface.stub_companies[HOST] = "DEACTIVATED"
    assert problem(register(api), 409, "company-not-active")
    interface.stub_companies.pop(HOST)
    iam = test_iam.iam()
    iam.bind(iam.find("erika"), HOST, None)     # ACTIVE company without BPN
    assert register(api).status_code == 201


def test_3b_company_unknown_to_c3_m1_in_process(api, monkeypatch):
    monkeypatch.setenv("C3_M1_URL", "in-process")   # the C3-M1 of this installation does not know HOST
    assert problem(register(api), 409, "company-not-active")


def test_4_connector_as_a_service(api):
    r = register_caas(api)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["type"] == "CONNECTOR_AS_A_SERVICE" and c["providerCompanyId"] == PROVIDER
    assert c["hostCompanyId"] == HOST and c["offerSubscriptionId"] == SUB
    assert published("ConnectorRegistered")[0]["companyId"] == HOST
    # subscription of another provider: the host company is not the provider of the offer
    assert problem(register_caas(api, person="erika", name="x"), 404, "not-found")
    assert problem(register_caas(api, name="edc-other", endpoint="https://b.example/dsp"), 409, "subscription-linked")
    assert problem(register_caas(api, offerSubscriptionId=None), 400, "validation")


def test_5_visibility_for_host_and_others(api):
    con = register_caas(api).json()["connectorId"]
    hosted = api.get(f"{BASE_PATH}/connectors", params={"role": "host"}, headers=h("erika")).json()
    assert [c["connectorId"] for c in hosted["items"]] == [con] and hosted["total"] == 1
    assert api.get(f"{BASE_PATH}/connectors", params={"role": "provider"}, headers=h("erika")).json()["total"] == 0
    assert api.get(f"{BASE_PATH}/connectors/{con}", headers=h("erika")).status_code == 200
    assert problem(api.get(f"{BASE_PATH}/connectors/{con}", headers=h("max")), 404, "not-found")
    assert api.get(f"{BASE_PATH}/connectors", headers=h("max")).json()["total"] == 0


def test_6_change_endpoint_only_by_provider(api):
    con = register_caas(api).json()["connectorId"]
    new = {"endpoint": "https://edc2.provider.example/dsp"}
    assert problem(api.patch(f"{BASE_PATH}/connectors/{con}", headers=h("erika"), json=new), 403, "forbidden")
    r = api.patch(f"{BASE_PATH}/connectors/{con}", headers=h("pia"), json=new)
    assert r.status_code == 200 and r.json()["endpoint"] == new["endpoint"] and r.json()["changedAt"]
    assert published("ConnectorEndpointChanged") == [{"connectorId": con, "companyId": HOST,
                                                      "endpoint": new["endpoint"]}]
    assert api.patch(f"{BASE_PATH}/connectors/{con}", headers=h("pia"), json=new).status_code == 200
    assert len(published("ConnectorEndpointChanged")) == 1     # same value: no change, no event
    assert problem(api.patch(f"{BASE_PATH}/connectors/{con}", headers=h("pia"), json={"endpoint": "http://x"}),
                   400, "validation")


def test_7_delete_with_active_subscription_then_step_8_1(api):
    con = register_caas(api).json()["connectorId"]
    assert problem(api.delete(f"{BASE_PATH}/connectors/{con}", headers=h("pia")), 409, "subscription-active")
    interface.stub_subscriptions[SUB] = interface.stub_subscriptions[SUB] | {"status": "INACTIVE"}
    step = {"processId": PROCESS, "stepRunId": RUN_1, "offerSubscriptionId": SUB}
    r = api.post(f"{BASE_PATH}/steps/deactivate-subscription-connectors", headers=svc("c12-m1"), json=step)
    assert r.status_code == 200 and r.json() == {"stepRunId": RUN_1, "state": "DONE", "result": {"connectorIds": [con]}}
    assert published("ConnectorDeactivated") == [{"connectorId": con, "companyId": HOST}]
    assert api.delete(f"{BASE_PATH}/connectors/{con}", headers=h("pia")).status_code == 204
    assert interface.connectors[con]["status"] == "INACTIVE" and not published("ConnectorDeleted")
    assert len(published("ConnectorDeactivated")) == 1
    # INACTIVE connectors are left out of lists but stay readable
    assert api.get(f"{BASE_PATH}/connectors", headers=h("pia")).json()["total"] == 0
    assert api.get(f"{BASE_PATH}/connectors", params={"status": "INACTIVE"}, headers=h("pia")).json()["total"] == 1
    assert problem(api.patch(f"{BASE_PATH}/connectors/{con}", headers=h("pia"),
                             json={"endpoint": "https://n.example"}), 409, "invalid-state")


def test_8_unlink_technical_user_is_repeatable(api):
    con = register(api, technicalUserId=TU).json()["connectorId"]
    step = {"processId": PROCESS, "stepRunId": RUN_1, "technicalUserId": TU}
    r = api.post(f"{BASE_PATH}/steps/unlink-technical-user", headers=svc("c12-m1"), json=step)
    assert r.json()["result"] == {"connectorIds": [con]} and r.json()["state"] == "DONE"
    assert interface.connectors[con]["technical_user_id"] is None and interface.connectors[con]["status"] == "ACTIVE"
    again = api.post(f"{BASE_PATH}/steps/unlink-technical-user", headers=svc("c12-m1"), json=step | {"stepRunId": RUN_2})
    assert again.json() == {"stepRunId": RUN_2, "state": "DONE", "result": {"connectorIds": []}}


def test_9_internal_query_for_c2_m3(api):
    con = register(api, technicalUserId=TU).json()["connectorId"]
    url = f"{BASE_PATH}/internal/connectors"
    assert api.get(url, params={"technicalUserId": TU}, headers=svc("c2-m3")).json() == [
        {"connectorId": con, "status": "ACTIVE"}]
    assert api.get(url, params={"technicalUserId": OTHER}, headers=svc("c2-m3")).json() == []
    assert api.get(url, params={"technicalUserId": TU}, headers=h("pia")).status_code == 403
    interface.unlink_technical_user({"processId": PROCESS, "stepRunId": RUN_1, "technicalUserId": TU})
    assert api.get(url, params={"technicalUserId": TU}, headers=svc("c2-m3")).json() == []
    assert problem(api.get(url, headers=svc("c2-m3")), 400, "validation")


def test_10_new_connector_for_pending_subscription_after_delete(api):
    interface.stub_subscriptions[SUB] = interface.stub_subscriptions[SUB] | {"status": "PENDING"}
    con = register_caas(api).json()["connectorId"]
    assert api.delete(f"{BASE_PATH}/connectors/{con}", headers=h("pia")).status_code == 204
    assert interface.connectors[con]["status"] == "INACTIVE" and interface.connectors[con]["offer_subscription_id"] == SUB
    assert register_caas(api).status_code == 201       # same name and endpoint: the old one is INACTIVE


def test_11_customer_account_of_the_subscription(api, monkeypatch):
    from modules.c2_m3 import interface as c2_m3
    monkeypatch.setenv("C2_M3_URL", "in-process")
    c2_m3.reset()
    tu = c2_m3.create_for_subscription({"processId": "p", "stepRunId": "s", "offerSubscriptionId": SUB,
                                        "customerCompanyId": HOST, "providerCompanyId": PROVIDER,
                                        "name": "edc", "roles": []})["result"]["accounts"][0]["technicalUserId"]
    # company connector of the customer without offerSubscriptionId: C2-M3 says not usable (account still unlinked)
    assert problem(register(api, name="own", endpoint="https://own.example/dsp", technicalUserId=tu),
                   409, "technical-user-not-usable")
    r = register_caas(api, technicalUserId=tu)
    assert r.status_code == 201, r.text
    c2_m3.reset()


# ---------------------------------------------------------------- further rules
def test_delete_company_connector_removes_it(api):
    con = register(api).json()["connectorId"]
    assert api.delete(f"{BASE_PATH}/connectors/{con}", headers=h("max")).status_code == 404
    assert api.delete(f"{BASE_PATH}/connectors/{con}", headers=h("erika")).status_code == 204
    assert con not in interface.connectors
    assert published("ConnectorDeleted") == [{"connectorId": con, "companyId": HOST}]
    assert problem(api.get(f"{BASE_PATH}/connectors/{con}", headers=h("erika")), 404, "not-found")


@pytest.mark.parametrize("fields", [{"location": "XX"}, {"location": "de"}, {"endpoint": "http://edc.example/dsp"},
                                    {"endpoint": "https://"}, {"name": ""},
                                    {"name": 7}, {"location": None}, {"technicalUserId": "not-a-uuid"}])
def test_invalid_input_is_400(api, fields):
    assert problem(register(api, **fields), 400, "validation")


def test_list_paging_and_filters(api):
    for i in range(3):
        assert register(api, name=f"edc-{i}").status_code == 201
    page = api.get(f"{BASE_PATH}/connectors", params={"size": 2, "page": 1}, headers=h("erika")).json()
    assert page["total"] == 3 and page["page"] == 1 and page["size"] == 2 and len(page["items"]) == 1
    assert api.get(f"{BASE_PATH}/connectors", params={"type": "CONNECTOR_AS_A_SERVICE"},
                   headers=h("erika")).json()["total"] == 0
    assert problem(api.get(f"{BASE_PATH}/connectors", params={"size": 101}, headers=h("erika")), 400, "validation")
    assert problem(api.get(f"{BASE_PATH}/connectors", params={"role": "x"}, headers=h("erika")), 400, "validation")


def test_permissions_and_company_scope(api):
    assert api.get(f"{BASE_PATH}/connectors").status_code == 401
    assert api.get(f"{BASE_PATH}/connectors", headers=h("hans")).status_code == 403    # no company, no role
    assert problem(api.post(f"{BASE_PATH}/steps/unlink-technical-user", headers=h("pia"),
                            json={"processId": PROCESS, "stepRunId": RUN_1, "technicalUserId": TU}), 403, "forbidden")


def test_steps_in_process_validate_and_repeat():
    interface.reset()
    with pytest.raises(problems.Problem) as e:
        interface.deactivate_subscription_connectors({"processId": PROCESS, "stepRunId": RUN_1})
    assert e.value.status == 400 and e.value.ext["retryable"] is False
    first = interface.deactivate_subscription_connectors({"processId": PROCESS, "stepRunId": RUN_1,
                                                          "offerSubscriptionId": SUB})
    assert first == {"stepRunId": RUN_1, "state": "DONE", "result": {"connectorIds": []}}


@pytest.mark.parametrize("step,key", [("deactivate_subscription_connectors", "offerSubscriptionId"),
                                      ("unlink_technical_user", "technicalUserId")])
@pytest.mark.parametrize("missing", ["processId", "stepRunId", "key", "not-uuid"])
def test_steps_require_uuid_identifiers_before_any_change(step, key, missing):
    interface.reset()
    interface.connectors["c"] = {"id": "c", "technical_user_id": TU, "offer_subscription_id": SUB, "status": "ACTIVE"}
    body = {"processId": PROCESS, "stepRunId": RUN_1, key: SUB if key == "offerSubscriptionId" else TU}
    if missing == "not-uuid":
        body[key] = "abc"
    else:
        body.pop(key if missing == "key" else missing)
    with pytest.raises(problems.Problem) as e:
        getattr(interface, step)(body)
    assert e.value.status == 400 and e.value.name == "validation" and e.value.ext["retryable"] is False
    assert interface.connectors["c"]["technical_user_id"] == TU and interface.connectors["c"]["status"] == "ACTIVE"
    interface.reset()


def test_step_without_ids_over_http_is_400(api):
    r = api.post(f"{BASE_PATH}/steps/unlink-technical-user", headers=svc("c12-m1"), json={"technicalUserId": TU})
    assert problem(r, 400, "validation") and r.json()["retryable"] is False


def test_8_1_clears_the_link_of_a_connector_deleted_while_pending(api):
    interface.stub_subscriptions[SUB] = interface.stub_subscriptions[SUB] | {"status": "PENDING"}
    con = register_caas(api, technicalUserId=TU).json()["connectorId"]
    assert api.delete(f"{BASE_PATH}/connectors/{con}", headers=h("pia")).status_code == 204   # INACTIVE, link stays
    assert interface.connectors[con]["technical_user_id"] == TU
    step = {"processId": PROCESS, "stepRunId": RUN_1, "offerSubscriptionId": SUB}            # subscription declined
    r = api.post(f"{BASE_PATH}/steps/deactivate-subscription-connectors", headers=svc("c12-m1"), json=step)
    assert r.json()["result"] == {"connectorIds": [con]} and interface.connectors[con]["technical_user_id"] is None
    assert len(published("ConnectorDeactivated")) == 1          # only the delete changed the status
    again = api.post(f"{BASE_PATH}/steps/deactivate-subscription-connectors", headers=svc("c12-m1"),
                     json=step | {"stepRunId": RUN_2})
    assert again.json()["result"] == {"connectorIds": []} and len(published("ConnectorDeactivated")) == 1


@pytest.mark.parametrize("endpoint", ["https://[", "https://edc.example]/dsp"])
def test_malformed_endpoint_is_400_not_500(api, endpoint):
    assert problem(register(api, endpoint=endpoint), 400, "validation")
    con = register(api).json()["connectorId"]
    assert problem(api.patch(f"{BASE_PATH}/connectors/{con}", headers=h("erika"), json={"endpoint": endpoint}),
                   400, "validation")


def _race(monkeypatch, calls: list) -> list[int]:
    """Runs the calls at the same time; both pass the neighbour checks before either inserts."""
    from modules.c6_m1 import service
    barrier = threading.Barrier(len(calls))
    real = service.company_status

    def slow_company_status(company_id):
        status = real(company_id)
        barrier.wait(timeout=5)       # every request has passed its fail-fast checks
        return status
    monkeypatch.setattr(service, "company_status", slow_company_status)
    results = [None] * len(calls)

    def run(i):
        results[i] = calls[i]()
    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(calls))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_concurrent_registrations_same_name_and_endpoint(api, monkeypatch):
    results = _race(monkeypatch, [lambda: register(api), lambda: register(api)])
    assert sorted(r.status_code for r in results) == [201, 409]
    assert any(problem(r, 409, "duplicate") for r in results)
    assert len(interface.connectors) == 1 and len(published("ConnectorRegistered")) == 1


def test_concurrent_registrations_same_technical_user(api, monkeypatch):
    results = _race(monkeypatch, [lambda: register(api, name="a", technicalUserId=TU),
                                  lambda: register(api, name="b", technicalUserId=TU)])
    assert sorted(r.status_code for r in results) == [201, 409]
    assert any(problem(r, 409, "technical-user-not-usable") for r in results)
    assert len(interface.connectors) == 1


def test_concurrent_registrations_same_subscription(api, monkeypatch):
    results = _race(monkeypatch, [lambda: register_caas(api, name="a", endpoint="https://a.example/dsp"),
                                  lambda: register_caas(api, name="b", endpoint="https://b.example/dsp")])
    assert sorted(r.status_code for r in results) == [201, 409]
    assert any(problem(r, 409, "subscription-linked") for r in results)
    assert len(interface.connectors) == 1


def test_concurrent_endpoint_change_and_registration(api, monkeypatch):
    con = register(api, name="edc", endpoint="https://old.example/dsp").json()["connectorId"]
    from modules.c6_m1 import service
    barrier = threading.Barrier(2)
    real = service.company_status

    def slow(company_id):
        status = real(company_id)
        barrier.wait(timeout=5)
        return status
    monkeypatch.setattr(service, "company_status", slow)
    out = {}

    def reg():
        out["reg"] = register(api, name="edc", endpoint="https://new.example/dsp")

    def patch():
        barrier.wait(timeout=5)       # the registration has passed its fail-fast checks
        out["patch"] = api.patch(f"{BASE_PATH}/connectors/{con}", headers=h("erika"),
                                 json={"endpoint": "https://new.example/dsp"})
    threads = [threading.Thread(target=reg), threading.Thread(target=patch)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # whichever runs first wins; the other sees it and answers 409 duplicate
    assert sorted([out["reg"].status_code, out["patch"].status_code]) in ([200, 409], [201, 409])
    assert problem(out["reg"] if out["reg"].status_code == 409 else out["patch"], 409, "duplicate")
    live = [(c["name"], c["endpoint"]) for c in interface.connectors.values() if c["status"] == "ACTIVE"]
    assert len(live) == len(set(live))


def test_endpoint_with_user_information_is_400_and_not_echoed(api):
    secret_url = "https://user:s3cret@edc.example/dsp"
    r = register(api, endpoint=secret_url)
    assert problem(r, 400, "validation") and "s3cret" not in r.text
    assert not published("ConnectorRegistered")
    con = register(api).json()["connectorId"]
    r = api.patch(f"{BASE_PATH}/connectors/{con}", headers=h("erika"), json={"endpoint": secret_url})
    assert problem(r, 400, "validation") and "s3cret" not in r.text and not published("ConnectorEndpointChanged")


@pytest.mark.parametrize("endpoint", ["https://:443/dsp", "https://edc.example:invalid/dsp"])
def test_endpoint_without_hostname_or_with_invalid_port_is_400(api, endpoint):
    assert problem(register(api, endpoint=endpoint), 400, "validation")


def test_no_connector_for_a_subscription_after_step_8_1(api):
    interface.stub_subscriptions[SUB] = interface.stub_subscriptions[SUB] | {"status": "PENDING"}   # read before decline
    step = {"processId": PROCESS, "stepRunId": RUN_1, "offerSubscriptionId": SUB}
    r = api.post(f"{BASE_PATH}/steps/deactivate-subscription-connectors", headers=svc("c12-m1"), json=step)
    assert r.json()["result"] == {"connectorIds": []}
    assert problem(register_caas(api), 409, "invalid-state")
    assert not interface.connectors and not published("ConnectorRegistered")


def test_internal_query_rejects_a_technical_user_id_that_is_no_uuid(api):
    r = api.get(f"{BASE_PATH}/internal/connectors", params={"technicalUserId": "not-a-uuid"}, headers=svc("c2-m3"))
    assert problem(r, 400, "validation")


def test_delete_asks_c10_m1_outside_the_lock(api, monkeypatch):
    from modules.c6_m1 import service
    con = register_caas(api).json()["connectorId"]
    interface.stub_subscriptions[SUB] = interface.stub_subscriptions[SUB] | {"status": "INACTIVE"}
    asked, release = threading.Event(), threading.Event()
    real = service.subscription

    def slow_subscription(sub_id):
        asked.set()
        release.wait(timeout=5)       # a slow C10-M1
        return real(sub_id)
    monkeypatch.setattr(service, "subscription", slow_subscription)
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("delete", api.delete(f"{BASE_PATH}/connectors/{con}",
                                                                            headers=h("pia"))))
    t.start()
    assert asked.wait(timeout=5)
    acquired = interface.LOCK.acquire(timeout=1)   # other requests are not blocked meanwhile
    if acquired:
        interface.LOCK.release()
    release.set()
    t.join()
    assert acquired and out["delete"].status_code == 204 and interface.connectors[con]["status"] == "INACTIVE"


def test_no_link_to_a_technical_user_after_step_8_2(api):
    step = {"processId": PROCESS, "stepRunId": RUN_1, "technicalUserId": TU}   # deleted in C2-M3, no connector yet
    assert api.post(f"{BASE_PATH}/steps/unlink-technical-user", headers=svc("c12-m1"), json=step).json()["result"] == {
        "connectorIds": []}
    assert problem(register(api, technicalUserId=TU), 409, "technical-user-not-usable")
    assert problem(register(api, technicalUserId=TU.upper()), 409, "technical-user-not-usable")
    assert not interface.connectors


def test_uuid_casing_does_not_matter(api):
    con = register(api, technicalUserId=TU.upper()).json()
    assert con["technicalUserId"] == TU
    assert problem(register(api, name="second", technicalUserId=TU), 409, "technical-user-not-usable")
    url = f"{BASE_PATH}/internal/connectors"
    assert api.get(url, params={"technicalUserId": TU.upper()}, headers=svc("c2-m3")).json() == [
        {"connectorId": con["connectorId"], "status": "ACTIVE"}]
    assert api.get(f"{BASE_PATH}/connectors/{con['connectorId'].upper()}", headers=h("erika")).status_code == 200
    step = {"processId": PROCESS, "stepRunId": RUN_1, "technicalUserId": TU.upper()}
    r = api.post(f"{BASE_PATH}/steps/unlink-technical-user", headers=svc("c12-m1"), json=step)
    assert r.json()["result"] == {"connectorIds": [con["connectorId"]]}


def test_subscription_id_casing_does_not_matter(api):
    assert register_caas(api, offerSubscriptionId=SUB.upper()).json()["offerSubscriptionId"] == SUB
    assert problem(register_caas(api, name="b", endpoint="https://b.example/dsp"), 409, "subscription-linked")
