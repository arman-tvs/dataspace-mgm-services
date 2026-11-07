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
"""Public interface of C3-M1 Company Profile: the steps of Process Orchestration (README 8), the
queries of other modules (9) and the read paths.

This file is the facade of ADR-0003: each function delegates to `services/`, where the rules live.
Names and signatures follow the call convention of AGENTS.md: a step is
`def create_company(input: dict) -> dict` returning `{stepRunId, state, result}`, a query takes its
parameters by their openapi names. No token checks here.

Steps are idempotent (FRAMEWORK 4.4): the business key is looked up first, only what is missing is
created, a repetition returns the stored result and publishes nothing. Every changing operation
writes the audit log of README 5 and FRAMEWORK 4.3 before it publishes.
"""

from __future__ import annotations

from .errors import MODULE
from .services import attested, change_requests, common, lifecycle, onboarding, profile, queries, roles
from .services.changes import CAMEL, CORE_IDENTIFIERS, CORE_TEXT_FIELDS
from .services.profile import OSP_LOCKED_FIELDS


# ----------------------------------- start and the views of a company (README 4, 5, 7.1, 7.11, 9.1)
def reset() -> None:
    """Empty state, then the seed data of the OSP company (README 4). Seed data has no events."""
    common.reset()


def get_company(cid: str | None) -> dict:
    """The stored company, or 404 `not-found` (README 5)."""
    return common.get_company(cid)


def company_view(cid: str | None, *, detail: bool = False) -> dict:
    """`Company` (7.1) and `CompanyDetail` (7.11) in camelCase, with the dataspace name for people."""
    return common.company_view(cid, detail=detail)


def company_internal(cid: str | None) -> dict:
    """`CompanyInternal` (9.1): address, identifiers, source and active roles for other modules."""
    return common.company_internal(cid)


def role_view(cid: str | None) -> dict:
    """`Company` of the paths for people (7.1, 7.7): roles with status, so a role can read REQUESTED."""
    return common.role_view(cid)


# ------------------------------------------------------------------ steps of onboarding (8.1 - 8.4)
def create_company(input: dict) -> dict:
    """8.1: create the company `REQUESTED` from a submitted application of kind ONBOARDING/TRANSFER."""
    return onboarding.create_company(input)


def assign_identifier(input: dict) -> dict:
    """8.2: take over the BPN from `CompanyRegisteredAtCsp`."""
    return onboarding.assign_identifier(input)


def activate_company(input: dict) -> dict:
    """8.3: activate, taking over the consents of the application."""
    return onboarding.activate_company(input)


def reject_company(input: dict) -> dict:
    """8.4: `REJECTED`, final; an assigned BPN becomes free."""
    return onboarding.reject_company(input)


# ------------------------------------------- deactivation, return and reactivation (7.13, 8.5, 8.6)
def deactivate_company(input: dict) -> dict:
    """8.5: deactivation by Process Orchestration with reason `MANUAL` or `TRANSFERRED`."""
    return lifecycle.deactivate_company(input)


def deactivate_company_by_staff(companyId: str, body: dict, sub: str | None = None) -> dict:
    """7.13: manual deactivation by OSP staff, always with a justification."""
    return lifecycle.deactivate_company_by_staff(companyId, body, sub)


def reactivate_company(input: dict) -> dict:
    """8.6: back to ACTIVE from an approved application of the matching kind."""
    return lifecycle.reactivate_company(input)


# ------------------------------ search for OSP staff and queries of other modules (7.10, 9.1 - 9.3)
def list_companies(
    *,
    status: list[str] | str | None = None,
    name: str | None = None,
    bpn: str | None = None,
    hasBpn: bool | str | None = None,
    companyRole: str | None = None,
    coreDataSource: str | None = None,
    page: int | str = 0,
    size: int | str = 20,
) -> dict:
    """7.10: filters, newest first, paged; `companyRole` matches active roles only."""
    return queries.list_companies(
        status=status,
        name=name,
        bpn=bpn,
        hasBpn=hasBpn,
        companyRole=companyRole,
        coreDataSource=coreDataSource,
        page=page,
        size=size,
    )


def query_company_role_catalog(*, lang: str | None = None, **_other: object) -> list[dict]:
    """9.4: role catalogue with descriptions in `lang`; the terms of the roles are at C1-M2 (9.3)."""
    return queries.query_company_role_catalog(lang=lang, **_other)


def query_company(*, companyId: str) -> dict:
    """9.1: `CompanyInternal` of one company."""
    return queries.query_company(companyId=companyId)


def query_companies(*, id: list[str] | str | None = None, bpn: list[str] | str | None = None, **_other: object) -> dict:
    """9.2: exactly one of `id` and `bpn`, 1 to QUERY_MAX_COMPANIES values."""
    return queries.query_companies(id=id, bpn=bpn, **_other)


