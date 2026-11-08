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
#  Assisted-By: Hermes Agent (deepseek-v4.1-flash)
#################################################################################
"""Thin HTTP layer of C3-M1: token, permission, scope, then the interface (AGENTS.md 5).

Every route takes its permission from `x-permission` of the spec through `standin.perm`. Paths in
the scope `company` additionally check `company_id` against the path (FRAMEWORK 4.3: another
company's object stays invisible, 404). No business logic here.

Every route takes its permission from `x-permission` of the spec through `standin.perm` (a FastAPI
dependency). Paths in the scope `company` additionally check `company_id` against the path
(FRAMEWORK 4.3: another company's object stays invisible, 404). No business logic here.

ADR-0003 "HTTP layer (FastAPI)": every route has the spec's `operationId`, a request model and a response
model from `schemas.py`, and documents its Problem answers (README 12). The router hands the interface the
plain dict the client sent (`_input`), so `interface.py` keeps the call convention.
"""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import Body, File, Form, Query, Response, UploadFile
from pydantic import BaseModel

from portal_common import standin

from . import errors, interface
from .interface import MODULE, company_view, role_view
from .schemas import (
    ApprovalInput,
    AttestationUpdate,
    AttestationUpdateResult,
    ChangeRequest,
    ChangeRequestDetail,
    ChangeRequestPage,
    Company,
    CompanyCorrection,
    CompanyDetail,
    CompanyInternal,
    CompanyLookupResult,
    CompanyPage,
    CompanyRoleAdd,
    CompanyRoleDefinition,
    CompanyRoleState,
    CompanyUpdate,
    DeclineInput,
    IdentifierMatchQuery,
    IdentifierMatchResult,
    Problem,
    Reason,
    StepAssignIdentifier,
    StepCompanyApplication,
    StepCompanyRef,
    StepDeactivateCompany,
    StepResultActivation,
    StepResultCompanyState,
    StepResultDeactivation,
    StepResultIdentifier,
    StepResultReactivation,
)

router = standin.router(MODULE)
# standin.router() tags every router "<module> (stand-in)" in Swagger; C3-M1 is implemented.
router.tags = ["c3-m1 Company Profile"]

Claims = dict


def reset() -> None:
    interface.reset()


def _input(body: BaseModel) -> dict:
    """The validated body as the plain JSON dict the interface functions take: only what the client sent."""
    return body.model_dump(mode="json", exclude_unset=True)


def _problems(*statuses: int) -> dict[int | str, dict[str, object]]:
    """The Problem answers of an operation (README 12) for Swagger."""
    return {status: {"model": Problem, "description": "Problem Details (README 12)"} for status in statuses}


STEP_ERRORS = _problems(400, 403, 404, 409, 502)


# ---------------------------------------------------------------------------------- steps (README 8)
@router.post("/steps/create-company", operation_id="stepCreateCompany", response_model=StepResultCompanyState,
             response_model_exclude_unset=True, responses=STEP_ERRORS)
def create_company(body: StepCompanyApplication,
                   _: Claims = standin.perm(MODULE, "POST", "/steps/create-company")) -> dict:
    """README 8.1: the company REQUESTED from a submitted application."""
    return interface.create_company(_input(body))


@router.post("/steps/assign-identifier", operation_id="stepAssignIdentifier", response_model=StepResultIdentifier,
             response_model_exclude_unset=True, responses=STEP_ERRORS)
def assign_identifier(body: StepAssignIdentifier,
                      _: Claims = standin.perm(MODULE, "POST", "/steps/assign-identifier")) -> dict:
    """README 8.2: the BPN from the CSP."""
    return interface.assign_identifier(_input(body))


@router.post("/steps/activate-company", operation_id="stepActivateCompany", response_model=StepResultActivation,
             response_model_exclude_unset=True, responses=STEP_ERRORS)
def activate_company(body: StepCompanyApplication,
                     _: Claims = standin.perm(MODULE, "POST", "/steps/activate-company")) -> dict:
    """README 8.3: ACTIVE with the roles whose terms were consented to."""
    return interface.activate_company(_input(body))


@router.post("/steps/deactivate-company", operation_id="stepDeactivateCompany",
             response_model=StepResultDeactivation, response_model_exclude_unset=True, responses=STEP_ERRORS)
def deactivate_company(body: StepDeactivateCompany,
                       _: Claims = standin.perm(MODULE, "POST", "/steps/deactivate-company")) -> dict:
    """README 8.5: INACTIVE with the reason."""
    return interface.deactivate_company(_input(body))


@router.post("/steps/reactivate-company", operation_id="stepReactivateCompany",
             response_model=StepResultReactivation, response_model_exclude_unset=True, responses=STEP_ERRORS)
