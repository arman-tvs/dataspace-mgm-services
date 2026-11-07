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
"""The errors of C3-M1 (README section 12, FRAMEWORK 4.5): one factory per `type`, the only place that builds a
`Problem` (ADR-0003).

Each factory takes the optional `detail` and the additional fields of README 12 (`retryable` for steps, `reason`,
`fields`, `missing`, `errors`) unchanged, so a call site sets exactly the fields it set before: `retryable` appears in
the answer only where the caller passes it.
"""
from __future__ import annotations

from typing import Any

from portal_common.problems import Problem

MODULE = "c3-m1"


def validation(detail: str | None = None, **ext: Any) -> Problem:
    """400 `validation`: input invalid; the field errors in `errors`."""
    return Problem(MODULE, 400, "validation", detail=detail, **ext)


def attestation_invalid(detail: str | None = None, **ext: Any) -> Problem:
    """400 `attestation-invalid`: verification attestation not acceptable; the reason in `reason` (6.7)."""
    return Problem(MODULE, 400, "attestation-invalid", detail=detail, **ext)


def document_invalid(detail: str | None = None, **ext: Any) -> Problem:
    """400 `document-invalid`: supporting document missing, too large, too many or wrong type; details in `errors`."""
    return Problem(MODULE, 400, "document-invalid", detail=detail, **ext)


def consent_missing(detail: str | None = None, **ext: Any) -> Problem:
    """400 `consent-missing`: consent to terms of the role is missing (7.8); the terms in `missing`."""
    return Problem(MODULE, 400, "consent-missing", detail=detail, **ext)


def not_found(detail: str | None = None, **ext: Any) -> Problem:
    """404 `not-found`: company, application, change request, document or role unknown, or not in scope `company`."""
    return Problem(MODULE, 404, "not-found", detail=detail, **ext)


def invalid_state(detail: str | None = None, **ext: Any) -> Problem:
    """409 `invalid-state`: status does not allow the operation."""
    return Problem(MODULE, 409, "invalid-state", detail=detail, **ext)


def conflict(detail: str | None = None, **ext: Any) -> Problem:
    """409 `conflict`: company belongs to another application, application does not match the company."""
    return Problem(MODULE, 409, "conflict", detail=detail, **ext)


def field_locked(detail: str | None = None, **ext: Any) -> Problem:
    """409 `field-locked`: field must not be changed (6.6); the fields in `fields`."""
    return Problem(MODULE, 409, "field-locked", detail=detail, **ext)


def role_not_assignable(detail: str | None = None, **ext: Any) -> Problem:
    """409 `role-not-assignable`: role must not be assigned or removed this way."""
    return Problem(MODULE, 409, "role-not-assignable", detail=detail, **ext)


def last_role(detail: str | None = None, **ext: Any) -> Problem:
    """409 `last-role`: last active role with `assignableBy` `COMPANY`."""
    return Problem(MODULE, 409, "last-role", detail=detail, **ext)


def bpn_taken(detail: str | None = None, **ext: Any) -> Problem:
    """409 `bpn-taken`: BPN already belongs to another company of the installation."""
    return Problem(MODULE, 409, "bpn-taken", detail=detail, **ext)


def bpn_mismatch(detail: str | None = None, **ext: Any) -> Problem:
    """409 `bpn-mismatch`: company already has a different BPN."""
    return Problem(MODULE, 409, "bpn-mismatch", detail=detail, **ext)


def identifier_missing(detail: str | None = None, **ext: Any) -> Problem:
    """409 `identifier-missing`: activation without BPN."""
    return Problem(MODULE, 409, "identifier-missing", detail=detail, **ext)


def roles_without_consent(detail: str | None = None, **ext: Any) -> Problem:
    """409 `roles-without-consent`: no requested role with complete consents (activate-company); roles in `missing`."""
    return Problem(MODULE, 409, "roles-without-consent", detail=detail, **ext)


def company_mismatch(detail: str | None = None, **ext: Any) -> Problem:
    """409 `company-mismatch`: EBWOID or country of attestation or application does not match; `fields`."""
    return Problem(MODULE, 409, "company-mismatch", detail=detail, **ext)


def attestation_used(detail: str | None = None, **ext: Any) -> Problem:
    """409 `attestation-used`: verification attestation already used."""
    return Problem(MODULE, 409, "attestation-used", detail=detail, **ext)


def attestation_outdated(detail: str | None = None, **ext: Any) -> Problem:
    """409 `attestation-outdated`: verification attestation older than the state of the core data."""
    return Problem(MODULE, 409, "attestation-outdated", detail=detail, **ext)


def representation_not_confirmed(detail: str | None = None, **ext: Any) -> Problem:
    """409 `representation-not-confirmed`: representation not confirmed in the verification attestation."""
    return Problem(MODULE, 409, "representation-not-confirmed", detail=detail, **ext)


def attestation_required(detail: str | None = None, **ext: Any) -> Problem:
    """409 `attestation-required`: name or address with source `EBW` only with a verification attestation."""
    return Problem(MODULE, 409, "attestation-required", detail=detail, **ext)


def change_request_open(detail: str | None = None, **ext: Any) -> Problem:
    """409 `change-request-open`: already an open change request."""
    return Problem(MODULE, 409, "change-request-open", detail=detail, **ext)


def change_requests_disabled(detail: str | None = None, **ext: Any) -> Problem:
    """409 `change-requests-disabled`: change requests with supporting documents switched off."""
    return Problem(MODULE, 409, "change-requests-disabled", detail=detail, **ext)


def same_person(detail: str | None = None, **ext: Any) -> Problem:
    """409 `same-person`: approval of one's own change request."""
    return Problem(MODULE, 409, "same-person", detail=detail, **ext)


def upstream_error(detail: str | None = None, **ext: Any) -> Problem:
    """502 `upstream-error`: C1-M2 or JWKS of the EBW-Connector not reachable or unexpected response."""
    return Problem(MODULE, 502, "upstream-error", detail=detail, **ext)


def not_implemented(detail: str | None = None, **ext: Any) -> Problem:
    """501 `not-implemented`: the configured store cannot be used (FRAMEWORK 4.5)."""
    return Problem(MODULE, 501, "not-implemented", detail=detail, **ext)
