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
"""C11-M1 event handling (README 6.2, 6.4, acceptance 13.1 to 13.4 and 13.6) through `router.on_event`."""
import threading

import pytest

from modules.c11_m1 import recipients, store, worker
from modules.c11_m1 import router as c11
from portal_common import events, tokens

APPLICATION = "0f8e2d4c-6b1a-4c3e-8f7d-2a9b1c0d3e4f"   # FRAMEWORK 7a
COMPANY = "c0000001-0000-4000-8000-000000000001"     # FRAMEWORK 7a, Beispiel Maschinenbau GmbH
APPLICANT = "5a1c0001-0000-4000-8000-000000000001"   # README 14: the `sub` of Erika; C11-M1 never sees names
PROCESS = "77777777-7777-4777-8777-777777777777"          # IDs below: not in FRAMEWORK 7a
TECHNICAL_USER = "88888888-8888-4888-8888-888888888888"
OFFER = "33333333-3333-4333-8333-333333333333"
SUBSCRIPTION = "55555555-5555-4555-8555-555555555555"
CONNECTOR = "66666666-6666-4666-8666-666666666666"


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    """conftest does not reset module state, so every test starts from an empty inbox."""
    monkeypatch.delenv("DISABLED_RULES", raising=False)
    c11.reset()
    worker.set_sync(True)
    yield
    c11.reset()


def ev(module: str, etype: str, time: str = "2026-11-06T09:30:00Z", **data) -> dict:
    return events.cloudevent(module, etype, data, time=time)


def submitted() -> dict:
    return ev("c1-m2", "ApplicationSubmitted", applicationId=APPLICATION, companyId=COMPANY, kind="ONBOARDING",
              existingCompany=False, applicantSub=APPLICANT)


def of_type(ntype: str) -> list[dict]:
    return [n for n in c11.notifications if n["type"] == ntype]


def claims(sub: str, *perms: str) -> dict:
    return {"sub": sub, "resource_access": {tokens.AUDIENCE: {"roles": list(perms)}}}


def test_submitted_informs_applicant_and_opens_review_task():
    c11.on_event(submitted())
    [info] = of_type("APPLICATION_SUBMITTED")
    assert (info["receiverSub"], info["topic"], info["done"], info["forStaff"]) == (APPLICANT, "INFO", None, False)
    assert (info["subjectType"], info["subjectId"], info["companyId"]) == ("APPLICATION", APPLICATION, COMPANY)
    assert info["content"]["applicationId"] == APPLICATION
    [task] = of_type("REVIEW_CASE_OPENED")
    assert (task["receiverPermission"], task["topic"], task["done"], task["forStaff"]) == \
        ("review_application", "ACTION", False, True)
    reviewer, other = claims("rolf", "review_application"), claims("otto", "retrigger_process_steps")
    assert store.visible_to(task, reviewer) and not store.visible_to(task, other)   # acceptance 1
    assert not store.visible_to(info, reviewer)


def test_same_event_id_twice_creates_no_second_notification():
    event = submitted()
    c11.on_event(event)
    c11.on_event(event)   # at-least-once delivery (README 4, 6.4)
    assert len(c11.notifications) == 2


def test_the_same_id_from_another_source_is_another_event():
    """CloudEvents identify an event by `source` and `id` (FRAMEWORK 6): one module cannot suppress another's."""
    failed = ev("c12-m1", "ProcessStepFailed", processId=PROCESS, stepKey="register-company")
    other = events.cloudevent("c1-m2", "ApplicationSubmitted", submitted()["data"], id=failed["id"])
    c11.on_event(failed)
    c11.on_event(other)
    assert sorted(n["type"] for n in c11.notifications) == \
        ["APPLICATION_SUBMITTED", "PROCESS_STEP_FAILED", "REVIEW_CASE_OPENED"]


def test_a_failing_closing_step_still_applies_the_rules_and_marks_the_event_failed(monkeypatch):
    from modules.c11_m1 import closing

    def broken(event):
        raise RuntimeError("closing broke")
    monkeypatch.setattr(closing, "handle", broken)
    event = submitted()
    c11.on_event(event)
    assert sorted(n["type"] for n in c11.notifications) == ["APPLICATION_SUBMITTED", "REVIEW_CASE_OPENED"]
    assert store.processed[store.event_key(event)]["status"] == "FAILED"


def test_a_failing_applicant_cleanup_is_logged_not_raised():
    c11.on_event(submitted())   # a stored applicant row: dropping a row by an unhashable key then raises
    event = ev("c1-m2", "ApplicationWithdrawn", applicationId={"not": "an id"}, companyId=COMPANY)
    c11.on_event(event)   # dropping the applicant row fails; the relay must not see the error
    assert store.processed[store.event_key(event)]["status"] == "FAILED"


