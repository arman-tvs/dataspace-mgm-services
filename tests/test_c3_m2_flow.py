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
"""C3-M2 inside the onboarding flow of the real Process Orchestration (C12-M1 engine, flows.yaml):
register-company answers RUNNING, the CSP's callback completes it, and the flow runs to the end
(README 8.1, 7.2, 13 case 4; FRAMEWORK 5.2). C3-M2 runs in-process, every other module is the
engine's built-in stand-in."""
import datetime as dt

import pytest
from fastapi import FastAPI

from conftest import BASE
from modules.c12_m1 import engine as eng
from modules.c3_m2 import csp_client, interface
from portal_common import events
from portal_common import http as phttp
from tools import test_iam

COMPANY = "c0000001-0000-4000-8000-000000000001"     # Beispiel Maschinenbau GmbH (FRAMEWORK 7a)
APPLICATION = "a0000001-0000-4000-8000-000000000001"  # no 7a ID for applications: C1-M2 assigns it
MASCHINENBAU_BPN = "BPNLIUK2REMLK3F4"                 # 7a


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setenv("MODULE_URLS_DEFAULT", "")      # every neighbour: built-in stand-in of the engine ...
    monkeypatch.setenv("C3_M2_URL", "in-process")      # ... except C3-M2, the module under test
    monkeypatch.setenv("CSP_URL", "")
    monkeypatch.delenv("CSP_STUB_FILE", raising=False)
    iam = FastAPI()
    iam.include_router(test_iam.router)
    phttp.register_local(BASE, iam)
    interface.reset()
    e = eng.reset()
    e.clock = lambda: dt.datetime(2026, 11, 6, 9, 0, tzinfo=dt.UTC)
    events.RELAY.subscribe("c12-m1", eng.on_event)
    yield e
    events.RELAY.clear_subscribers()
    interface.reset()


def event(module, etype, **data):
    return events.cloudevent(module, etype, data, time="2026-11-06T09:30:00Z")


def test_running_step_is_completed_by_the_csp_callback_and_the_flow_continues(engine):
    core = csp_client._builtin_core()
    core.async_operations = True                       # the CSP answers 202 and calls back later
    engine.on_event(event("c1-m2", "ApplicationSubmitted", applicationId=APPLICATION, companyId=COMPANY,
                          kind="ONBOARDING", existingCompany=False, applicantSub="ebw.test-erika"))
    engine.on_event(event("c1-m3", "ApplicationApproved", applicationId=APPLICATION, companyId=COMPANY,
                          kind="ONBOARDING", existingCompany=False))
    proc = next(p for p in engine.processes.values() if p["flowKey"] == "onboarding")
    step = next(s for s in proc["steps"] if s["stepKey"] == "register-company")
    assert step["state"] == "AWAITING_EVENT" and proc["status"] == "RUNNING"
    assert interface.get_csp_registration(companyId=COMPANY)["status"] == "PENDING"

    # the CSP finishes the operation and calls back (README 7.2)
    operation = next(iter(core.operations))
    core.complete_operation(operation)
    interface.receive_csp_notification({"notificationId": "n-1", "type": "OperationCompleted",
                                        "operationId": operation, "outcome": "SUCCEEDED", "bpn": MASCHINENBAU_BPN})
    events.RELAY.drain()

    assert step["state"] == "DONE" and step["result"]["bpn"] == MASCHINENBAU_BPN
    assert proc["status"] == "COMPLETED", {s["stepKey"]: s["state"] for s in proc["steps"]}
    view = interface.get_csp_registration(companyId=COMPANY)
    assert (view["status"], view["membership"]) == ("REGISTERED", "REGISTERED") and view["did"]
    assert dict(engine.call_log)["c3-m1.assign-identifier"]["bpn"] == MASCHINENBAU_BPN
