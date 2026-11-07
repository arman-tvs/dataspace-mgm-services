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
"""Public interface of C3-M2 CSP Connection (call convention of AGENTS.md; ADR-0003 "facade").

Steps for Process Orchestration (README 8), the query `find-companies` (README 9), the callback
of the CSP (README 7.2) and the status of a company at the CSP (README 7.1). No token checks
here: the router checks token and permission, a caller in the same process has none.

Steps take the JSON body as a plain dict (`StepInputJson`) and answer a `StepReply`
(FRAMEWORK 4.4). The HTTP contract of the same operations is in `schemas.py`, the logic in
`services/`, the CSP behind `adapters/csp.py`, the module's data in `store.py`.
"""
from __future__ import annotations

from typing import Any

from .errors import MODULE
from .services import connectors, lifecycle, notifications, queries, registration
from .services.common import StepInputJson, StepReply

__all__ = [
    "MODULE",
    "StepReply",
    "deregister_connector",
    "deregister_membership",
    "find_companies",
    "get_csp_registration",
    "receive_csp_notification",
    "register_company",
    "register_connector",
    "register_did",
    "register_membership",
    "registration_view",
    "reset",
    "transfer_company",
    "update_company",
]


def reset() -> None:
    """Fresh state: own tables empty, then the seed data of README 4; new built-in CSP stand-in."""
    lifecycle.reset()


# ---------------------------------------------------------------- steps (README 8)
def register_company(input: StepInputJson) -> StepReply:
    """Step register-company (README 8.1)."""
    return registration.register_company(input)


def transfer_company(input: StepInputJson) -> StepReply:
    """Step transfer-company (README 8.2): the company moves to this OSP."""
    return registration.transfer_company(input)


def register_did(input: StepInputJson) -> StepReply:
    """Step register-did (README 8.3): DID in the directory BPN -> DID."""
    return registration.register_did(input)


def update_company(input: StepInputJson) -> StepReply:
    """Step update-company (README 8.4): changed core data to the CSP."""
    return registration.update_company(input)


def register_membership(input: StepInputJson) -> StepReply:
    """Step register-membership (README 8.5)."""
    return registration.membership(input, True)


def deregister_membership(input: StepInputJson) -> StepReply:
    """Step deregister-membership (README 8.5)."""
    return registration.membership(input, False)


def register_connector(input: StepInputJson) -> StepReply:
    """Step register-connector (README 8.6): connector into the discovery of the CSP."""
    return connectors.register_connector(input)


def deregister_connector(input: StepInputJson) -> StepReply:
    """Step deregister-connector (README 8.6)."""
    return connectors.deregister_connector(input)


# ---------------------------------------------------------------- query (README 9)
def find_companies(*, ebwoid: str | None = None, euid: str | None = None, identifier: list[str] | str | None = None,
                   legalName: str | None = None, country: str | None = None) -> list[dict[str, Any]]:  # openapi names
    """Query findCompanies (README 9, 6.2): duplicate check at the CSP; one `CspCompanyMatch` per match."""
    return queries.find_companies(ebwoid, euid, identifier, legalName, country)


# ---------------------------------------------------------------- callback of the CSP (README 7.2)
def receive_csp_notification(body: dict[str, Any]) -> dict[str, str | bool]:
    """Notification from the CSP (README 7.2)."""
    return notifications.receive_csp_notification(body)


# ---------------------------------------------------------------- status at the CSP (README 7.1)
registration_view = queries.registration_view


def get_csp_registration(companyId: str) -> dict[str, str]:  # openapi name
    """Operation getCspRegistration (README 7.1); 404 `not-found` without a registration."""
    return queries.get_csp_registration(companyId)