def test_approval_closes_the_review_task_for_everyone():
    c11.on_event(submitted())
    c11.on_event(ev("c1-m3", "ApplicationApproved", applicationId=APPLICATION, companyId=COMPANY))
    [task] = of_type("REVIEW_CASE_OPENED")
    assert task["done"] is True and task["doneAt"]


def test_declined_informs_applicant_with_reason_and_forgets_the_applicant():
    c11.on_event(submitted())
    c11.on_event(ev("c1-m3", "ApplicationDeclined", applicationId=APPLICATION, companyId=COMPANY, reason="incomplete"))
    [info] = of_type("APPLICATION_DECLINED")
    assert info["receiverSub"] == APPLICANT and info["content"]["reason"] == "incomplete"
    assert of_type("REVIEW_CASE_OPENED")[0]["done"] is True
    assert APPLICATION not in store.applicants   # README 5, table `applicant`


def test_step_task_closed_by_retrigger_and_reopened_by_a_new_failure():
    def failed(time):
        return ev("c12-m1", "ProcessStepFailed", time, processId=PROCESS, flowKey="onboarding",
                  subjectType="APPLICATION", subjectId=APPLICATION, stepKey="register-company", errorType="x",
                  retryable=False)
    c11.on_event(failed("2026-11-06T09:30:00Z"))
    c11.on_event(ev("c12-m1", "ProcessStepRetriggered", "2026-11-06T09:31:00Z", processId=PROCESS,
                    stepKey="register-company", retriggeredBy="x"))
    c11.on_event(failed("2026-11-06T09:32:00Z"))   # acceptance 6
    assert [n["done"] for n in of_type("PROCESS_STEP_FAILED")] == [True, False]


def test_disabled_rules_are_skipped(monkeypatch):
    monkeypatch.setenv("DISABLED_RULES", "r14, R2")
    jobs = []
    monkeypatch.setattr(worker, "submit", lambda job, *, label: jobs.append(label))
    c11.on_event(submitted())
    c11.on_event(ev("c4-m2", "WalletAccountCreated", companyId=COMPANY, technicalUserId=TECHNICAL_USER))
    assert [n["type"] for n in c11.notifications] == ["APPLICATION_SUBMITTED"] and jobs == []


def test_company_role_rule_gives_one_personal_notification_per_person(monkeypatch):
    asked = []

    def resolve(kind, data):
        asked.append((kind, data["providerCompanyId"]))
        return ["admin-1", "admin-2", "admin-1"]
    monkeypatch.setattr(recipients, "resolve", resolve)
    c11.on_event(ev("c8-m1", "OfferApproved", offerId=OFFER, providerCompanyId=COMPANY))
    assert asked == [("company_role:providerCompanyId:Company Admin", COMPANY)]
    assert sorted(n["receiverSub"] for n in of_type("OFFER_APPROVED")) == ["admin-1", "admin-2"]


# ---- the real worker thread (README 4); the tests above run it in sync mode

def blocking_resolve(monkeypatch) -> tuple[threading.Event, threading.Event]:
    """Recipient queries wait for `go`, like a slow neighbour; `started` says one is in flight."""
    started, go = threading.Event(), threading.Event()

    def resolve(kind, data):
        started.set()
        go.wait(5)
        return [APPLICANT]
    monkeypatch.setattr(recipients, "resolve", resolve)
    worker.set_sync(False)
    return started, go


def subscription(etype: str, time: str) -> dict:
    return ev("c10-m1", etype, time, offerSubscriptionId=SUBSCRIPTION, offerId=OFFER,
              providerCompanyId=COMPANY, customerCompanyId=COMPANY)


def test_closer_during_a_pending_delivery_creates_the_task_done(monkeypatch):
    started, go = blocking_resolve(monkeypatch)
    stored, add = threading.Event(), store.add_notification

    def add_and_signal(event, rule, **receiver):
        n = add(event, rule, **receiver)
        if rule.id == "R9":
            stored.set()
        return n
    monkeypatch.setattr(store, "add_notification", add_and_signal)
    c11.on_event(subscription("SubscriptionRequested", "2026-11-06T09:30:00Z"))
    assert started.wait(2)   # the recipient query of R9 is in flight in the worker thread
    c11.on_event(subscription("SubscriptionActivated", "2026-11-06T09:31:00Z"))
    go.set()
    assert stored.wait(2)
    assert of_type("SUBSCRIPTION_REQUESTED")[0]["done"] is True   # README 6.2: the remembered closer


def test_reset_stops_the_worker_before_clearing_the_inbox(monkeypatch):
    started, go = blocking_resolve(monkeypatch)
    stop_worker = worker.reset

    def answer_then_stop():
        go.set()   # the neighbour answers while the worker is being stopped
        stop_worker()
    monkeypatch.setattr(worker, "reset", answer_then_stop)
    c11.on_event(ev("c6-m1", "ConnectorRegistered", connectorId=CONNECTOR, companyId=COMPANY))
    assert started.wait(2)
    c11.reset()
    assert c11.notifications == []
