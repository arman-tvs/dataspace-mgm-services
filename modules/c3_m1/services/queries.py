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
"""The search for OSP staff (README 7.10) and the queries of other modules (9.1 - 9.3)."""
from __future__ import annotations

from modules.c3_m1 import config, errors, store, validation

from .common import company_internal


# ---------------------------------------------------------------------- search for OSP (7.10)
def _summary(row: dict) -> dict:
    return {"id": row["id"], "name": row["name"], "status": row["status"], "bpn": row["bpn"],
            "coreDataSource": row["core_data_source"], "countryCode": row["country_code"],
            "companyRoles": [role for role, status in store.list_roles(row["id"]).items()
                             if status == "ACTIVE"],
            "createdAt": row["created_at"]}


def list_companies(*, status: list[str] | str | None = None, name: str | None = None,
                   bpn: str | None = None, hasBpn: bool | str | None = None,
                   companyRole: str | None = None, coreDataSource: str | None = None,
                   page: int | str = 0, size: int | str = 20) -> dict:
    """7.10: filters, newest first, paged; `companyRole` matches active roles only."""
    has_bpn = None if hasBpn in (None, "") else str(hasBpn).lower() in ("1", "true", "yes")
    try:
        items, total = store.find_companies(
            status=status, name=name, bpn=bpn, has_bpn=has_bpn, company_role=companyRole,
            core_data_source=coreDataSource, page=int(page or 0), size=int(size or 20))
    except ValueError as error:
        raise errors.validation(errors=[{"field": "filter", "reason": str(error)}]) from error
    return {"items": [_summary(row) for row in items], "page": int(page or 0),
            "size": int(size or 20), "total": total}


# --------------------------------------------------------------------------- queries (9.1 - 9.3)
def query_company_role_catalog(*, lang: str | None = None, **_other: object) -> list[dict]:
    """9.4: role catalogue with descriptions in `lang`; the terms of the roles are at C1-M2 (9.3)."""
    wanted = lang or "en"
    return [{"companyRole": role, "assignableBy": entry.get("assignableBy"),
             "description": config.description(role, wanted),
             "descriptions": entry.get("descriptions") or {}}
            for role, entry in config.role_catalogue().items()]


def query_company(*, companyId: str) -> dict:
    """9.1"""
    return company_internal(companyId)


def query_companies(*, id: list[str] | str | None = None, bpn: list[str] | str | None = None,
                    **_other: object) -> dict:
    """9.2: exactly one of `id` and `bpn`, 1 to QUERY_MAX_COMPANIES values."""
    ids = [id] if isinstance(id, str) else list(id or [])
    bpns = [bpn] if isinstance(bpn, str) else list(bpn or [])
    if bool(ids) == bool(bpns):
        raise errors.validation(errors=[{"field": "id,bpn", "reason": "exactly one of both"}])
    if len(ids + bpns) > config.query_max_companies():
        raise errors.validation(errors=[{"field": "id,bpn", "reason": "too many values"}])
    items, found = [], set()
    for wanted in ids:
        if store.get_company(wanted) is not None:
            items.append(company_internal(wanted))
            found.add(wanted)
    for wanted in bpns:
        rows = store.find_companies(bpn=wanted, size=config.query_max_companies())[0]
        live = [row for row in rows if row["status"] != "REJECTED"] or rows
        for other in live:
            items.append(company_internal(other["id"]))
            found.add(wanted)
    return {"items": items, "notFound": [value for value in ids + bpns if value not in found]}


def find_identifier_matches(*, identifiers: list[dict], name: str | None = None,
                            excludeCompanyId: str | None = None,
                            statuses: list[str] | str | None = None, **_other: object) -> dict:
    """9.3: local duplicate search; the caller decides whether a match is a duplicate."""
    wanted_statuses = [statuses] if isinstance(statuses, str) else list(statuses or [])
    _check_match_request(identifiers, wanted_statuses)
    candidates = _all_companies(wanted_statuses or ["REQUESTED", "ACTIVE", "INACTIVE"])
    wanted_name = validation.normalise(name) if name else None
    matches = []
    for row in candidates:
        if row["id"] == excludeCompanyId:
            continue
        matched = _matched_on(row, identifiers)
        if wanted_name and validation.normalise(row["name"]) == wanted_name:
            matched.append("NAME")
        if matched:
            matches.append({"companyId": row["id"], "name": row["name"], "status": row["status"],
                            "bpn": row["bpn"], "matchedOn": matched})
    matches.sort(key=lambda match: len(match["matchedOn"]), reverse=True)
    return {"matches": matches}


def _check_match_request(identifiers: list[dict], wanted_statuses: list[str]) -> None:
    """400 `validation` for 9.3: 1 to 10 identifiers of known types with values, known statuses."""
    invalid = []
    if not 1 <= len(identifiers) <= 10:
        invalid.append({"field": "identifiers", "reason": "1 to 10 entries"})
    for entry in identifiers:
        if entry.get("type") not in (*store.IDENTIFIER_TYPES, "BPN"):
            invalid.append({"field": "identifiers.type", "reason": str(entry.get("type"))})
        if not entry.get("value"):
            invalid.append({"field": "identifiers.value", "reason": "required"})
    for value in wanted_statuses:
        if value not in store.STATUSES:
            invalid.append({"field": "statuses", "reason": value})
    if invalid:
        raise errors.validation(errors=invalid)


def _all_companies(statuses: list[str]) -> list[dict]:
    """Every company with one of the statuses, page by page."""
    candidates: list[dict] = []
    page, total = 0, None
    while total is None or len(candidates) < total:
        batch, total = store.find_companies(status=statuses, page=page, size=100)
        candidates += batch
        if not batch:
            break
        page += 1
    return candidates


def _matched_on(row: dict, identifiers: list[dict]) -> list[str]:
    """The identifier types (and BPN) of the request that the company has, normalised."""
    own = {(entry["type"], entry["value_normalized"]) for entry in store.list_identifiers(row["id"])}
    if row["bpn"]:
        own.add(("BPN", validation.value_normalized(row["bpn"])))
    return sorted({entry["type"] for entry in identifiers
                   if (entry["type"], validation.value_normalized(entry["value"])) in own})
