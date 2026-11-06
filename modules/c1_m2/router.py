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
"""C1-M2 Registration: HTTP layer. Checks token and permission and calls `interface.py`; the scope `own` of
the applicant's paths is applied by the interface functions, which answer 404 for other people (README 6.3)."""
from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from fastapi import Body, File, Form, Query, Response, UploadFile

from portal_common import standin

from . import attestation, catalog, interface
from .interface import MODULE

router = standin.router(MODULE)

Status = Literal["CREATED", "SUBMITTED", "WITHDRAWN", "DECLINED", "COMPLETED"]
Kind = Literal["ONBOARDING", "REACTIVATION", "TRANSFER"]
Verification = Literal["EBW", "DOCUMENTS"]
Lang = Literal["de", "en"]
Page = Query(0, ge=0)
Size = Query(20, ge=1, le=100)


def reset() -> None:
    interface.reset()


def on_startup() -> None:
    attestation.config()   # an invalid value prevents the start (README 4)
    catalog.master()


# ------------------------------------------------------------------------- reference data (7.1)
@router.get("/countries")
def list_countries(lang: Lang = "en", _: dict = standin.perm(MODULE, "GET", "/countries")):
    return interface.list_countries(lang)


@router.get("/countries/{countryCode}/identifier-types")
def list_identifier_types(countryCode: str, lang: Lang = "en",
                          _: dict = standin.perm(MODULE, "GET", "/countries/{countryCode}/identifier-types")):
    return interface.list_identifier_types(countryCode, lang)


@router.get("/company-roles")
def list_company_roles(lang: Lang = "en", _: dict = standin.perm(MODULE, "GET", "/company-roles")):
    return interface.list_company_roles(lang)


@router.get("/agreements")
def list_agreements(companyRole: list[str] | None = Query(None), lang: Lang = "en",
                    _: dict = standin.perm(MODULE, "GET", "/agreements")):
    return interface.list_agreements(companyRole or [], lang)


# --------------------------------------------------------------------- applications (7.2 to 7.11)
@router.post("/applications", status_code=201)
def create_application(response: Response, body: dict = Body(...),
                       claims: dict = standin.perm(MODULE, "POST", "/applications")):
    application, created = interface.create_application(body, claims)
    if created:
        response.headers["Location"] = f"{router.prefix}/applications/{application['id']}"
    else:
        response.status_code = 200
    return application


@router.get("/applications")
def list_applications(status: list[Status] | None = Query(None), page: int = Page, size: int = Size,
                      claims: dict = standin.perm(MODULE, "GET", "/applications")):
    return interface.list_own(claims["sub"], status, page, size)


@router.get("/applications/{applicationId}")
def get_application(applicationId: str, claims: dict = standin.perm(MODULE, "GET", "/applications/{applicationId}")):
    return interface.with_review(interface.own(claims["sub"], applicationId))


@router.patch("/applications/{applicationId}")
def update_application(applicationId: str, body: dict = Body(...),
                       claims: dict = standin.perm(MODULE, "PATCH", "/applications/{applicationId}")):
    return interface.update_application(applicationId, claims["sub"], body)


@router.put("/applications/{applicationId}/attestation")
def replace_attestation(applicationId: str, body: dict = Body(...),
                        claims: dict = standin.perm(MODULE, "PUT", "/applications/{applicationId}/attestation")):
    return interface.replace_attestation(applicationId, claims, body.get("attestation"))


@router.post("/applications/{applicationId}/submit")
def submit_application(applicationId: str, body: dict = Body(...),
                       claims: dict = standin.perm(MODULE, "POST", "/applications/{applicationId}/submit")):
    return interface.submit_application(applicationId, claims["sub"], body)


@router.post("/applications/{applicationId}/withdraw")
def withdraw_application(applicationId: str,
                         claims: dict = standin.perm(MODULE, "POST", "/applications/{applicationId}/withdraw")):
    return interface.withdraw_application(applicationId, claims["sub"])


# --------------------------------------------------------------------- supporting documents (7.7 to 7.9)
def _download(info: dict, content: bytes) -> Response:
    disposition = "attachment; filename*=UTF-8''" + quote(info["fileName"])
    return Response(content, media_type=info["contentType"],
                    headers={"Content-Disposition": disposition, "X-Content-Type-Options": "nosniff"})