def find_identifier_matches(
    *,
    identifiers: list[dict],
    name: str | None = None,
    excludeCompanyId: str | None = None,
    statuses: list[str] | str | None = None,
    **_other: object,
) -> dict:
    """9.3: local duplicate search; the caller decides whether a match is a duplicate."""
    return queries.find_identifier_matches(
        identifiers=identifiers, name=name, excludeCompanyId=excludeCompanyId, statuses=statuses, **_other
    )


# --------------------------------------- changes by people and corrections by OSP staff (7.2, 7.12)
def update_company(companyId: str, body: dict, sub: str | None = None) -> dict:
    """7.2: the Company Admin changes the short name."""
    return profile.update_company(companyId, body, sub)


def correct_company(companyId: str, body: dict, sub: str | None = None) -> dict:
    """7.12: correction by OSP staff, always with a justification."""
    return profile.correct_company(companyId, body, sub)


# ----------------------------------------------------- change with a verification attestation (7.3)
def update_company_from_attestation(companyId: str, body: dict, sub: str | None = None) -> dict:
    """7.3: core data from a new verification attestation, immediately and without OSP staff."""
    return attested.update_company_from_attestation(companyId, body, sub)


# ------------------------------------------------------------------------ company roles (7.7 - 7.9)
def list_company_roles(companyId: str, lang: str | None = None) -> list[dict]:
    """7.7"""
    return roles.list_company_roles(companyId, lang)


def add_company_role(companyId: str, body: dict, sub: str | None = None, lang: str | None = None) -> list[dict]:
    """7.8"""
    return roles.add_company_role(companyId, body, sub, lang)


def remove_company_role(
    companyId: str, companyRole: str, sub: str | None = None, lang: str | None = None
) -> list[dict]:
    """7.9"""
    return roles.remove_company_role(companyId, companyRole, sub, lang)


# ---------------------------------------- change requests and their review (7.4 - 7.6, 7.14 - 7.18)
def create_change_request(
    companyId: str, data: dict, documents: list[tuple[str, bytes, str | None]], sub: str | None = None
) -> dict:
    """7.4: a change request with supporting documents."""
    return change_requests.create_change_request(companyId, data, documents, sub)


def list_own_change_requests(companyId: str, page: int = 0, size: int = 20) -> dict:
    """7.5: own change requests, newest first, without `decidedBy`."""
    return change_requests.list_own_change_requests(companyId, page, size)


def withdraw_change_request(companyId: str, changeRequestId: str, sub: str | None = None) -> dict:
    """7.6"""
    return change_requests.withdraw_change_request(companyId, changeRequestId, sub)


def list_change_requests(
    *, status: list[str] | str | None = None, companyId: str | None = None, page: int | str = 0, size: int | str = 20
) -> dict:
    """7.14: all change requests, oldest first."""
    return change_requests.list_change_requests(status=status, companyId=companyId, page=page, size=size)


def get_change_request(changeRequestId: str) -> dict:
    """7.15: the request with the current state of the company."""
    return change_requests.get_change_request(changeRequestId)


def get_change_request_document(changeRequestId: str, documentId: str, sub: str | None = None) -> dict:
    """7.16: content, media type and file name; the read is audited."""
    return change_requests.get_change_request_document(changeRequestId, documentId, sub)


def approve_change_request(changeRequestId: str, body: dict | None = None, sub: str | None = None) -> dict:
    """7.17"""
    return change_requests.approve_change_request(changeRequestId, body, sub)


def decline_change_request(changeRequestId: str, body: dict | None = None, sub: str | None = None) -> dict:
    """7.18"""
    return change_requests.decline_change_request(changeRequestId, body, sub)


__all__ = [
    "CAMEL",
    "CORE_IDENTIFIERS",
    "CORE_TEXT_FIELDS",
    "MODULE",
    "OSP_LOCKED_FIELDS",
    "activate_company",
    "add_company_role",
    "approve_change_request",
    "assign_identifier",
    "company_internal",
    "company_view",
    "correct_company",
    "create_change_request",
    "create_company",
    "deactivate_company",
    "deactivate_company_by_staff",
    "decline_change_request",
    "find_identifier_matches",
    "get_change_request",
    "get_change_request_document",
    "get_company",
    "list_change_requests",
    "list_companies",
    "list_company_roles",
    "list_own_change_requests",
    "query_companies",
    "query_company",
    "query_company_role_catalog",
    "reactivate_company",
    "reject_company",
    "remove_company_role",
    "reset",
    "role_view",
    "update_company",
    "update_company_from_attestation",
    "withdraw_change_request",
]
