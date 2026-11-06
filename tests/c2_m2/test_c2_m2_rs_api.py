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
#  Assisted-By: GitHub Copilot
#################################################################################
"""Contract and HTTP tests for the C2-M2 public/private API boundary."""
import ast
import os

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from conftest import BASE, bearer, needs_admin_api, person_token
from modules.c2_m2 import interface, router as module_router
from modules.c2_m2.c2_m2_rs_api import contract, create_router, load_contract
from modules.c2_m2.c2_m2_rs_api.apis import PRIVATE_APIS, PUBLIC_APIS, CompanyUsersApi, InvitationAcceptanceApi
from modules.c2_m2.c2_m2_rs_api.sync_openapi import split_contract
from modules.c2_m2.c2_m2_rs_service import main as standalone
from modules.c2_m2.c2_m2_rs_service.producer import private_implementations, public_implementations
from modules.c2_m2.c2_m2_rs_service.producer.impl import CompanyUsersApiImpl
from portal_common import http, spec, tokens
from scaffold.app import create_app, reset_all

API = "/api/c2-m2"
COMPANY = "c0000001-0000-4000-8000-000000000001"
USER = "5a1c0001-0000-4000-8000-000000000001"

needs_database = pytest.mark.skipif(not os.environ.get("DATABASE_URL"),
                                    reason="C2-M2 needs its PostgreSQL: set DATABASE_URL (README 4)")