@router.post("/applications/{applicationId}/documents", status_code=201)
def upload_document(applicationId: str, response: Response, file: UploadFile = File(...), documentType: str = Form(...),
                    claims: dict = standin.perm(MODULE, "POST", "/applications/{applicationId}/documents")):
    try:
        content = file.file.read(interface.document_max_bytes() + 1)
    finally:
        file.file.close()
    info = interface.upload_document(applicationId, claims["sub"], documentType, file.filename, content)
    response.headers["Location"] = f"{router.prefix}/applications/{applicationId}/documents/{info['documentId']}"
    return info


@router.get("/applications/{applicationId}/documents/{documentId}")
def get_document(applicationId: str, documentId: str,
                 claims: dict = standin.perm(MODULE, "GET", "/applications/{applicationId}/documents/{documentId}")):
    return _download(*interface.document(interface.own(claims["sub"], applicationId), documentId))


@router.delete("/applications/{applicationId}/documents/{documentId}", status_code=204)
def delete_document(applicationId: str, documentId: str,
                    claims: dict = standin.perm(MODULE, "DELETE", "/applications/{applicationId}/documents/{documentId}")):
    interface.delete_document(applicationId, documentId, claims["sub"])


# ---------------------------------------------------------------------- OSP staff (7.12 to 7.16)
@router.get("/osp/applications")
def list_all_applications(status: list[Status] | None = Query(None), kind: list[Kind] | None = Query(None),
                          verification: list[Verification] | None = Query(None), companyId: str | None = None,
                          page: int = Page, size: int = Size, _: dict = standin.perm(MODULE, "GET", "/osp/applications")):
    return interface.list_all(status, kind, verification, companyId, page, size)


@router.get("/osp/applications/{applicationId}")
def get_any_application(applicationId: str, _: dict = standin.perm(MODULE, "GET", "/osp/applications/{applicationId}")):
    return interface.with_review(interface.any_application(applicationId))


@router.get("/osp/applications/{applicationId}/documents/{documentId}")
def get_any_document(applicationId: str, documentId: str,
                     claims: dict = standin.perm(MODULE, "GET", "/osp/applications/{applicationId}/documents/{documentId}")):
    return _download(*interface.staff_document(applicationId, documentId, claims["sub"]))


@router.get("/osp/agreements")
def list_agreement_versions(agreementKey: str | None = None, status: Literal["ACTIVE", "INACTIVE"] | None = None,
                            page: int = Page, size: int = Size, _: dict = standin.perm(MODULE, "GET", "/osp/agreements")):
    return interface.list_agreement_versions(agreementKey, status, page, size)


@router.post("/osp/agreements", status_code=201)
def create_agreement_version(body: dict = Body(...), claims: dict = standin.perm(MODULE, "POST", "/osp/agreements")):
    return interface.create_agreement_version(body, claims["sub"])


# ------------------------------------------------------------------------- steps and queries (8, 9)
@router.post("/steps/complete-application")
def step_complete_application(body: dict = Body(...),
                              _: dict = standin.perm(MODULE, "POST", "/steps/complete-application")):
    return interface.complete_application(body)


@router.post("/steps/close-application")
def step_close_application(body: dict = Body(...), _: dict = standin.perm(MODULE, "POST", "/steps/close-application")):
    return interface.close_application(body)


@router.get("/internal/applications/{applicationId}")
def get_application_internal(applicationId: str,
                             _: dict = standin.perm(MODULE, "GET", "/internal/applications/{applicationId}")):
    return interface.get_application_internal(applicationId=applicationId)


@router.get("/internal/applications")
def list_applications_internal(applicationId: list[str] = Query(..., max_length=100),
                               _: dict = standin.perm(MODULE, "GET", "/internal/applications")):
    return interface.list_applications_internal(applicationId=applicationId)


@router.get("/internal/agreements")
def list_agreements_internal(status: Literal["ACTIVE", "INACTIVE"] | None = None,
                             _: dict = standin.perm(MODULE, "GET", "/internal/agreements")):
    return interface.list_agreements_internal(status=status)
