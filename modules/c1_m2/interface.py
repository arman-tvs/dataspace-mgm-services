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
"""Public interface of C1-M2 Registration (call convention of AGENTS.md; ADR-0003 "facade"): the steps
`complete-application` and `close-application`, the queries 9.1 to 9.3, and the operations of people and OSP staff
that `router.py` calls.

Every function delegates to `services/`; the data is in `store.py`, the calls to neighbours in `gateways.py`, the
errors of README 12 in `errors.py`.
"""
from __future__ import annotations

from collections.abc import Sequence

from .errors import MODULE
from .services import (
    agreements,
    applications,
    common,
    documents,
    lifecycle,
    queries,
    reference,
    steps,
    submission,
)

__all__ = ["MODULE"]


def reset() -> None:
    lifecycle.reset()


# ------------------------------------------------------------------------------------- views
def public(a: dict) -> dict:
    """`Application`: without the JWT and with the extract of the attestation only."""
    return common.public(a)


def summary(a: dict) -> dict:
    """`ApplicationSummary`."""
    return common.summary(a)


def with_review(a: dict) -> dict:
    """`Application` with `reviewStatus` (7.4)."""
    return common.with_review(a)


# ----------------------------------------------------------------------------- reference data (7.1)
def list_countries(lang: str) -> list[dict]:
    return reference.list_countries(lang)


def list_identifier_types(country_code: str, lang: str) -> list[dict]:
    return reference.list_identifier_types(country_code, lang)


def list_company_roles(lang: str) -> list[dict]:
    return reference.list_company_roles(lang)


def list_agreements(company_roles: list[str], lang: str) -> list[dict]:
    return reference.list_agreements(company_roles, lang)


# --------------------------------------------------------------------------- applications (7.2 to 7.11)
def create_application(body: dict, claims: dict) -> tuple[dict, bool]:
    """7.2: the application and whether it is new (201) or a repetition (200)."""
    return applications.create_application(body, claims)


def own(sub: str, application_id: str) -> dict:
    """Scope `own` (6.3): for other people the application does not exist."""
    return common.own(sub, application_id)


def any_application(application_id: str) -> dict:
    return common.any_application(application_id)


def list_own(sub: str, status: Sequence[str] | None, page: int, size: int) -> dict:
    return applications.list_own(sub, status, page, size)


def list_all(status: Sequence[str] | None, kind: Sequence[str] | None, verification: Sequence[str] | None,
             company_id: str | None, page: int, size: int) -> dict:
    return applications.list_all(status, kind, verification, company_id, page, size)


def update_application(application_id: str, sub: str, body: dict) -> dict:
    """7.5."""
    return applications.update_application(application_id, sub, body)


def replace_attestation(application_id: str, claims: dict, token: object) -> dict:
    """7.6."""
    return submission.replace_attestation(application_id, claims, token)


def submit_application(application_id: str, sub: str, body: dict) -> dict:
    """7.10."""
    return submission.submit_application(application_id, sub, body)


def withdraw_application(application_id: str, sub: str) -> dict:
    """7.11."""
    return applications.withdraw_application(application_id, sub)


# --------------------------------------------------------------------- supporting documents (7.7 to 7.9)
def document_max_bytes() -> int:
    return documents.document_max_bytes()


def upload_document(application_id: str, sub: str, document_type: str, file_name: str | None,
                    content: bytes) -> dict:
    return documents.upload_document(application_id, sub, document_type, file_name, content)


def document(a: dict, document_id: str) -> tuple[dict, bytes]:
    return documents.document(a, document_id)


def staff_document(application_id: str, document_id: str, sub: str) -> tuple[dict, bytes]:
    """7.14: every retrieval is in the audit log."""
    return documents.staff_document(application_id, document_id, sub)


def delete_document(application_id: str, document_id: str, sub: str) -> None:
    documents.delete_document(application_id, document_id, sub)


# ---------------------------------------------------------------------------- terms (7.15, 7.16)
def list_agreement_versions(agreement_key: str | None, status: str | None, page: int, size: int) -> dict:
    return agreements.list_agreement_versions(agreement_key, status, page, size)


def create_agreement_version(body: dict, sub: str) -> dict:
    """7.16."""
    return agreements.create_agreement_version(body, sub)


# --------------------------------------------------------------------------------- steps (README 8)
def complete_application(input: dict) -> dict:
    return steps.complete_application(input)


def close_application(input: dict) -> dict:
    return steps.close_application(input)


# ------------------------------------------------------------------------------- queries (README 9)
def get_application_internal(*, applicationId: str, **_other: object) -> dict:  # openapi names
    return queries.get_application_internal(applicationId=applicationId)


def list_applications_internal(*, applicationId: list[str] | str | None = None, **_other: object) -> list[dict]:
    return queries.list_applications_internal(applicationId=applicationId)


def list_agreements_internal(*, status: str | None = None, **_other: object) -> list[dict]:
    return queries.list_agreements_internal(status=status)
