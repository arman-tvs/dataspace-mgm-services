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
"""Shared parts of the C3-M2 services: the step types, input checks and the step answer (FRAMEWORK 4.4)."""
from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

from modules.c3_m2 import errors, store
from modules.c3_m2.store import Registration

StepInputJson = dict[str, Any]    # JSON body of POST /steps/<step>, incl. processId and stepRunId
StepState = Literal["DONE", "RUNNING"]


class StepReply(TypedDict):
    """Answer of a step (FRAMEWORK 4.4); `result` holds `bpn`, `did`, `connectorId` (all strings)."""
    stepRunId: str | None
    state: StepState
    result: dict[str, str]


class IdentifierJson(TypedDict):
    type: str
    value: str


COUNTRY = re.compile(r"^[A-Z]{2}$")


def required(input: StepInputJson, field: str) -> str:
    """A non-empty string field of the input; otherwise 400 `validation` (never a KeyError)."""
    value = input.get(field)
    if not isinstance(value, str) or not value.strip():
        raise errors.validation(f"{field} is required")
    return value


def optional(input: StepInputJson, field: str) -> str | None:
    """An optional string field; `None` and "" both count as absent (flows pass missing lookups as None)."""
    value = input.get(field)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise errors.validation(f"{field} must be a string")
    return value


def identifiers(value: object) -> list[IdentifierJson]:
    """`identifiers` (README 6.5): list of `type` and `value`; `None` counts as empty."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise errors.validation("identifiers must be a list")
    out: list[IdentifierJson] = []
    for item in value:
        kind = item.get("type") if isinstance(item, dict) else None
        text = item.get("value") if isinstance(item, dict) else None
        if not isinstance(kind, str) or not kind or not isinstance(text, str) or not text:
            raise errors.validation("every identifier needs type and value")
        out.append({"type": kind, "value": text})
    return out


def registered(company_id: str) -> Registration:
    """Precondition of most steps: status `REGISTERED` (otherwise 409 `invalid-state`)."""
    row = store.registrations.get(company_id)
    if row is None or row.status != "REGISTERED" or row.bpn is None:
        status = row.status if row else "no registration"
        raise errors.invalid_state(f"company {company_id} is not REGISTERED at the CSP ({status})")
    return row


def bpn_of(row: Registration) -> str:
    """BPN of a registered row (`registered` guarantees it)."""
    assert row.bpn is not None
    return row.bpn


def reply(input: StepInputJson, result: dict[str, str] | None = None, state: StepState = "DONE") -> StepReply:
    """Step answer of FRAMEWORK 4.4; the shape of `portal_common.standin.step_reply`, typed."""
    step_run = input.get("stepRunId")
    return {"stepRunId": step_run if isinstance(step_run, str) else None, "state": state, "result": result or {}}
