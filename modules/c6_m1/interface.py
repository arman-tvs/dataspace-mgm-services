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
from pathlib import Path

from portal_common import events, standin
from portal_common.problems import Problem

MODULE = "c6-m1"
HERE = Path(__file__).resolve().parent

ACTIVE, INACTIVE = "ACTIVE", "INACTIVE"
COMPANY_CONNECTOR, CONNECTOR_AS_A_SERVICE = "COMPANY_CONNECTOR", "CONNECTOR_AS_A_SERVICE"

connectors: dict[str, dict] = {}     # connectorId -> row of table `connector` (README 5)
audit: list[dict] = []               # table `audit_entry` (FRAMEWORK 4.3)
stub_companies: dict[str, str] = {}          # built-in stand-in of C3-M1: companyId -> status (README 11)
stub_subscriptions: dict[str, dict] = {}     # built-in stand-in of C10-M1: offerSubscriptionId -> subscription


def _load(name: str) -> dict:
    path = HERE / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def reset() -> None:
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


def _require(input: dict, field: str) -> str:
    value = input.get(field)
    if not value:
        raise Problem(MODULE, 400, "validation", detail=f"{field} is required", retryable=False)
    return value


# ---------------------------------------------------------------- steps (README 8)
def deactivate_subscription_connectors(input: dict) -> dict:
    """8.1: the connector of an ended or declined subscription becomes INACTIVE, without technical user.
    Repeatable: a second call finds nothing left to change and answers DONE with an empty list."""
    sub_id = _require(input, "offerSubscriptionId")
    changed = []
    for c in connectors.values():
        if c["offer_subscription_id"] == sub_id and c["status"] == ACTIVE:
            c.update(status=INACTIVE, technical_user_id=None, changed_at=now())
            write_audit("deactivate-subscription-connectors", c["id"])
            publish_deactivated(c)
            changed.append(c["id"])
    return standin.step_reply(input, {"connectorIds": changed})


def unlink_technical_user(input: dict) -> dict:
    """8.2: removes the deleted technical user from the connector that uses it; the connector keeps its status."""
    tu_id = _require(input, "technicalUserId")
    changed = []
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
    return [{"connectorId": c["id"], "status": c["status"]} for c in connectors.values()
            if c["technical_user_id"] == technicalUserId and c["status"] == ACTIVE]


reset()
