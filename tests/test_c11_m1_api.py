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
"""C11-M1 inbox API (README 7.1 to 7.5; acceptance 13.8 to 13.10). The stream of 7.6 (cases 13.13 to
13.16) runs over a real HTTP server in `test_sse.py`."""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import BASE, bearer, person_token
from modules.c11_m1 import store, worker
from modules.c11_m1 import router as c11
from portal_common import events, problems
from portal_common import http as phttp
from tools import test_iam

APPLICATION = "0f8e2d4c-6b1a-4c3e-8f7d-2a9b1c0d3e4f"   # FRAMEWORK 7a
COMPANY = "c0000001-0000-4000-8000-000000000001"
CHANGE_REQUEST = "44444444-4444-4444-8444-444444444444"
API = "/api/c11-m1/notifications"


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    """conftest does not reset module state, so every test starts from an empty inbox."""
    monkeypatch.delenv("DISABLED_RULES", raising=False)
    c11.reset()
    worker.set_sync(True)
    yield
    c11.reset()


@pytest.fixture
def client():
    app = FastAPI()
    problems.install(app)
    for r in (test_iam.router, c11.router):
        app.include_router(r)
    phttp.register_local(BASE, app)   # JWKS of the test IAM for the token check
    return TestClient(app, base_url=BASE)


def call(client, method: str, path: str, person: str, **kw):
    return client.request(method, API + path, headers=bearer(person_token(person)), **kw)


def submitted() -> dict:
    return events.cloudevent("c1-m2", "ApplicationSubmitted", {
        "applicationId": APPLICATION, "companyId": COMPANY, "kind": "ONBOARDING", "existingCompany": False,
        "applicantSub": test_iam.iam().find("erika")}, time="2026-11-06T09:30:00Z")


def change_request(etype: str = "CompanyChangeRequestSubmitted", **extra) -> dict:
    return events.cloudevent("c3-m1", etype, {"companyId": COMPANY, "changeRequestId": CHANGE_REQUEST} | extra,
                             time="2026-11-06T09:30:00Z")


def only(client, person: str, ntype: str) -> dict:
    [n] = [n for n in call(client, "GET", "", person).json()["items"] if n["type"] == ntype]
    return n


def test_list_shows_the_own_inbox_with_paging(client):
    c11.on_event(submitted())
    page = call(client, "GET", "", "erika").json()
    assert (page["page"], page["size"], page["total"]) == (0, 20, 1)
    [n] = page["items"]
    assert (n["type"], n["topic"], n["read"], n["done"], n["forStaff"]) == ("APPLICATION_SUBMITTED", "INFO",
                                                                             False, None, False)
    assert n["subjectId"] == APPLICATION and n["content"]["applicationId"] == APPLICATION
    assert call(client, "GET", "", "lieschen").json()["total"] == 0
    [task] = call(client, "GET", "", "rolf").json()["items"]   # staff: review_application (README 4)
    assert (task["type"], task["done"], task["forStaff"]) == ("REVIEW_CASE_OPENED", False, True)


def test_filters_sort_and_pages(client):
    for i in range(3):
        c11.on_event(change_request(changeRequestId=str(uuid.UUID(int=i + 1))))
    for i, n in enumerate(store.notifications):   # fixed times make the order deterministic
        n["createdAt"] = f"2026-11-06T09:3{i}:00+00:00"
    ids = [n["notificationId"] for n in store.notifications]
    desc = call(client, "GET", "", "rolf", params={"size": 2}).json()
    assert [n["notificationId"] for n in desc["items"]] == ids[:0:-1] and desc["total"] == 3
    rest = call(client, "GET", "", "rolf", params={"size": 2, "page": 1, "sort": "createdAt.asc"}).json()
    assert [n["notificationId"] for n in rest["items"]] == ids[2:]
    since = call(client, "GET", "", "rolf", params={"createdSince": "2026-11-06T09:31:00Z"}).json()
    assert since["total"] == 2
    assert call(client, "GET", "", "rolf", params={"topic": "INFO"}).json()["total"] == 0
    assert call(client, "GET", "", "rolf", params={"done": "false", "type": "CHANGE_REQUEST_OPENED"}).json()["total"] == 3


