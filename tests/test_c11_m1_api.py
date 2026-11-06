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
"""C11-M1 inbox (README 7.1 to 7.5; acceptance 13.8 to 13.10), one section per file: inbox.py, listing.py, marks.py
and the HTTP layer of api.py. The stream of 7.6 (cases 13.13 to 13.16) runs over a real HTTP server
in `test_sse.py`."""
import datetime as dt
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import BASE, bearer, person_token
from modules.c11_m1 import inbox, listing, marks, store, worker
from modules.c11_m1 import router as c11
from portal_common import events, problems, tokens
from portal_common import http as phttp
from portal_common.problems import Problem
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


def submitted() -> dict:
    return events.cloudevent("c1-m2", "ApplicationSubmitted", {
        "applicationId": APPLICATION, "companyId": COMPANY, "kind": "ONBOARDING", "existingCompany": False,
        "applicantSub": test_iam.iam().find("erika")}, time="2026-11-06T09:30:00Z")


def change_request(etype: str = "CompanyChangeRequestSubmitted", **extra) -> dict:
    return events.cloudevent("c3-m1", etype, {"companyId": COMPANY, "changeRequestId": CHANGE_REQUEST} | extra,
                             time="2026-11-06T09:30:00Z")


def claims(sub: str, *perms: str) -> dict:
    """Token claims without HTTP: the `sub` and the permissions of the person."""
    return {"sub": sub, "resource_access": {tokens.AUDIENCE: {"roles": list(perms)}}}


def three_change_requests() -> list[str]:
    """Three R5 tasks for staff with `review_company_changes`, created 09:30, 09:31 and 09:32."""
    for i in range(3):
        c11.on_event(change_request(changeRequestId=str(uuid.UUID(int=i + 1))))
    for i, n in enumerate(store.notifications):   # fixed times make the order deterministic
        n["createdAt"] = f"2026-11-06T09:3{i}:00+00:00"
    return [n["notificationId"] for n in store.notifications]


def of_type(ntype: str) -> dict:
    [n] = [n for n in store.notifications if n["type"] == ntype]
    return n


# ---------------------------------------------------------------- inbox.py: what a person's inbox contains


def applicant() -> dict:
    return claims(test_iam.iam().find("erika"))


def test_personal_notifications_go_to_their_sub_and_staff_ones_to_the_permission():
    c11.on_event(submitted())
    assert [v["type"] for v in inbox.own(applicant())] == ["APPLICATION_SUBMITTED"]
    assert [v["type"] for v in inbox.own(claims("rolf", "review_application"))] == ["REVIEW_CASE_OPENED"]
    assert inbox.own(claims("lieschen")) == []


def test_a_view_is_the_notification_schema_with_read_for_the_caller():
    c11.on_event(submitted())
    n = of_type("APPLICATION_SUBMITTED")
    marks.mark_read(n, applicant()["sub"])
    v = inbox.get(n["notificationId"], applicant())
    assert set(v) == {"notificationId", "type", "topic", "companyId", "subjectType", "subjectId", "content",
                      "forStaff", "read", "done", "createdAt", "doneAt"}   # openapi `Notification`
    assert (v["read"], v["subjectId"], v["companyId"]) == (True, APPLICATION, COMPANY)


def test_hidden_notifications_are_left_out_of_the_own_inbox():
    c11.on_event(submitted())
    n = of_type("APPLICATION_SUBMITTED")
    marks.hide(n, applicant()["sub"])
    assert inbox.own(applicant()) == [] and inbox.get(n["notificationId"], applicant())["notificationId"]


def test_another_persons_notification_is_not_found():
    """Acceptance 13.10."""
    c11.on_event(submitted())
    n = of_type("APPLICATION_SUBMITTED")
    for who in (claims("lieschen"), claims("rolf", "review_application")):
        with pytest.raises(Problem) as e:
            inbox.find(n["notificationId"], who)
        assert (e.value.status, e.value.name) == (404, "not-found")


def test_count_of_the_own_inbox():
    c11.on_event(submitted())
    reviewer = claims("rolf", "review_application")
    assert inbox.count(applicant()) == {"total": 1, "unread": 1, "openTasks": 0, "unreadInfo": 1}
    assert inbox.count(reviewer) == {"total": 1, "unread": 1, "openTasks": 1, "unreadInfo": 0}
    marks.mark_read(of_type("APPLICATION_SUBMITTED"), applicant()["sub"])
    assert inbox.count(applicant()) == {"total": 1, "unread": 0, "openTasks": 0, "unreadInfo": 0}


