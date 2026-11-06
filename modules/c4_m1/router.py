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
"""HTTP layer of C4-M1 Credentials (README 6.5, 7, 8, 9): token, permission, then the interface function.

Operations that this router does not implement are answered by the spec-driven fallback of the scaffold.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from fastapi import Body, Query
from fastapi.responses import Response

from portal_common import standin

from . import interface, service
from .interface import MODULE

router = standin.router(MODULE)


def reset() -> None:
    interface.reset()


@router.post("/steps/issue-credentials")
def issue(body: dict = Body(...), _: dict = standin.perm(MODULE, "POST", "/steps/issue-credentials")):
    return interface.issue_credentials(body)


@router.post("/steps/revoke-credentials")
def revoke(body: dict = Body(...), _: dict = standin.perm(MODULE, "POST", "/steps/revoke-credentials")):
    return interface.revoke_credentials(body)


@router.post("/issuer-callbacks/{credentialKind}", status_code=204, response_class=Response)
def issuer_callback(credentialKind: str, body: dict = Body(...),
                    claims: dict = standin.perm(MODULE, "POST", "/issuer-callbacks/{credentialKind}")):
    """README 7.4: token and permission (dependency), kind, body, row handling, audit entry, 204 without body."""
    bpn, status, message = service.validate_report(credentialKind, body)
    interface.report_status(credentialKind, bpn, status, message)
    service.audit(claims, "REPORT_CREDENTIAL_STATUS", None, f"{bpn}:{credentialKind.upper()}", 204)
    return Response(status_code=204)


@router.get("/internal/companies/{companyId}/credentials")
def query_credentials(companyId: str,
                      _: dict = standin.perm(MODULE, "GET", "/internal/companies/{companyId}/credentials")):
    return interface.query_company_credentials(companyId=companyId)


@router.get("/companies/{companyId}/credentials")
def own_credentials(companyId: str, claims: dict = standin.perm(MODULE, "GET", "/companies/{companyId}/credentials")):
    """README 7.1; order of checks per 6.5: token, permission, then `company_id` of the token = `companyId`."""
    standin.company_scope(MODULE, claims, companyId)
    return service.list_company_credentials(companyId)


@router.get("/credentials")
def list_credentials(page: int = Query(0, ge=0), size: int = Query(20, ge=1, le=100),
                     status: list[Literal["REQUESTED", "ISSUED", "FAILED", "CANCELLED", "REVOCATION_PENDING",
                                          "REVOKED"]] | None = Query(None),
                     credentialType: Literal["BPN", "MEMBERSHIP"] | None = None,
                     companyId: uuid.UUID | None = None,
                     route: Literal["CREDENTIAL_ISSUER", "ISSUER_SERVICE", "CSP_ISSUER", "STUB"] | None = None,
                     requestedBefore: dt.datetime | None = None,
                     _: dict = standin.perm(MODULE, "GET", "/credentials")):
    """README 7.2 (OSP staff, `manage_credentials`)."""
    return interface.list_credentials(statuses=status, credential_type=credentialType,
                                      company_id=str(companyId) if companyId else None, route=route,
                                      requested_before=requestedBefore, page=page, size=size)


@router.post("/credentials/{credentialId}/confirm-revocation")
def confirm_revocation(credentialId: str, body: dict = Body(...),
                       claims: dict = standin.perm(MODULE, "POST", "/credentials/{credentialId}/confirm-revocation")):
    """README 7.3 (OSP staff, `manage_credentials`)."""
    return interface.confirm_revocation(credentialId, body, claims)