def operations(document):
    return {
        (path, method): item[method]
        for path, item in document["paths"].items()
        for method in spec.METHODS if method in item
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("C3_M1_URL", "")
    monkeypatch.setenv("C10_M1_URL", "")
    app = create_app()
    http.register_local(BASE, app)
    yield TestClient(app, base_url=BASE)
    reset_all(app.state.entries)


def test_contracts_partition_the_binding_spec_without_drift():
    source = spec.module("c2-m2").document
    public, private = load_contract(public=True), load_contract(public=False)
    assert public == split_contract(source, public=True)
    assert private == split_contract(source, public=False)
    public_ops, private_ops = operations(public), operations(private)
    assert len(public_ops) == 22
    assert len(private_ops) == 14
    assert public_ops.keys().isdisjoint(private_ops)
    assert public_ops | private_ops == operations(source)
    assert set(public["paths"]).isdisjoint(private["paths"])
    assert all(not path.startswith(("/internal/", "/steps/")) for path in public["paths"])
    assert all(path.startswith(("/internal/", "/steps/")) for path in private["paths"])
    assert not any(name.startswith(("Step", "Event")) for name in public["components"]["schemas"])
    assert "EventUserAssignedToCompany" in private["components"]["schemas"]
    for public, interfaces in ((True, PUBLIC_APIS), (False, PRIVATE_APIS)):
        declared = [(e.method, e.path) for api in interfaces for e in api.endpoints().values()]
        assert len(declared) == len(set(declared))
        assert set(declared) == contract.operations(load_contract(public=public)).keys()


@pytest.mark.parametrize("public", [True, False])
def test_contract_references_are_self_contained(public):
    document = load_contract(public=public)

    def check(value):
        if isinstance(value, dict):
            if "$ref" in value:
                assert value["$ref"].startswith("#/")
                target = document
                for part in value["$ref"][2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)

    check(document)


def test_route_registration_and_public_swagger():
    app = FastAPI()
    app.include_router(module_router.public_router)
    routes = [route for route in module_router.router.routes if isinstance(route, APIRoute)]
    assert len(routes) == 36
    for public, router in ((True, module_router.public_router), (False, module_router.private_router)):
        expected = operations(load_contract(public=public))
        actual = {(route.path.removeprefix(API), method.lower()): route
                  for route in router.routes if isinstance(route, APIRoute) for method in route.methods}
        assert actual.keys() == expected.keys()
        for key, route in actual.items():
            assert route.include_in_schema is True
            assert route.operation_id == expected[key]["operationId"]
            declared = {e: name for api in (PUBLIC_APIS if public else PRIVATE_APIS)
                        for name, e in api.endpoints().items()}
            names = [name for e, name in declared.items() if (e.path, e.method.lower()) == key]
            assert names == [route.endpoint.__name__]
            implementation = route.endpoint.implementation.__self__
            assert type(implementation).__module__.startswith("modules.c2_m2.c2_m2_rs_service.producer.impl.")

    document = app.openapi()
    public_contract = load_contract(public=True)
    assert set(document["paths"]) == {API + path for path in public_contract["paths"]}
    assert document["components"]["securitySchemes"]["portalIam"]["scheme"] == "bearer"
    for (path, method), expected in operations(public_contract).items():
        operation = document["paths"][API + path][method]
        assert operation["operationId"] == expected["operationId"]
        assert operation["x-permission"] == expected["x-permission"]
        assert operation["x-permission-scope"] == expected["x-permission-scope"]
        assert operation["security"] == [{"portalIam": []}]
        assert "422" not in operation["responses"]
        params = [(param["in"], param["name"]) for param in operation.get("parameters", [])]
        assert len(params) == len(set(params))
        for status, response in expected["responses"].items():
            assert operation["responses"][status] == contract.resolve(response, public_contract)
        if "requestBody" in expected:
            schema = operation["requestBody"]["content"]["application/json"]["schema"]
            expected_schema = contract.resolve(expected["requestBody"], public_contract)["content"]["application/json"]["schema"]
            for key, value in expected_schema.items():
                assert schema[key] == value
    assert not any(name.startswith(("Step", "Event")) for name in document["components"].get("schemas", {}))


def test_definition_layer_does_not_import_service_implementations():
    for path in contract.DIRECTORY.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any(part in (node.module or "").split(".")
                               for part in ("c2_m2_impl", "c2_m2_rs_service", "module", "interface"))
            elif isinstance(node, ast.Import):
                assert not any(part in alias.name.split(".")
                               for alias in node.names for part in ("c2_m2_impl", "c2_m2_rs_service"))


@pytest.mark.parametrize("public", [True, False])
def test_every_http_endpoint_requires_authentication(client, public):
    for (path, method), operation in operations(load_contract(public=public)).items():
        for name in ("companyId", "userId", "appId", "invitationId", "id"):
            path = path.replace("{" + name + "}", COMPANY if name == "companyId" else USER)
        response = client.request(method.upper(), API + path, json={})
        assert response.status_code == 401, operation["operationId"]
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["type"] == "urn:c2-m2:problem:unauthorized"
        if path.startswith("/steps/"):
            assert "retryable" in response.json()


@needs_database
def test_private_queries_still_work_with_service_tokens_and_reject_people(client):
    response = client.get(API + "/internal/company-users", params={"companyId": COMPANY},
                          headers=bearer(person_token("otto")))
    assert response.status_code == 403
    response = client.get(API + "/internal/company-users", params={"companyId": COMPANY},
                          headers=bearer(tokens.service_token("c11-m1")))
    assert response.status_code == 200
    assert response.json() == []
    response = client.get(API + "/internal/company-users", params={"companyId": "not-a-uuid"},
                          headers=bearer(tokens.service_token("c11-m1")))
    assert response.status_code == 400
    assert response.json()["type"] == "urn:c2-m2:problem:validation"


@needs_database
@needs_admin_api
def test_public_handlers_preserve_scope_validation_and_camel_case(client):
    interface.assign_company_admin({
        "processId": COMPANY, "stepRunId": USER,
        "companyId": COMPANY, "bpn": "BPNLIUK2REMLK3F4", "applicantSub": USER,
    })
    headers = bearer(person_token("erika"))
    response = client.get(API + f"/companies/{COMPANY}/users", headers=headers)
    assert response.status_code == 200
    assert response.json()["items"][0]["userId"] == USER
    assert response.json()["items"][0]["portalRoles"] == ["Company Admin"]
    response = client.get(API + "/companies/c0000002-0000-4000-8000-000000000002/users", headers=headers)
    assert response.status_code == 404
    response = client.post(API + f"/companies/{COMPANY}/invitations", headers=headers,
                           json={"givenName": "Max", "familyName": "Mustermann", "portalRoles": ["Member"]})
    assert response.status_code == 201
    assert len(response.json()["code"]) == 43
    response = client.post(API + f"/companies/{COMPANY}/invitations", headers=headers, json=[])
    assert response.status_code == 400
    assert response.json()["type"] == "urn:c2-m2:problem:validation"


def test_interfaces_are_abstract_definitions_only():
    for api in PUBLIC_APIS + PRIVATE_APIS:
        assert api.endpoints()
        assert set(api.endpoints()) <= api.__abstractmethods__
        with pytest.raises(TypeError):
            api()

    class Partial(CompanyUsersApi):
        def list_company_users(self, companyId, page, size, status, claims):
            return {}

    with pytest.raises(TypeError):
        Partial()


def test_router_rejects_missing_duplicate_foreign_and_mismatched_implementations():
    with pytest.raises(ValueError, match="no implementation for CompanyUsersApi"):
        create_router([], public=True)
    with pytest.raises(ValueError, match="implemented by"):
        create_router((*public_implementations(), CompanyUsersApiImpl()), public=True)
    with pytest.raises(TypeError, match="implements none"):
        create_router((*public_implementations(), object()), public=True)
    with pytest.raises(TypeError, match="implements none"):
        create_router(public_implementations(), public=False)

    class WrongParameters(InvitationAcceptanceApi):
        def accept_invitation(self, payload, claims):
            return {}

    implementations = [i for i in public_implementations() if not isinstance(i, InvitationAcceptanceApi)]
    with pytest.raises(TypeError, match="does not accept the parameters"):
        create_router((*implementations, WrongParameters()), public=True)
    assert len(create_router(private_implementations(), public=False).routes) == 14


def test_scaffold_preserves_complete_api_without_fallback_duplicates(client):
    document = client.get("/openapi.json").json()
    paths = {path for path in document["paths"] if path.startswith(API + "/")}
    assert paths == {API + path for path in spec.module("c2-m2").document["paths"]}
    for path in paths:
        for method in spec.METHODS:
            if method in document["paths"][path]:
                assert "stand-in" not in document["paths"][path][method].get("summary", "")


@needs_database
@needs_admin_api
def test_delete_answers_204_without_body(client):
    interface.assign_company_admin({
        "processId": COMPANY, "stepRunId": USER,
        "companyId": COMPANY, "bpn": "BPNLIUK2REMLK3F4", "applicantSub": USER,
    })
    headers = bearer(person_token("erika"))
    created = client.post(API + f"/companies/{COMPANY}/invitations", headers=headers,
                          json={"givenName": "Max", "familyName": "Mustermann", "portalRoles": ["Member"]}).json()
    response = client.delete(API + f"/companies/{COMPANY}/invitations/{created['id']}", headers=headers)
    assert response.status_code == 204
    assert response.content == b""


def test_standalone_service_serves_both_apis_and_checks_tokens():
    app = standalone.create_app()
    client = TestClient(app, base_url=BASE)   # without `with`: no lifespan, so no database is needed
    assert client.get("/health").json() == {"status": "UP", "module": "c2-m2"}
    paths = {path for path in client.get("/openapi.json").json()["paths"] if path.startswith(API + "/")}
    everything = load_contract(public=True)["paths"] | load_contract(public=False)["paths"]
    assert paths == {API + path for path in everything}
    response = client.get(API + "/osp/users")
    assert (response.status_code, response.json()["type"]) == (401, "urn:c2-m2:problem:unauthorized")
    response = client.get(API + "/osp/users", headers=bearer(person_token("max")))
    assert (response.status_code, response.json()["type"]) == (403, "urn:c2-m2:problem:forbidden")
    response = client.get(API + "/no-such-path")
    assert response.headers["content-type"] == "application/problem+json"