def reactivate_company(body: StepCompanyApplication,
                       _: Claims = standin.perm(MODULE, "POST", "/steps/reactivate-company")) -> dict:
    """README 8.6: ACTIVE again from a reactivation application."""
    return interface.reactivate_company(_input(body))


@router.post("/steps/reject-company", operation_id="stepRejectCompany", response_model=StepResultCompanyState,
             response_model_exclude_unset=True, responses=STEP_ERRORS)
def reject_company(body: StepCompanyRef,
                   _: Claims = standin.perm(MODULE, "POST", "/steps/reject-company")) -> dict:
    """README 8.4: REJECTED (final)."""
    return interface.reject_company(_input(body))


# ------------------------------------------------------------------------- queries (README 9.2, 9.3, 9.4)
@router.get("/internal/companies", operation_id="queryCompanies", response_model=CompanyLookupResult,
            response_model_exclude_unset=True, responses=_problems(400, 403))
def query_companies(id: Annotated[list[str] | None, Query()] = None,
                    bpn: Annotated[list[str] | None, Query()] = None,
                    _: Claims = standin.perm(MODULE, "GET", "/internal/companies")) -> dict:
    """README 9.2: several companies by id or BPN."""
    return interface.query_companies(id=id, bpn=bpn)


@router.post("/internal/companies/identifier-matches", operation_id="findIdentifierMatches",
             response_model=IdentifierMatchResult, response_model_exclude_unset=True, responses=_problems(400, 403))
def find_identifier_matches(body: IdentifierMatchQuery,
                            _: Claims = standin.perm(MODULE, "POST",
                                                     "/internal/companies/identifier-matches")) -> dict:
    """README 9.3: companies with one of the identifiers (duplicate check)."""
    return interface.find_identifier_matches(**_input(body))


@router.get("/internal/company-roles", operation_id="queryCompanyRoleCatalog",
            response_model=list[CompanyRoleDefinition], response_model_exclude_unset=True,
            responses=_problems(403))
def query_company_role_catalog(lang: str | None = None,
                               _: Claims = standin.perm(MODULE, "GET", "/internal/company-roles")) -> list[dict]:
    """README 9.4: the role catalogue of the installation."""
    return interface.query_company_role_catalog(lang=lang)


@router.get("/internal/companies/{companyId}", operation_id="queryCompany", response_model=CompanyInternal,
            response_model_exclude_unset=True, responses=_problems(403, 404))
def query_company(companyId: str,
                  _: Claims = standin.perm(MODULE, "GET", "/internal/companies/{companyId}")) -> dict:
    """README 9.1: one company for other modules."""
    return interface.query_company(companyId=companyId)


# -------------------------------------------------------------------- own company, people (README 7.1 - 7.3)
@router.get("/companies/{companyId}", operation_id="getCompany", response_model=Company,
            response_model_exclude_unset=True, responses=_problems(401, 403, 404))
def read_own_company(companyId: str,
                     claims: Claims = standin.perm(MODULE, "GET", "/companies/{companyId}")) -> dict:
    """README 7.1: the own company."""
    standin.company_scope(MODULE, claims, companyId)
    return role_view(companyId)


@router.post("/companies/{companyId}/attestation-updates", operation_id="updateCompanyFromAttestation",
             response_model=AttestationUpdateResult, response_model_exclude_unset=True,
             responses=_problems(400, 401, 403, 404, 409, 502))
def update_from_attestation(companyId: str, body: AttestationUpdate,
                            claims: Claims = standin.perm(MODULE, "POST",
                                                          "/companies/{companyId}/attestation-updates")) -> dict:
    """README 7.3: core data from a verification attestation of the EBW-Connector."""
    standin.company_scope(MODULE, claims, companyId)
    return interface.update_company_from_attestation(companyId, _input(body), claims.get("sub"))


@router.patch("/companies/{companyId}", operation_id="updateCompany", response_model=Company,
              response_model_exclude_unset=True, responses=_problems(400, 401, 403, 404, 409))
def update_own_company(companyId: str, body: CompanyUpdate,
                       claims: Claims = standin.perm(MODULE, "PATCH", "/companies/{companyId}")) -> dict:
    """README 7.2: only `shortName`; other fields give 409 `field-locked`."""
    standin.company_scope(MODULE, claims, companyId)
    return interface.update_company(companyId, _input(body), claims.get("sub"))


# ------------------------------------------------------------------------------- company roles (README 7.7 - 7.9)
@router.get("/companies/{companyId}/company-roles", operation_id="listCompanyRolesOfCompany",
            response_model=list[CompanyRoleState], response_model_exclude_unset=True,
            responses=_problems(400, 401, 403, 404))
def list_company_roles(companyId: str, lang: str | None = None,
                       claims: Claims = standin.perm(MODULE, "GET",
                                                     "/companies/{companyId}/company-roles")) -> list[dict]:
    """README 7.7: every role of the catalogue with the company's status and consents."""
    standin.company_scope(MODULE, claims, companyId)
    return interface.list_company_roles(companyId, lang)