# ---------------------------------------------------------------- listing.py: the list query


def view(**fields) -> dict:
    """A `Notification` view with the fields the filters read."""
    return {"notificationId": "n", "topic": "INFO", "type": "APPLICATION_SUBMITTED", "read": False, "done": None,
            "createdAt": "2026-11-06T09:30:00+00:00"} | fields


THREE = [view(notificationId=f"n{i}", createdAt=f"2026-11-06T09:3{i}:00+00:00") for i in range(3)]


def everything(*, newest_first: bool, page: int = 0, size: int = 20) -> dict:
    """`THREE` without filters."""
    return listing.list_page(THREE, listing.Filters(), newest_first=newest_first, page=page, size=size)


def ids(page: dict) -> list[str]:
    return [v["notificationId"] for v in page["items"]]


def test_no_filter_matches_everything():
    assert listing.Filters().matches(view())


@pytest.mark.parametrize("filters, match, other", [
    (listing.Filters(topic="ACTION"), view(topic="ACTION", done=False), view()),
    (listing.Filters(ntype="APPLICATION_COMPLETED"), view(type="APPLICATION_COMPLETED"), view()),
    (listing.Filters(read=True), view(read=True), view()),
    (listing.Filters(done=False), view(topic="ACTION", done=False), view(topic="ACTION", done=True)),
])
def test_each_filter_keeps_only_matching_notifications(filters, match, other):
    assert filters.matches(match) and not filters.matches(other)


def test_done_filter_leaves_information_out():
    assert not listing.Filters(done=False).matches(view()) and not listing.Filters(done=True).matches(view())


def test_created_since_includes_its_own_time_and_reads_no_offset_as_utc():
    since = listing.Filters(created_since=dt.datetime(2026, 11, 6, 9, 30))   # no offset: UTC
    assert since.matches(view(createdAt="2026-11-06T09:30:00+00:00"))
    assert not since.matches(view(createdAt="2026-11-06T09:29:59+00:00"))


def test_sorts_newest_first_or_oldest_first():
    assert ids(everything(newest_first=True)) == ["n2", "n1", "n0"]
    assert ids(everything(newest_first=False)) == ["n0", "n1", "n2"]


def test_pages_slice_the_list_and_total_counts_all_matches():
    page = everything(newest_first=False, page=1, size=2)
    assert page == {"items": page["items"], "page": 1, "size": 2, "total": 3} and ids(page) == ["n2"]
    assert everything(newest_first=False, page=5, size=2)["items"] == []


# ---------------------------------------------------------------- marks.py: read and hidden per person


def task() -> dict:
    """The open R5 task for staff with `review_company_changes` (Rolf and Otto)."""
    c11.on_event(change_request())
    return of_type("CHANGE_REQUEST_OPENED")


def test_read_keeps_the_time_of_the_first_read(monkeypatch):
    n = task()
    monkeypatch.setattr(store, "now", lambda: "2026-11-06T10:00:00+00:00")
    marks.mark_read(n, "rolf")
    monkeypatch.setattr(store, "now", lambda: "2026-11-06T11:00:00+00:00")
    marks.mark_read(n, "rolf")
    assert marks.is_read(n, "rolf")
    assert store.state[(n["notificationId"], "rolf")]["readAt"] == "2026-11-06T10:00:00+00:00"


def test_unread_is_idempotent():
    n = task()
    marks.mark_read(n, "rolf")
    marks.mark_unread(n, "rolf")
    marks.mark_unread(n, "rolf")
    assert not marks.is_read(n, "rolf")


def test_state_is_per_person_also_for_staff_notifications():
    """Acceptance 13.9: Rolf reads the task; for Otto it stays unread."""
    n = task()
    marks.mark_read(n, "rolf")
    assert marks.is_read(n, "rolf") and not marks.is_read(n, "otto")


def test_an_open_task_cannot_be_hidden():
    """Acceptance 13.8: 409 `task-open` while the task is open."""
    n = task()
    with pytest.raises(Problem) as e:
        marks.hide(n, "rolf")
    assert (e.value.status, e.value.name) == (409, "task-open") and not marks.is_hidden(n, "rolf")


