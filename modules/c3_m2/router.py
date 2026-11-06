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
"""HTTP layer of C3-M2 CSP Connection under `/api/c3-m2`.

Each route reads like its entry in openapi.yaml: the request body is the schema of the spec
(`schemas.py`, validated by FastAPI, 400 `validation` on error), the permission is its
`x-permission` (all with scope `osp`, FRAMEWORK 4.3), the answer is its response schema. Then the
route calls the function of `interface.py` with a plain dict, as Process Orchestration does
in-process.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from portal_common import problems, spec, standin

from . import interface
from .interface import MODULE, StepReply
from .schemas import (
    ConnectorInput,
    CspCompanyMatch,
    CspNotification,
    CspRegistration,
    RegisterCompanyInput,
    RegisterConnectorInput,
    RegisterDidInput,
    StepInput,
    StepResult,
    TransferCompanyInput,
    UpdateCompanyInput,
)

# Every route declares its permission as a FastAPI dependency: `standin.perm(MODULE, method, path)`
# reads `x-permission` of that operation in openapi.yaml and answers 401 or 403 before the handler
# runs. `_` receives the token's claims; no route needs them, because every permission of this
# module has scope `osp` (FRAMEWORK 4.3). The docstring of a route is its description in /docs.
Claims = dict[str, Any]

router = APIRouter(prefix=spec.module(MODULE).base_path, route_class=problems.route_class(MODULE),
                   tags=["c3-m2 CSP Connection"])


def reset() -> None:
    interface.reset()


def _input(body: BaseModel) -> dict[str, Any]:
    """The validated body as the plain JSON dict the interface functions take."""
    return body.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------- OSP staff (README 7.1)
@router.get("/companies/{companyId}", operation_id="getCspRegistration", summary="Status of a company at the CSP",
            response_model=CspRegistration, response_model_exclude_none=True)
def get_csp_registration(companyId: UUID,  # openapi name (format uuid: a malformed id is 400 validation)
                         _: Claims = standin.perm(MODULE, "GET", "/companies/{companyId}")) -> dict[str, str]:
    """README 7.1, for OSP staff (`view_csp_registration`). 404 without a registration."""
    return interface.get_csp_registration(companyId=str(companyId))


# ---------------------------------------------------------------- callback of the CSP (README 7.2)
@router.post("/csp-notifications", operation_id="receiveCspNotification", summary="Notification from the CSP")
def receive_csp_notification(body: CspNotification,
                             _: Claims = standin.perm(MODULE, "POST", "/csp-notifications")) -> dict[str, str | bool]:
    """README 7.2, called by the CSP's service account (`report_csp_notification`).
    A known `notificationId` answers 200 and is not processed again."""
    return interface.receive_csp_notification(_input(body))


# ---------------------------------------------------------------- query (README 9)
@router.get("/internal/find-companies", operation_id="findCompanies", summary="Duplicate check at the CSP",
            response_model=list[CspCompanyMatch], response_model_exclude_none=True)
def find_companies(_: Claims = standin.perm(MODULE, "GET", "/internal/find-companies"),
                   ebwoid: str | None = None, euid: str | None = None,
                   identifier: list[str] = Query(default=[], description="<type>:<value>, repeatable"),
                   legalName: str | None = None,  # openapi name
                   country: str | None = Query(default=None, pattern=r"^[A-Z]{2}$")) -> list[dict[str, Any]]:
    """README 9, duplicate check for C1-M3. At least `ebwoid`, `euid`, `identifier`, or
    `legalName` with `country`. An empty list means no match."""
    return interface.find_companies(ebwoid=ebwoid, euid=euid, identifier=identifier, legalName=legalName,
                                    country=country)


# ---------------------------------------------------------------- steps (README 8)
@router.post("/steps/register-company", operation_id="stepRegisterCompany",
             summary="Register a company with the CSP",
             response_model=StepResult, response_model_exclude_none=True)
def register_company(body: RegisterCompanyInput,
                     _: Claims = standin.perm(MODULE, "POST", "/steps/register-company")) -> StepReply:
    """README 8.1. DONE with `bpn`, or RUNNING until `CompanyRegisteredAtCsp`."""
    return interface.register_company(_input(body))


@router.post("/steps/transfer-company", operation_id="stepTransferCompany",
             summary="Transfer a company to this OSP",
             response_model=StepResult, response_model_exclude_none=True)
def transfer_company(body: TransferCompanyInput,
                     _: Claims = standin.perm(MODULE, "POST", "/steps/transfer-company")) -> StepReply:
    """README 8.2. The company moves to this OSP; answers as register-company."""
    return interface.transfer_company(_input(body))


@router.post("/steps/register-did", operation_id="stepRegisterDid",
             summary="Enter the DID in the directory BPN → DID",
             response_model=StepResult, response_model_exclude_none=True)
def register_did(body: RegisterDidInput,
                 _: Claims = standin.perm(MODULE, "POST", "/steps/register-did")) -> StepReply:
    """README 8.3. Needs status REGISTERED."""
    return interface.register_did(_input(body))


@router.post("/steps/update-company", operation_id="stepUpdateCompany",
             summary="Pass changed core data to the CSP",
             response_model=StepResult, response_model_exclude_none=True)
def update_company(body: UpdateCompanyInput,
                   _: Claims = standin.perm(MODULE, "POST", "/steps/update-company")) -> StepReply:
    """README 8.4. Needs status REGISTERED."""
    return interface.update_company(_input(body))


@router.post("/steps/register-membership", operation_id="stepRegisterMembership",
             summary="Register the membership at the CSP",
             response_model=StepResult, response_model_exclude_none=True)
def register_membership(body: StepInput,
                        _: Claims = standin.perm(MODULE, "POST", "/steps/register-membership")) -> StepReply:
    """README 8.5. Needs status REGISTERED; calls the CSP only on a change."""
    return interface.register_membership(_input(body))


@router.post("/steps/deregister-membership", operation_id="stepDeregisterMembership",
             summary="Deregister the membership at the CSP",
             response_model=StepResult, response_model_exclude_none=True)
def deregister_membership(body: StepInput,
                          _: Claims = standin.perm(MODULE, "POST", "/steps/deregister-membership")) -> StepReply:
    """README 8.5. After `CompanyTransferredAway`: DONE without a call."""
    return interface.deregister_membership(_input(body))


@router.post("/steps/register-connector", operation_id="stepRegisterConnector",
             summary="Enter a connector in the discovery of the CSP",
             response_model=StepResult, response_model_exclude_none=True)
def register_connector(body: RegisterConnectorInput,
                       _: Claims = standin.perm(MODULE, "POST", "/steps/register-connector")) -> StepReply:
    """README 8.6. Calls the CSP only for a new connector or a new address."""
    return interface.register_connector(_input(body))


@router.post("/steps/deregister-connector", operation_id="stepDeregisterConnector",
             summary="Remove a connector from the discovery of the CSP",
             response_model=StepResult, response_model_exclude_none=True)
def deregister_connector(body: ConnectorInput,
                         _: Claims = standin.perm(MODULE, "POST", "/steps/deregister-connector")) -> StepReply:
    """README 8.6. Unknown or already removed: DONE without a call."""
    return interface.deregister_connector(_input(body))