@router.post("/companies/{companyId}/company-roles", operation_id="addCompanyRole",
             response_model=list[CompanyRoleState], response_model_exclude_unset=True,
             responses=_problems(400, 401, 403, 404, 409))
def add_company_role(companyId: str, body: CompanyRoleAdd, lang: str | None = None,
                     claims: Claims = standin.perm(MODULE, "POST",
                                                   "/companies/{companyId}/company-roles")) -> list[dict]:
    """README 7.8: a role with the consents to all its terms."""
    standin.company_scope(MODULE, claims, companyId)
    return interface.add_company_role(companyId, _input(body), claims.get("sub"), lang)


@router.delete("/companies/{companyId}/company-roles/{companyRole}", operation_id="removeCompanyRole",
               response_model=list[CompanyRoleState], response_model_exclude_unset=True,
               responses=_problems(401, 403, 404, 409))
def remove_company_role(companyId: str, companyRole: str, lang: str | None = None,
                        claims: Claims = standin.perm(
                            MODULE, "DELETE",
                            "/companies/{companyId}/company-roles/{companyRole}")) -> list[dict]:
    """README 7.9: the role INACTIVE; not the last role assignable by the company."""
    standin.company_scope(MODULE, claims, companyId)
    return interface.remove_company_role(companyId, companyRole, claims.get("sub"), lang)


# ------------------------------------------------------------------------------ change requests (README 7.4 - 7.6)
@router.post("/companies/{companyId}/change-requests", operation_id="createChangeRequest", status_code=201,
             response_model=ChangeRequest, response_model_exclude_unset=True,
             responses=_problems(400, 401, 403, 404, 409))
def create_change_request(companyId: str, data: Annotated[str, Form()],
                          documents: Annotated[list[UploadFile], File()] = [],  # noqa: B006 - FastAPI copies it
                          claims: Claims = standin.perm(MODULE, "POST",
                                                        "/companies/{companyId}/change-requests")) -> dict:
    """README 7.4: a change request with supporting documents (multipart: `data` as JSON, `documents`)."""
    standin.company_scope(MODULE, claims, companyId)
    try:
        parsed = json.loads(data)
    except ValueError as error:
        raise errors.validation(errors=[{"field": "data", "message": f"not JSON: {error}"}]) from error
    files = [(upload.filename or "", upload.file.read(), upload.content_type) for upload in documents]
    return interface.create_change_request(companyId, parsed, files, claims.get("sub"))


@router.get("/companies/{companyId}/change-requests", operation_id="listOwnChangeRequests",
            response_model=ChangeRequestPage, response_model_exclude_unset=True,
            responses=_problems(400, 401, 403, 404))
def list_own_change_requests(companyId: str, page: int = 0, size: int = 20,
                             claims: Claims = standin.perm(MODULE, "GET",
                                                           "/companies/{companyId}/change-requests")) -> dict:
    """README 7.5: the company's change requests, newest first."""
    standin.company_scope(MODULE, claims, companyId)
    return interface.list_own_change_requests(companyId, page, size)


@router.post("/companies/{companyId}/change-requests/{changeRequestId}/withdraw",
             operation_id="withdrawChangeRequest", response_model=ChangeRequest, response_model_exclude_unset=True,
             responses=_problems(401, 403, 404, 409))
def withdraw_change_request(companyId: str, changeRequestId: str,
                            claims: Claims = standin.perm(
                                MODULE, "POST",
                                "/companies/{companyId}/change-requests/{changeRequestId}/withdraw")) -> dict:
    """README 7.6: an OPEN change request WITHDRAWN."""
    standin.company_scope(MODULE, claims, companyId)
    return interface.withdraw_change_request(companyId, changeRequestId, claims.get("sub"))


# --------------------------------------------------------------------- change requests, review (README 7.14 - 7.18)
@router.get("/osp/change-requests", operation_id="listChangeRequests", response_model=ChangeRequestPage,
            response_model_exclude_unset=True, responses=_problems(400, 401, 403))
def list_change_requests(status: Annotated[list[str] | None, Query()] = None, companyId: str | None = None,
                         page: int = 0, size: int = 20,
                         _: Claims = standin.perm(MODULE, "GET", "/osp/change-requests")) -> dict:
    """README 7.14: change requests for OSP staff, oldest first."""
    return interface.list_change_requests(status=status, companyId=companyId, page=page, size=size)


@router.get("/osp/change-requests/{changeRequestId}", operation_id="getChangeRequest",
            response_model=ChangeRequestDetail, response_model_exclude_unset=True,
            responses=_problems(401, 403, 404))