def test_a_done_task_is_hidden_for_that_person_only():
    n = task()
    c11.on_event(change_request("CompanyChangeRequestClosed", outcome="APPROVED"))
    marks.hide(n, "rolf")
    marks.hide(n, "rolf")
    assert marks.is_hidden(n, "rolf") and not marks.is_hidden(n, "otto")


@pytest.mark.parametrize("topic, done, is_open", [
    ("ACTION", False, True), ("ACTION", True, False), ("INFO", None, False)])
def test_only_a_task_that_is_not_done_is_open(topic, done, is_open):
    assert marks.is_open_task({"topic": topic, "done": done}) is is_open


# ---------------------------------------------------------------- api.py: the HTTP layer


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


def only(client, person: str, ntype: str) -> dict:
    [n] = [n for n in call(client, "GET", "", person).json()["items"] if n["type"] == ntype]
    return n


def test_list_passes_filters_sort_and_paging(client):
    created = three_change_requests()
    params = {"type": "CHANGE_REQUEST_OPENED", "topic": "ACTION", "done": "false", "read": "false",
              "createdSince": "2026-11-06T09:31:00Z", "sort": "createdAt.asc", "page": 0, "size": 1}
    page = call(client, "GET", "", "rolf", params=params).json()
    assert page == {"items": page["items"], "page": 0, "size": 1, "total": 2}
    assert [n["notificationId"] for n in page["items"]] == created[1:2]
    assert call(client, "GET", "", "rolf").json()["size"] == 20   # FRAMEWORK 4.1 default


@pytest.mark.parametrize("params", [{"topic": "TASK"}, {"read": "maybe"}, {"createdSince": "yesterday"},
                                    {"sort": "type"}, {"size": 0}, {"size": 101}, {"page": -1}])
def test_invalid_filter_is_validation_problem(client, params):
    r = call(client, "GET", "", "erika", params=params)
    assert r.status_code == 400 and r.json()["type"] == "urn:c11-m1:problem:validation"


def test_count_get_read_and_unread(client):
    c11.on_event(submitted())
    nid = only(client, "erika", "APPLICATION_SUBMITTED")["notificationId"]
    assert call(client, "GET", "/count", "erika").json() == {"total": 1, "unread": 1, "openTasks": 0, "unreadInfo": 1}
    assert call(client, "POST", f"/{nid}/read", "erika").status_code == 204
    assert call(client, "GET", f"/{nid}", "erika").json()["read"] is True
    assert call(client, "POST", f"/{nid}/unread", "erika").status_code == 204
    assert call(client, "GET", f"/{nid}", "erika").json()["read"] is False


def test_hide_answers_409_problem_for_an_open_task_and_204_when_done(client):
    """Acceptance 13.8."""
    c11.on_event(change_request())
    nid = only(client, "rolf", "CHANGE_REQUEST_OPENED")["notificationId"]
    r = call(client, "POST", f"/{nid}/hide", "rolf")
    assert r.status_code == 409 and r.json()["type"] == "urn:c11-m1:problem:task-open"
    c11.on_event(change_request("CompanyChangeRequestClosed", outcome="APPROVED"))
    assert call(client, "POST", f"/{nid}/hide", "rolf").status_code == 204
    assert call(client, "GET", "", "rolf").json()["total"] == 0


def test_other_persons_notification_is_not_found_and_has_no_names(client):
    """Acceptance 13.10."""
    c11.on_event(submitted())
    nid = only(client, "erika", "APPLICATION_SUBMITTED")["notificationId"]
    for method, path in (("GET", f"/{nid}"), ("POST", f"/{nid}/read"), ("POST", f"/{nid}/unread"),
                         ("POST", f"/{nid}/hide"), ("GET", f"/{uuid.uuid4()}")):
        r = call(client, method, path, "lieschen")
        assert r.status_code == 404 and r.json()["type"] == "urn:c11-m1:problem:not-found"
    text = str(call(client, "GET", f"/{nid}", "erika").json()).lower()
    assert "erika" not in text and "mustermann" not in text


def test_inbox_needs_a_token(client):
    r = client.get(API)
    assert r.status_code == 401 and r.json()["type"] == "urn:c11-m1:problem:unauthorized"