@pytest.mark.parametrize("params", [{"topic": "TASK"}, {"read": "maybe"}, {"createdSince": "yesterday"},
                                    {"sort": "type"}, {"size": 0}, {"size": 101}, {"page": -1}])
def test_invalid_filter_is_validation_problem(client, params):
    r = call(client, "GET", "", "erika", params=params)
    assert r.status_code == 400 and r.json()["type"] == "urn:c11-m1:problem:validation"


def test_read_unread_and_count(client):
    c11.on_event(submitted())
    nid = only(client, "erika", "APPLICATION_SUBMITTED")["notificationId"]
    assert call(client, "GET", "/count", "erika").json() == {"total": 1, "unread": 1, "openTasks": 0, "unreadInfo": 1}
    for _ in range(2):   # idempotent (README 6.4)
        assert call(client, "POST", f"/{nid}/read", "erika").status_code == 204
    assert call(client, "GET", f"/{nid}", "erika").json()["read"] is True
    assert call(client, "GET", "", "erika", params={"read": "false"}).json()["total"] == 0
    assert call(client, "GET", "/count", "erika").json()["unread"] == 0
    assert call(client, "POST", f"/{nid}/unread", "erika").status_code == 204
    assert call(client, "GET", f"/{nid}", "erika").json()["read"] is False


def test_staff_read_state_is_per_person(client):
    """Acceptance 13.9: Rolf and Otto both have `review_company_changes` (R5)."""
    c11.on_event(change_request())
    nid = only(client, "rolf", "CHANGE_REQUEST_OPENED")["notificationId"]
    assert call(client, "POST", f"/{nid}/read", "rolf").status_code == 204
    assert only(client, "rolf", "CHANGE_REQUEST_OPENED")["read"] is True
    assert only(client, "otto", "CHANGE_REQUEST_OPENED")["read"] is False
    assert call(client, "GET", "/count", "otto").json() == {"total": 1, "unread": 1, "openTasks": 1, "unreadInfo": 0}


def test_hide_open_task_conflicts_until_done(client):
    """Acceptance 13.8."""
    c11.on_event(change_request())
    nid = only(client, "rolf", "CHANGE_REQUEST_OPENED")["notificationId"]
    r = call(client, "POST", f"/{nid}/hide", "rolf")
    assert r.status_code == 409 and r.json()["type"] == "urn:c11-m1:problem:task-open"
    c11.on_event(change_request("CompanyChangeRequestClosed", outcome="APPROVED"))
    for _ in range(2):
        assert call(client, "POST", f"/{nid}/hide", "rolf").status_code == 204
    assert call(client, "GET", "", "rolf").json()["total"] == 0
    assert call(client, "GET", "", "otto").json()["total"] == 1   # hidden only for Rolf


def test_other_persons_notification_is_not_found_and_has_no_names(client):
    """Acceptance 13.10."""
    c11.on_event(submitted())
    nid = only(client, "erika", "APPLICATION_SUBMITTED")["notificationId"]
    for method, path in (("GET", f"/{nid}"), ("POST", f"/{nid}/read"), ("POST", f"/{nid}/hide"),
                         ("GET", f"/{uuid.uuid4()}")):
        r = call(client, method, path, "lieschen")
        assert r.status_code == 404 and r.json()["type"] == "urn:c11-m1:problem:not-found"
    text = str(call(client, "GET", f"/{nid}", "erika").json()).lower()
    assert "erika" not in text and "mustermann" not in text


def test_inbox_needs_a_token(client):
    r = client.get(API)
    assert r.status_code == 401 and r.json()["type"] == "urn:c11-m1:problem:unauthorized"