def get_change_request(changeRequestId: str,
                       _: Claims = standin.perm(MODULE, "GET", "/osp/change-requests/{changeRequestId}")) -> dict:
    """README 7.15: one change request with the current state of the company."""
    return interface.get_change_request(changeRequestId)


DOCUMENT_TYPES: dict[str, dict[str, object]] = {"application/pdf": {}, "image/png": {}, "image/jpeg": {}}


@router.get("/osp/change-requests/{changeRequestId}/documents/{documentId}", operation_id="getChangeRequestDocument",
            response_class=Response,
            responses={200: {"content": DOCUMENT_TYPES, "description": "The supporting document"},
                       **_problems(401, 403, 404)})
def get_change_request_document(changeRequestId: str, documentId: str,
                                claims: Claims = standin.perm(
                                    MODULE, "GET",
                                    "/osp/change-requests/{changeRequestId}/documents/{documentId}")) -> Response:
    """README 7.16: a supporting document as file (PDF, PNG or JPEG)."""
    answer = interface.get_change_request_document(changeRequestId, documentId, claims.get("sub"))
    return Response(answer["content"], media_type=answer["media_type"], headers={
        "Content-Disposition": f'attachment; filename="{answer["file_name"]}"'})


@router.post("/osp/change-requests/{changeRequestId}/approve", operation_id="approveChangeRequest",
             response_model=ChangeRequest, response_model_exclude_unset=True,
             responses=_problems(400, 401, 403, 404, 409))
def approve_change_request(changeRequestId: str, body: Annotated[ApprovalInput | None, Body()] = None,
                           claims: Claims = standin.perm(
                               MODULE, "POST", "/osp/change-requests/{changeRequestId}/approve")) -> dict:
    """README 7.17: the requested values are taken over; core data source MANUAL."""
    return interface.approve_change_request(changeRequestId, _input(body) if body else None, claims.get("sub"))


@router.post("/osp/change-requests/{changeRequestId}/decline", operation_id="declineChangeRequest",
             response_model=ChangeRequest, response_model_exclude_unset=True,
             responses=_problems(400, 401, 403, 404, 409))
def decline_change_request(changeRequestId: str, body: DeclineInput,
                           claims: Claims = standin.perm(
                               MODULE, "POST", "/osp/change-requests/{changeRequestId}/decline")) -> dict:
    """README 7.18: declined with a reason the Company Admin sees."""
    return interface.decline_change_request(changeRequestId, _input(body), claims.get("sub"))


# --------------------------------------------------------------------------- OSP staff (README 7.10 - 7.13)
@router.get("/osp/companies", operation_id="listCompanies", response_model=CompanyPage,
            response_model_exclude_unset=True, responses=_problems(400, 401, 403))
def list_companies(status: Annotated[list[str] | None, Query()] = None, name: str | None = None,
                   bpn: str | None = None, hasBpn: bool | None = None,
                   companyRole: str | None = None, coreDataSource: str | None = None,
                   page: int = 0, size: int = 20,
                   _: Claims = standin.perm(MODULE, "GET", "/osp/companies")) -> dict:
    """README 7.10: companies for OSP staff, filtered and paged."""
    return interface.list_companies(status=status, name=name, bpn=bpn, hasBpn=hasBpn,
                                    companyRole=companyRole, coreDataSource=coreDataSource,
                                    page=page, size=size)


@router.get("/osp/companies/{companyId}", operation_id="getCompanyDetail", response_model=CompanyDetail,
            response_model_exclude_unset=True, responses=_problems(401, 403, 404))
def read_company(companyId: str,
                 _: Claims = standin.perm(MODULE, "GET", "/osp/companies/{companyId}")) -> dict:
    """README 7.11: the company with all fields."""
    return company_view(companyId, detail=True)


@router.post("/osp/companies/{companyId}/deactivate", operation_id="deactivateCompany", response_model=CompanyDetail,
             response_model_exclude_unset=True, responses=_problems(400, 401, 403, 404, 409))
def deactivate_company_by_staff(companyId: str, body: Reason,
                                claims: Claims = standin.perm(
                                    MODULE, "POST", "/osp/companies/{companyId}/deactivate")) -> dict:
    """README 7.13: INACTIVE by OSP staff, with a reason for the audit log."""
    return interface.deactivate_company_by_staff(companyId, _input(body), claims.get("sub"))


@router.patch("/osp/companies/{companyId}", operation_id="correctCompany", response_model=CompanyDetail,
              response_model_exclude_unset=True, responses=_problems(400, 401, 403, 404, 409))
def correct_company(companyId: str, body: CompanyCorrection,
                    claims: Claims = standin.perm(MODULE, "PATCH", "/osp/companies/{companyId}")) -> dict:
    """README 7.12: correction of name, address or identifiers by OSP staff, with a reason."""
    return interface.correct_company(companyId, _input(body), claims.get("sub"))
