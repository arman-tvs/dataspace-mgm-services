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
"""The errors of C1-M2 (README 12, ADR-0003 "error factories"): the only file that builds a `Problem`.

Each factory takes, as named parameters, exactly the additional fields README 12 and `openapi.yaml` give the error
(`errors`, `reason`, `fields`, `missing`, ...). `retryable` is set only where a step answers (README 12: "applies
only to steps"), so an answer carries it exactly where it did before.
"""
from __future__ import annotations

from typing import TypedDict

from portal_common.problems import Problem

MODULE = "c1-m2"


class FieldError(TypedDict):
    """One entry of `errors` in a 400 `validation` answer."""
    field: str
    message: str


class AgreementRef(TypedDict):
    """One entry of `missing` in a 400 `consents-incomplete` answer: terms and the version that is required."""
    agreementKey: str
    version: str


Extra = bool | str | None | list[str] | list[FieldError] | list[AgreementRef]


def _problem(status: int, name: str, detail: str | None = None, extra: dict[str, Extra] | None = None) -> Problem:
    problem = Problem(MODULE, status, name, detail=detail)
    problem.ext = dict(extra or {})
    return problem


def _retryable(retryable: bool | None) -> dict[str, Extra]:
    return {} if retryable is None else {"retryable": retryable}


def validation(errors: list[FieldError], *, retryable: bool | None = None) -> Problem:
    """400 `validation`: input invalid; details in `errors`. `retryable` only for a step."""
    return _problem(400, "validation", extra={"errors": errors} | _retryable(retryable))


def attestation_invalid(reason: str) -> Problem:
    """400 `attestation-invalid`: verification attestation not acceptable; the reason in `reason` (6.4)."""
    return _problem(400, "attestation-invalid", extra={"reason": reason})


def attestation_mismatch(fields: list[str]) -> Problem:
    """400 `attestation-mismatch`: a fixed field differs from the verification attestation; fields in `fields`."""
    return _problem(400, "attestation-mismatch", extra={"fields": fields})


def consents_incomplete(missing: list[AgreementRef]) -> Problem:
    """400 `consents-incomplete`: consent to required terms missing or with another version; list in `missing`."""
    return _problem(400, "consents-incomplete", extra={"missing": missing})


def documents_incomplete(missing_document_types: list[str], representation_declaration_missing: bool) -> Problem:
    """400 `documents-incomplete`: register extract or declaration of representation missing (path `DOCUMENTS`)."""
    return _problem(400, "documents-incomplete", extra={
        "missingDocumentTypes": missing_document_types,
        "representationDeclarationMissing": representation_declaration_missing})


def documents_disabled() -> Problem:
    """400 `documents-disabled`: the verification path `DOCUMENTS` is switched off."""
    return _problem(400, "documents-disabled")


def account_bound() -> Problem:
    """403 `account-bound`: creation with an account that is already bound to a company."""
    return _problem(403, "account-bound")


def not_found(*, retryable: bool | None = None) -> Problem:
    """404 `not-found`: application, supporting document or country does not exist or is not visible."""
    return _problem(404, "not-found", extra=_retryable(retryable))


def invalid_state(detail: str, *, retryable: bool | None = None) -> Problem:
    """409 `invalid-state`: status or verification path does not allow the operation or the step."""
    return _problem(409, "invalid-state", detail, _retryable(retryable))


def conflict(detail: str) -> Problem:
    """409 `conflict`: the version of the terms already exists."""
    return _problem(409, "conflict", detail)


def open_application_exists(existing_application_id: str) -> Problem:
    """409 `open-application-exists`: the person already has an open application; ID in `existingApplicationId`."""
    return _problem(409, "open-application-exists", extra={"existingApplicationId": existing_application_id})


def company_has_open_application() -> Problem:
    """409 `company-has-open-application`: there already is an open application for the existing company."""
    return _problem(409, "company-has-open-application")


def company_unknown() -> Problem:
    """409 `company-not-eligible` for a reference C3-M1 does not know (no `companyStatus`)."""
    return _problem(409, "company-not-eligible", "company unknown")


def company_not_eligible(company_status: str | None) -> Problem:
    """409 `company-not-eligible`: status or reason of the deactivation does not fit the kind; `companyStatus`."""
    return _problem(409, "company-not-eligible", extra={"companyStatus": company_status})


def attestation_used() -> Problem:
    """409 `attestation-used`: verification attestation (`jti`) already used."""
    return _problem(409, "attestation-used")


def attestation_expired() -> Problem:
    """409 `attestation-expired`: at submission the verification attestation is expired or too old."""
    return _problem(409, "attestation-expired")


def already_decided(review_status: str) -> Problem:
    """409 `already-decided`: withdrawal after the decision; `reviewStatus`."""
    return _problem(409, "already-decided", extra={"reviewStatus": review_status})


def upstream_error(detail: str, *, retryable: bool) -> Problem:
    """502 `upstream-error`: JWKS of the issuer, C3-M1 or C1-M3 not reachable (`retryable` as the caller decides)."""
    return _problem(502, "upstream-error", detail, {"retryable": retryable})
