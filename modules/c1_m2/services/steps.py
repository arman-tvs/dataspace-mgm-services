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
"""Steps for Process Orchestration (README 8): complete-application and close-application."""
from __future__ import annotations

from modules.c1_m2 import errors, store
from modules.c1_m2.errors import MODULE
from modules.c1_m2.services.common import audit, err, now_iso
from portal_common import events


def step_application(input: dict) -> dict:
    a = store.applications.get(input.get("applicationId"))
    if not a:
        raise errors.not_found(retryable=False)
    return a


def step_result(input: dict, a: dict) -> dict:
    return {"stepRunId": input.get("stepRunId"), "state": "DONE",
            "result": {"applicationId": a["id"], "companyId": a["companyId"], "kind": a["kind"], "status": a["status"]}}


def complete_application(input: dict) -> dict:
    with store.lock:
        a = step_application(input)
        if a["status"] == "SUBMITTED":
            now = now_iso()
            a.update(status="COMPLETED", completedAt=now, changedAt=now)
            events.publish(MODULE, "ApplicationCompleted", {"applicationId": a["id"], "companyId": a["companyId"],
                                                            "kind": a["kind"]})
        elif a["status"] != "COMPLETED":
            raise errors.invalid_state(f"application is {a['status']}", retryable=False)
        audit(a, "stepCompleteApplication", step=input)
        return step_result(input, a)


def close_application(input: dict) -> dict:
    reason = input.get("reason")
    if not (isinstance(reason, str) and 1 <= len(reason) <= 1000):
        raise errors.validation([err("reason", "1 to 1000 characters")], retryable=False)
    with store.lock:
        a = step_application(input)
        if a["status"] == "SUBMITTED":
            now = now_iso()
            a.update(status="DECLINED", declineReason=reason, closedAt=now, changedAt=now)
        elif a["status"] not in ("DECLINED", "WITHDRAWN"):
            raise errors.invalid_state(f"application is {a['status']}", retryable=False)
        audit(a, "stepCloseApplication", step=input)
        return step_result(input, a)
