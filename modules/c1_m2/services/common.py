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
"""Shared parts of the C1-M2 services: constants, time, audit log, field errors and the views of an
application (README 5, 7)."""
from __future__ import annotations

import datetime as dt

from modules.c1_m2 import attestation, errors, gateways, store
from modules.c1_m2.errors import FieldError
from portal_common.problems import Problem

KINDS = ("ONBOARDING", "REACTIVATION", "TRANSFER")
VERIFICATIONS = ("EBW", "DOCUMENTS")
OPEN = ("CREATED", "SUBMITTED")
DOCUMENT_TYPES = ("COMMERCIAL_REGISTER_EXTRACT", "POWER_OF_ATTORNEY", "OTHER")
IDENTIFIER_TYPES = ("EUID", "EBWOID", "COMMERCIAL_REG_NUMBER", "VAT_ID", "LEI_CODE", "EORI")
SIGNATURES = ((b"%PDF-", "application/pdf"), (b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"))
ATTESTATION_MAX_CHARS = 16384
SUMMARY_KEYS = ("attestationId", "issuer", "issuedAt", "expiresAt", "verifiedAt", "person", "representation")


def now_iso() -> str:
    return dt.datetime.fromtimestamp(attestation.now(), dt.UTC).isoformat()


def audit(a: dict, operation: str, sub: str | None = None, step: dict | None = None, object_id: str | None = None) -> None:
    store.audit_log.append({"at": now_iso(), "sub": sub, "processId": (step or {}).get("processId"),
                      "stepRunId": (step or {}).get("stepRunId"), "companyId": a["companyId"], "operation": operation,
                      "applicationId": a["id"], "objectId": object_id})


def err(field: str, message: str) -> FieldError:
    return {"field": field, "message": message}


def public(a: dict) -> dict:
    """`Application`: without the JWT and with the extract of the attestation only."""
    out = {k: v for k, v in a.items() if not k.startswith("_")}
    current = a.get("_attestation")
    out["attestation"] = {k: current[k] for k in SUMMARY_KEYS} if current else None
    return out


def summary(a: dict) -> dict:
    """`ApplicationSummary`."""
    return {"id": a["id"], "companyId": a["companyId"], "kind": a["kind"], "existingCompany": a["existingCompany"],
            "verification": a["verification"], "status": a["status"], "legalName": a["companyData"]["legalName"],
            "countryCode": a["companyData"]["address"].get("countryCode"), "companyRoles": a["companyRoles"],
            "createdAt": a["createdAt"], "submittedAt": a.get("submittedAt")}


def review_status(a: dict) -> str:
    """`reviewStatus` of 7.4."""
    if a["status"] == "CREATED":
        return "NONE"
    try:
        return gateways.review_status(a["id"]) or "NONE"
    except Problem:
        return "UNKNOWN"


def with_review(a: dict) -> dict:
    return public(a) | {"reviewStatus": review_status(a)}


def paged(items: list[dict], page: int, size: int) -> dict:
    return {"items": items[page * size:(page + 1) * size], "page": page, "size": size, "total": len(items)}


def own(sub: str, application_id: str) -> dict:
    """Scope `own` (6.3): for other people the application does not exist."""
    a = store.applications.get(application_id)
    if not a or a["applicant"]["sub"] != sub:
        raise errors.not_found()
    return a


def any_application(application_id: str) -> dict:
    a = store.applications.get(application_id)
    if not a:
        raise errors.not_found()
    return a
