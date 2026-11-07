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
"""Queries of C3-M2: the duplicate check at the CSP (README 9, 6.2) and the status of a company (README 7.1)."""
from __future__ import annotations

from typing import Any

from modules.c3_m2 import errors, store
from modules.c3_m2.adapters import csp
from modules.c3_m2.store import Registration

from . import csp_calls
from .common import COUNTRY


def _search(ebwoid: str | None, euid: str | None, identifiers: list[str], legal_name: str | None,
            country: str | None) -> dict[str, Any]:
    """The query parameters of `GET /companies`; 400 `validation` for an unusable search (README 9)."""
    for value in identifiers:
        kind, _, rest = value.partition(":")
        if not kind or not rest:
            raise errors.validation("identifier must have the form <type>:<value>")
    if country and not COUNTRY.match(country):
        raise errors.validation("country must be two upper-case letters")
    if not (ebwoid or euid or identifiers or (legal_name and country)):
        raise errors.validation("ebwoid, euid, identifier, or legalName with country is required")
    params: dict[str, Any] = {k: v for k, v in (("ebwoid", ebwoid), ("euid", euid), ("legalName", legal_name),
                                                ("country", country)) if v}
    if identifiers:
        params["identifier"] = identifiers
    return params


def find_companies(ebwoid: str | None, euid: str | None, identifier: list[str] | str | None,
                   legal_name: str | None, country: str | None) -> list[dict[str, Any]]:
    """Query findCompanies (README 9, 6.2): duplicate check at the CSP; one `CspCompanyMatch` per match."""
    identifiers = [identifier] if isinstance(identifier, str) else list(identifier or [])
    params = _search(ebwoid, euid, identifiers, legal_name, country)
    status, answer = csp_calls.call("find-companies", "GET", "/companies", params=params)
    if status == 400:
        raise errors.validation("the CSP rejected the search parameters")
    csp.raise_for(status, answer, ok=(200,))
    return csp.parse_matches(answer, csp.osp_id())


def registration_view(row: Registration) -> dict[str, str]:
    """A registration as `CspRegistration`; empty fields are left out."""
    view: dict[str, str | None] = {
        "companyId": row.company_id, "bpn": row.bpn, "status": row.status, "failureReason": row.failure_reason,
        "did": row.did, "membership": row.membership, "registeredAt": row.registered_at, "updatedAt": row.updated_at}
    return {k: v for k, v in view.items() if v is not None}


def get_csp_registration(company_id: str) -> dict[str, str]:
    """Operation getCspRegistration (README 7.1); 404 `not-found` without a registration."""
    row = store.registrations.get(company_id)
    if row is None or row.status is None:
        raise errors.not_found()
    return registration_view(row)
