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
"""
from __future__ import annotations

import json

from fastapi import Body, File, Form, Query, Response, UploadFile

from portal_common import standin
from portal_common.problems import Problem

from . import interface
from .interface import MODULE, company_view, role_view

router = standin.router(MODULE)


def reset() -> None:
    interface.reset()


# ---------------------------------------------------------------------------------- steps (8)
@router.post("/steps/create-company")
def create_company(body: dict = Body(...),
                   _: dict = standin.perm(MODULE, "POST", "/steps/create-company")):
    return interface.create_company(body)


@router.post("/steps/assign-identifier")
def assign_identifier(body: dict = Body(...),
                      _: dict = standin.perm(MODULE, "POST", "/steps/assign-identifier")):
    return interface.assign_identifier(body)


@router.post("/steps/activate-company")
def activate_company(body: dict = Body(...),
                     _: dict = standin.perm(MODULE, "POST", "/steps/activate-company")):
    return interface.activate_company(body)


@router.post("/steps/deactivate-company")
def deactivate_company(body: dict = Body(...),
                       _: dict = standin.perm(MODULE, "POST", "/steps/deactivate-company")):
    return interface.deactivate_company(body)


@router.post("/steps/reactivate-company")
def reactivate_company(body: dict = Body(...),
                       _: dict = standin.perm(MODULE, "POST", "/steps/reactivate-company")):
    return interface.reactivate_company(body)


@router.post("/steps/reject-company")
def reject_company(body: dict = Body(...),
                   _: dict = standin.perm(MODULE, "POST", "/steps/reject-company")):
    return interface.reject_company(body)


# ------------------------------------------------------------------------- queries (9.2, 9.3, 9.4)
@router.get("/internal/companies")
def query_companies(id: list[str] | None = Query(None), bpn: list[str] | None = Query(None),
                    _: dict = standin.perm(MODULE, "GET", "/internal/companies")):
    return interface.query_companies(id=id, bpn=bpn)


@router.post("/internal/companies/identifier-matches")
def find_identifier_matches(body: dict = Body(...),
                            _: dict = standin.perm(MODULE, "POST",
                                                   "/internal/companies/identifier-matches")):
    return interface.find_identifier_matches(**body)


@router.get("/internal/company-roles")
def query_company_role_catalog(lang: str | None = None,
                               _: dict = standin.perm(MODULE, "GET", "/internal/company-roles")):
    return interface.query_company_role_catalog(lang=lang)


@router.get("/internal/companies/{companyId}")
def query_company(companyId: str,
                  _: dict = standin.perm(MODULE, "GET", "/internal/companies/{companyId}")):
    return interface.query_company(companyId=companyId)


# -------------------------------------------------------------------- own company, people (7.1, 7.2)
@router.get("/companies/{companyId}")
def read_own_company(companyId: str,
                     claims: dict = standin.perm(MODULE, "GET", "/companies/{companyId}")):
    standin.company_scope(MODULE, claims, companyId)
    return role_view(companyId)


@router.post("/companies/{companyId}/attestation-updates")
def update_from_attestation(companyId: str, body: dict = Body(...),
                            claims: dict = standin.perm(MODULE, "POST",
                                                        "/companies/{companyId}/attestation-updates")):
    standin.company_scope(MODULE, claims, companyId)
    return interface.update_company_from_attestation(companyId, body, claims.get("sub"))


@router.patch("/companies/{companyId}")
def update_own_company(companyId: str, body: dict = Body(...),
                       claims: dict = standin.perm(MODULE, "PATCH", "/companies/{companyId}")):
    standin.company_scope(MODULE, claims, companyId)
    return interface.update_company(companyId, body, claims.get("sub"))


# ------------------------------------------------------------------------------- company roles (7.7 - 7.9)
@router.get("/companies/{companyId}/company-roles")
def list_company_roles(companyId: str, lang: str | None = None,
                       claims: dict = standin.perm(MODULE, "GET",
                                                   "/companies/{companyId}/company-roles")):
    standin.company_scope(MODULE, claims, companyId)
    return interface.list_company_roles(companyId, lang)


@router.post("/companies/{companyId}/company-roles")
def add_company_role(companyId: str, body: dict = Body(...), lang: str | None = None,
                     claims: dict = standin.perm(MODULE, "POST",
                                                 "/companies/{companyId}/company-roles")):
    standin.company_scope(MODULE, claims, companyId)
    return interface.add_company_role(companyId, body, claims.get("sub"), lang)


@router.delete("/companies/{companyId}/company-roles/{companyRole}")
def remove_company_role(companyId: str, companyRole: str, lang: str | None = None,
                        claims: dict = standin.perm(
                            MODULE, "DELETE",
                            "/companies/{companyId}/company-roles/{companyRole}")):
    standin.company_scope(MODULE, claims, companyId)
    return interface.remove_company_role(companyId, companyRole, claims.get("sub"), lang)


# ------------------------------------------------------------------------------ change requests (7.4 - 7.6)
@router.post("/companies/{companyId}/change-requests", status_code=201)
def create_change_request(companyId: str, data: str = Form(...),
                          documents: list[UploadFile] = File(default=[]),
                          claims: dict = standin.perm(MODULE, "POST",
                                                      "/companies/{companyId}/change-requests")):
    standin.company_scope(MODULE, claims, companyId)
    try:
        parsed = json.loads(data)
    except ValueError as error:
        raise Problem(MODULE, 400, "validation",
                      errors=[{"field": "data", "reason": f"not JSON: {error}"}]) from error
    files = [(upload.filename or "", upload.file.read(), upload.content_type) for upload in documents]
    return interface.create_change_request(companyId, parsed, files, claims.get("sub"))


@router.get("/companies/{companyId}/change-requests")
def list_own_change_requests(companyId: str, page: int = 0, size: int = 20,
                             claims: dict = standin.perm(MODULE, "GET",
                                                         "/companies/{companyId}/change-requests")):
    standin.company_scope(MODULE, claims, companyId)
    return interface.list_own_change_requests(companyId, page, size)


@router.post("/companies/{companyId}/change-requests/{changeRequestId}/withdraw")
def withdraw_change_request(companyId: str, changeRequestId: str,
                            claims: dict = standin.perm(
                                MODULE, "POST",
                                "/companies/{companyId}/change-requests/{changeRequestId}/withdraw")):
    standin.company_scope(MODULE, claims, companyId)
    return interface.withdraw_change_request(companyId, changeRequestId, claims.get("sub"))


# --------------------------------------------------------------------- change requests, review (7.14 - 7.18)
@router.get("/osp/change-requests")
def list_change_requests(status: list[str] | None = Query(None), companyId: str | None = None,
                         page: int = 0, size: int = 20,
                         _: dict = standin.perm(MODULE, "GET", "/osp/change-requests")):
    return interface.list_change_requests(status=status, companyId=companyId, page=page, size=size)


@router.get("/osp/change-requests/{changeRequestId}")
def get_change_request(changeRequestId: str,
                       _: dict = standin.perm(MODULE, "GET", "/osp/change-requests/{changeRequestId}")):
    return interface.get_change_request(changeRequestId)


@router.get("/osp/change-requests/{changeRequestId}/documents/{documentId}")
def get_change_request_document(changeRequestId: str, documentId: str,
                                claims: dict = standin.perm(
                                    MODULE, "GET",
                                    "/osp/change-requests/{changeRequestId}/documents/{documentId}")):
    answer = interface.get_change_request_document(changeRequestId, documentId, claims.get("sub"))
    return Response(answer["content"], media_type=answer["media_type"], headers={
        "Content-Disposition": f'attachment; filename="{answer["file_name"]}"'})


@router.post("/osp/change-requests/{changeRequestId}/approve")
def approve_change_request(changeRequestId: str, body: dict | None = Body(None),
                           claims: dict = standin.perm(
                               MODULE, "POST", "/osp/change-requests/{changeRequestId}/approve")):
    return interface.approve_change_request(changeRequestId, body, claims.get("sub"))


@router.post("/osp/change-requests/{changeRequestId}/decline")
def decline_change_request(changeRequestId: str, body: dict | None = Body(None),
                           claims: dict = standin.perm(
                               MODULE, "POST", "/osp/change-requests/{changeRequestId}/decline")):
    return interface.decline_change_request(changeRequestId, body, claims.get("sub"))


# --------------------------------------------------------------------------- OSP staff (7.10, 7.11, 7.12)
@router.get("/osp/companies")
def list_companies(status: list[str] | None = Query(None), name: str | None = None,
                   bpn: str | None = None, hasBpn: bool | None = None,
                   companyRole: str | None = None, coreDataSource: str | None = None,
                   page: int = 0, size: int = 20,
                   _: dict = standin.perm(MODULE, "GET", "/osp/companies")):
    return interface.list_companies(status=status, name=name, bpn=bpn, hasBpn=hasBpn,
                                    companyRole=companyRole, coreDataSource=coreDataSource,
                                    page=page, size=size)


@router.get("/osp/companies/{companyId}")
def read_company(companyId: str,
                 _: dict = standin.perm(MODULE, "GET", "/osp/companies/{companyId}")):
    return company_view(companyId, detail=True)


@router.post("/osp/companies/{companyId}/deactivate")
def deactivate_company_by_staff(companyId: str, body: dict = Body(...),
                                claims: dict = standin.perm(
                                    MODULE, "POST", "/osp/companies/{companyId}/deactivate")):
    return interface.deactivate_company_by_staff(companyId, body, claims.get("sub"))


@router.patch("/osp/companies/{companyId}")
def correct_company(companyId: str, body: dict = Body(...),
                    claims: dict = standin.perm(MODULE, "PATCH", "/osp/companies/{companyId}")):
    return interface.correct_company(companyId, body, claims.get("sub"))
