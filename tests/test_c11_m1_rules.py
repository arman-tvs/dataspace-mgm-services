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
"""C11-M1 rules end to end through `router.on_event` (README 6.2; acceptance 13.5, 13.7, 13.12) and the
task lifecycle of `closing`. Cases 13.1 to 13.4, 13.6 and 13.11 are in `test_c11_m1_engine.py`."""
import datetime as dt

import pytest

from modules.c11_m1 import closing, rules, worker
from modules.c11_m1 import router as c11
from portal_common import events

APPLICATION = "0f8e2d4c-6b1a-4c3e-8f7d-2a9b1c0d3e4f"   # FRAMEWORK 7a
OSP_COMPANY = "11111111-1111-4111-8111-111111111111"   # provider company, README 14
COMPANY = "c0000001-0000-4000-8000-000000000001"       # Beispiel Maschinenbau GmbH, customer, no IT Admin
OTTO = "5a1c0012-0000-4000-8000-000000000012"
ERIKA = "5a1c0001-0000-4000-8000-000000000001"
PROCESS = "22222222-2222-4222-8222-222222222222"
SUBSCRIPTION = "55555555-5555-4555-8555-555555555555"
OFFER = "33333333-3333-4333-8333-333333333333"
CONNECTOR = "66666666-6666-4666-8666-666666666666"
T0, T1, T2 = "2026-11-06T09:30:00Z", "2026-11-06T09:31:00Z", "2026-11-06T09:32:00Z"


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    """conftest does not reset module state; recipients come from the built-in stand-in (README 14)."""
    monkeypatch.delenv("DISABLED_RULES", raising=False)
    monkeypatch.setenv("C2_M2_URL", "")
    c11.reset()
    worker.set_sync(True)
    yield
    c11.reset()


def ev(module: str, etype: str, time: str | None = T0, **data) -> dict:
    return events.cloudevent(module, etype, data, time=time)


def of_type(ntype: str) -> list[dict]:
    return [n for n in c11.notifications if n["type"] == ntype]


def submitted(time: str = T0) -> dict:
    return ev("c1-m2", "ApplicationSubmitted", time, applicationId=APPLICATION, companyId=COMPANY,
              kind="ONBOARDING", existingCompany=False, applicantSub=ERIKA)


def approved(time: str = T1, application: str = APPLICATION) -> dict:
    return ev("c1-m3", "ApplicationApproved", time, applicationId=application, companyId=COMPANY)


def subscription(etype: str, time: str = T0) -> dict:
    return ev("c10-m1", etype, time, offerSubscriptionId=SUBSCRIPTION, offerId=OFFER, offerType="APP",
              instanceKind="SINGLE", customerCompanyId=COMPANY, providerCompanyId=OSP_COMPANY)


def step_failed(time: str) -> dict:
    return ev("c12-m1", "ProcessStepFailed", time, processId=PROCESS, flowKey="onboarding", subjectType="APPLICATION",
              subjectId=APPLICATION, stepKey="register-company", errorType="upstream-error", retryable=True)


def retriggered(time: str, step: str = "register-company") -> dict:
    return ev("c12-m1", "ProcessStepRetriggered", time, processId=PROCESS, stepKey=step, retriggeredBy=OTTO)


# ---- 13.5 subscription task of the provider, closed by the activation

def test_subscription_request_is_a_task_for_the_provider_admin_and_activation_closes_it():
    c11.on_event(subscription("SubscriptionRequested", T0))
    [task] = of_type("SUBSCRIPTION_REQUESTED")
    assert (task["receiverSub"], task["topic"], task["done"]) == (OTTO, "ACTION", False)
    assert (task["subjectType"], task["subjectId"], task["companyId"]) == ("SUBSCRIPTION", SUBSCRIPTION, OSP_COMPANY)

    c11.on_event(subscription("SubscriptionActivated", T1))
    assert task["done"] is True and task["doneAt"] == dt.datetime.fromisoformat(T1).isoformat()
    [info] = of_type("SUBSCRIPTION_ACTIVATED")
    assert (info["receiverSub"], info["topic"], info["done"]) == (ERIKA, "INFO", None)


# ---- 13.7 a closer arrives before the event of its task

def test_earlier_task_event_after_its_closer_is_created_done():
    c11.on_event(approved(T1))
    c11.on_event(submitted(T0))
    [task] = of_type("REVIEW_CASE_OPENED")
    assert task["done"] is True
    assert of_type("APPLICATION_SUBMITTED")[0]["done"] is None   # information never has `done`


def test_task_event_with_equal_time_is_created_done():
    c11.on_event(approved(T0))
    c11.on_event(submitted(T0))
    assert of_type("REVIEW_CASE_OPENED")[0]["done"] is True


