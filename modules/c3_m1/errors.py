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

Each factory takes the optional `detail` and, as named parameters, exactly the additional fields of README 12 it is
used with (`retryable` for steps, `reason`, `fields`, `missing`, `errors`). A field is in the answer only when the
caller passes it, so `retryable` appears exactly where it did before.
"""
from __future__ import annotations

from typing import TypedDict

from portal_common.problems import Problem

MODULE = "c3-m1"


class FieldError(TypedDict):
    """One entry of `errors` in a 400 answer: the field and why it is invalid."""
    field: str
    reason: str


Extra = bool | str | list[str] | list[FieldError]


def _problem(status: int, name: str, detail: str | None, **extra: Extra | None) -> Problem:
    """The Problem with the additional fields that were passed (None = not passed)."""
    problem = Problem(MODULE, status, name, detail=detail)
    problem.ext = {key: value for key, value in extra.items() if value is not None}
    return problem


def validation(detail: str | None = None, *, errors: list[FieldError] | None = None,
               retryable: bool | None = None) -> Problem:
    """400 `validation`: input invalid; the field errors in `errors`."""
    return _problem(400, "validation", detail, errors=errors, retryable=retryable)


def attestation_invalid(detail: str | None = None, *, reason: str | None = None) -> Problem:
    """400 `attestation-invalid`: verification attestation not acceptable; the reason in `reason` (6.7)."""
    return _problem(400, "attestation-invalid", detail, reason=reason)


def document_invalid(detail: str | None = None, *, errors: list[FieldError] | None = None) -> Problem:
    """400 `document-invalid`: supporting document missing, too large, too many or wrong type; details in `errors`."""
    return _problem(400, "document-invalid", detail, errors=errors)


def consent_missing(detail: str | None = None, *, missing: list[str] | None = None) -> Problem:
    """400 `consent-missing`: consent to terms of the role is missing (7.8); the terms in `missing`."""
    return _problem(400, "consent-missing", detail, missing=missing)


def not_found(detail: str | None = None, *, retryable: bool | None = None) -> Problem:
    """404 `not-found`: company, application, change request, document or role unknown, or not in scope `company`."""
    return _problem(404, "not-found", detail, retryable=retryable)


def invalid_state(detail: str | None = None, *, retryable: bool | None = None) -> Problem:
    """409 `invalid-state`: status does not allow the operation."""
    return _problem(409, "invalid-state", detail, retryable=retryable)


def conflict(detail: str | None = None, *, retryable: bool | None = None) -> Problem:
    """409 `conflict`: company belongs to another application, application does not match the company."""
    return _problem(409, "conflict", detail, retryable=retryable)


def field_locked(detail: str | None = None, *, fields: list[str] | None = None) -> Problem:
    """409 `field-locked`: field must not be changed (6.6); the fields in `fields`."""
    return _problem(409, "field-locked", detail, fields=fields)


def role_not_assignable(detail: str | None = None) -> Problem:
    """409 `role-not-assignable`: role must not be assigned or removed this way."""
    return _problem(409, "role-not-assignable", detail)


def last_role(detail: str | None = None) -> Problem:
    """409 `last-role`: last active role with `assignableBy` `COMPANY`."""
    return _problem(409, "last-role", detail)


def bpn_taken(detail: str | None = None, *, retryable: bool | None = None) -> Problem:
    """409 `bpn-taken`: BPN already belongs to another company of the installation."""
    return _problem(409, "bpn-taken", detail, retryable=retryable)


def bpn_mismatch(detail: str | None = None, *, retryable: bool | None = None) -> Problem:
    """409 `bpn-mismatch`: company already has a different BPN."""
    return _problem(409, "bpn-mismatch", detail, retryable=retryable)


def identifier_missing(detail: str | None = None, *, retryable: bool | None = None) -> Problem:
    """409 `identifier-missing`: activation without BPN."""
    return _problem(409, "identifier-missing", detail, retryable=retryable)


def roles_without_consent(detail: str | None = None, *, missing: list[str] | None = None,
                          retryable: bool | None = None) -> Problem:
    """409 `roles-without-consent`: no requested role with complete consents (activate-company); roles in `missing`."""
    return _problem(409, "roles-without-consent", detail, missing=missing, retryable=retryable)


def company_mismatch(detail: str | None = None, *, fields: list[str] | None = None,
                     retryable: bool | None = None) -> Problem:
    """409 `company-mismatch`: EBWOID or country of attestation or application does not match; `fields`."""
    return _problem(409, "company-mismatch", detail, fields=fields, retryable=retryable)


def attestation_used(detail: str | None = None) -> Problem:
    """409 `attestation-used`: verification attestation already used."""
    return _problem(409, "attestation-used", detail)


def attestation_outdated(detail: str | None = None) -> Problem:
    """409 `attestation-outdated`: verification attestation older than the state of the core data."""
    return _problem(409, "attestation-outdated", detail)


def representation_not_confirmed(detail: str | None = None) -> Problem:
    """409 `representation-not-confirmed`: representation not confirmed in the verification attestation."""
    return _problem(409, "representation-not-confirmed", detail)


def attestation_required(detail: str | None = None) -> Problem:
    """409 `attestation-required`: name or address with source `EBW` only with a verification attestation."""
    return _problem(409, "attestation-required", detail)


def change_request_open(detail: str | None = None) -> Problem:
    """409 `change-request-open`: already an open change request."""
    return _problem(409, "change-request-open", detail)


def change_requests_disabled(detail: str | None = None) -> Problem:
    """409 `change-requests-disabled`: change requests with supporting documents switched off."""
    return _problem(409, "change-requests-disabled", detail)


def same_person(detail: str | None = None) -> Problem:
    """409 `same-person`: approval of one's own change request."""
    return _problem(409, "same-person", detail)


def upstream_error(detail: str | None = None, *, retryable: bool | None = None) -> Problem:
    """502 `upstream-error`: C1-M2 or JWKS of the EBW-Connector not reachable or unexpected response."""
    return _problem(502, "upstream-error", detail, retryable=retryable)


def not_implemented(detail: str | None = None) -> Problem:
    """501 `not-implemented`: the configured store cannot be used (FRAMEWORK 4.5)."""
    return _problem(501, "not-implemented", detail)
