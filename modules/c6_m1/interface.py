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
"""Public interface of C6-M1 Connectors: the register of the connectors of the companies of this
installation (README 5), the steps for Process Orchestration (README 8) and the query for C2-M3
(README 9). In memory for the hackathon (README 4 names an own database `c6_m1`; OPEN-QUESTIONS.md).

The operations of people (README 7) are in `service.py`; `router.py` is the HTTP layer.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
import uuid
from pathlib import Path

from portal_common import events, standin
from portal_common.problems import Problem

MODULE = "c6-m1"
HERE = Path(__file__).resolve().parent

ACTIVE, INACTIVE = "ACTIVE", "INACTIVE"
COMPANY_CONNECTOR, CONNECTOR_AS_A_SERVICE = "COMPANY_CONNECTOR", "CONNECTOR_AS_A_SERVICE"

# One lock for every change of the register: the uniqueness checks of README 5 and the change that
# follows them run as one unit, so that of two concurrent requests the second sees the first (409).
LOCK = threading.RLock()

connectors: dict[str, dict] = {}     # connectorId -> row of table `connector` (README 5)
audit: list[dict] = []               # table `audit_entry` (FRAMEWORK 4.3)
stub_companies: dict[str, str] = {}          # built-in stand-in of C3-M1: companyId -> status (README 11)
stub_subscriptions: dict[str, dict] = {}     # built-in stand-in of C10-M1: offerSubscriptionId -> subscription


def _load(name: str) -> dict:
    path = HERE / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def reset() -> None:
    with LOCK:
        connectors.clear()
        audit.clear()
        stub_companies.clear()
        stub_companies.update(_load("stub-companies.json").get("companies", {}))
        stub_subscriptions.clear()
        stub_subscriptions.update({s["offerSubscriptionId"]: s
                                   for s in _load("stub-subscriptions.json").get("subscriptions", [])})


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def write_audit(operation: str, object_id: str, sub: str | None = None, company_id: str | None = None) -> None:
    """FRAMEWORK 4.3: time, acting person, company, operation, object. No secrets, no names."""
    audit.append({"at": now(), "sub": sub, "companyId": company_id, "operation": operation, "objectId": object_id})


def view(c: dict) -> dict:
    """`Connector` of openapi.yaml."""
    return {"connectorId": c["id"], "name": c["name"], "endpoint": c["endpoint"], "location": c["location"],
            "type": c["type"], "status": c["status"], "providerCompanyId": c["provider_company_id"],
            "hostCompanyId": c["host_company_id"], "technicalUserId": c["technical_user_id"],
            "offerSubscriptionId": c["offer_subscription_id"], "createdAt": c["created_at"],
            "changedAt": c["changed_at"]}


def publish_deactivated(c: dict) -> None:
    events.publish(MODULE, "ConnectorDeactivated", {"connectorId": c["id"], "companyId": c["host_company_id"]})


def is_uuid(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _step_input(input: dict, key: str) -> str:
    """StepInput of openapi.yaml: `processId`, `stepRunId` and the business key, all UUIDs.
    Checked before anything changes (README 8, FRAMEWORK 4.4)."""
    if not isinstance(input, dict):
        raise Problem(MODULE, 400, "validation", detail="JSON object required", retryable=False)
    errors = [{"field": f, "message": "UUID required"} for f in ("processId", "stepRunId", key)
              if not is_uuid(input.get(f))]
    if errors:
        raise Problem(MODULE, 400, "validation", errors=errors, retryable=False)
    return input[key]


# ---------------------------------------------------------------- steps (README 8)
def deactivate_subscription_connectors(input: dict) -> dict:
    """8.1: the connector of an ended or declined subscription becomes INACTIVE, without technical user.
    Also clears a link that an INACTIVE connector still holds (deleted while the subscription was
    PENDING, README 7.6). `ConnectorDeactivated` only for a real change of status, so a repetition
    publishes nothing and answers DONE with an empty list."""
    sub_id = _step_input(input, "offerSubscriptionId")
    changed = []
    with LOCK:
        for c in connectors.values():
            if c["offer_subscription_id"] != sub_id or (c["status"] == INACTIVE and c["technical_user_id"] is None):
                continue
            was_active = c["status"] == ACTIVE
            c.update(status=INACTIVE, technical_user_id=None, changed_at=now())
            write_audit("deactivate-subscription-connectors", c["id"])
            if was_active:
                publish_deactivated(c)
            changed.append(c["id"])
    return standin.step_reply(input, {"connectorIds": changed})


def unlink_technical_user(input: dict) -> dict:
    """8.2: removes the deleted technical user from the connector that uses it; the connector keeps its status."""
    tu_id = _step_input(input, "technicalUserId")
    changed = []
    with LOCK:
        for c in connectors.values():
            if c["technical_user_id"] == tu_id:
                c.update(technical_user_id=None, changed_at=now())
                write_audit("unlink-technical-user", c["id"])
                changed.append(c["id"])
    return standin.step_reply(input, {"connectorIds": changed})


# ---------------------------------------------------------------- queries (README 9)
def list_connectors_internal(*, technicalUserId: str | None = None, **_other) -> list:
    """9.1: the ACTIVE connectors that use this technical user, as `ConnectorRef`."""
    if not technicalUserId:
        raise Problem(MODULE, 400, "validation", detail="technicalUserId is required")
    with LOCK:
        return [{"connectorId": c["id"], "status": c["status"]} for c in connectors.values()
                if c["technical_user_id"] == technicalUserId and c["status"] == ACTIVE]


reset()