def test_later_task_event_after_a_retrigger_stays_open():
    c11.on_event(retriggered(T1))
    c11.on_event(step_failed(T0))   # the failure the retrigger answered, delivered late
    c11.on_event(step_failed(T2))   # a new failure after the retrigger
    assert [n["done"] for n in of_type("PROCESS_STEP_FAILED")] == [True, False]


def test_remembered_closer_also_applies_to_tasks_of_people():
    c11.on_event(subscription("SubscriptionDeclined", T1))
    c11.on_event(subscription("SubscriptionRequested", T0))
    [task] = of_type("SUBSCRIPTION_REQUESTED")
    assert (task["receiverSub"], task["done"]) == (OTTO, True)


def test_closer_of_another_object_neither_closes_nor_is_remembered_for_this_one():
    c11.on_event(submitted(T0))
    c11.on_event(approved(T1, application="99999999-9999-4999-8999-999999999999"))
    assert of_type("REVIEW_CASE_OPENED")[0]["done"] is False
    c11.on_event(retriggered(T1, step="create-wallet"))   # same process, other step
    c11.on_event(step_failed(T0))
    assert of_type("PROCESS_STEP_FAILED")[0]["done"] is False


def test_process_end_closes_every_step_task_of_the_process():
    c11.on_event(step_failed(T0))
    c11.on_event(ev("c12-m1", "ProcessEnded", T1, processId=PROCESS))
    assert of_type("PROCESS_STEP_FAILED")[0]["done"] is True


def test_remembered_closer_is_forgotten_after_24_hours(monkeypatch):
    start = dt.datetime(2026, 11, 6, 9, 31, tzinfo=dt.UTC)
    monkeypatch.setattr(closing, "_now", lambda: start)
    c11.on_event(approved(T1))
    monkeypatch.setattr(closing, "_now", lambda: start + closing.REMEMBER_FOR + dt.timedelta(seconds=1))
    c11.on_event(submitted(T0))
    assert of_type("REVIEW_CASE_OPENED")[0]["done"] is False


def test_a_later_closer_of_the_same_object_outlives_an_expired_one(monkeypatch):
    start = dt.datetime(2026, 11, 6, 9, 31, tzinfo=dt.UTC)
    monkeypatch.setattr(closing, "_now", lambda: start)
    c11.on_event(approved(T2))
    monkeypatch.setattr(closing, "_now", lambda: start + dt.timedelta(hours=23))
    c11.on_event(approved(T1))   # another delivery path, same application, received 23 h later
    monkeypatch.setattr(closing, "_now", lambda: start + dt.timedelta(hours=25))
    c11.on_event(submitted(T0))
    assert of_type("REVIEW_CASE_OPENED")[0]["done"] is True


def test_expired_closers_are_dropped_from_memory(monkeypatch):
    start = dt.datetime(2026, 11, 6, 9, 31, tzinfo=dt.UTC)
    monkeypatch.setattr(closing, "_now", lambda: start)
    for n in range(50):
        c11.on_event(ev("c12-m1", "ProcessCompleted", T1, processId=f"p{n}"))
    assert len(closing._by_key) == 50
    monkeypatch.setattr(closing, "_now", lambda: start + closing.REMEMBER_FOR)
    c11.on_event(ev("c12-m1", "ProcessCompleted", T1, processId="p-new"))
    assert list(closing._by_key) == [("R17", ("processId",), ("p-new",))] and len(closing._expiry) == 1


def test_event_without_time_counts_as_now():
    r2 = next(r for r in rules.RULES if r.id == "R2")
    closer = approved(T1)
    del closer["time"]
    c11.on_event(closer)
    assert closing.closed_before(r2, {"applicationId": APPLICATION}, T0)
    assert not closing.closed_before(r2, {"applicationId": APPLICATION}, "2999-01-01T00:00:00Z")


def test_reset_forgets_remembered_closers():
    c11.on_event(approved(T1))
    c11.reset()
    c11.on_event(submitted(T0))
    assert of_type("REVIEW_CASE_OPENED")[0]["done"] is False


# ---- 13.12 connector of a company without IT Admin

def test_connector_registered_goes_to_the_company_admin_without_it_admin():
    c11.on_event(ev("c6-m1", "ConnectorRegistered", connectorId=CONNECTOR, companyId=COMPANY))
    [info] = of_type("CONNECTOR_REGISTERED")
    assert (info["receiverSub"], info["topic"], info["subjectId"], info["companyId"]) == \
        (ERIKA, "INFO", CONNECTOR, COMPANY)
