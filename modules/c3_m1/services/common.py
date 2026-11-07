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
"""Shared parts of the C3-M1 services: time, audit, start and seed (README 4), the views of a company
(5, 7.1, 7.11, 9.1)."""
from __future__ import annotations

import datetime as dt

from modules.c3_m1 import attestation, config, errors, store
from portal_common.problems import Problem


def _timestamp(value: str | None) -> dt.datetime | None:
    """Parse a stored ISO timestamp (`Z` or offset) to an instant; `None` when unreadable."""
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _audit(company_id: str | None, operation: str, input: dict, details: dict | None = None) -> None:
    """Steps carry `processId` and `stepRunId` instead of a `sub` (README 5, 4.3)."""
    store.audit(company_id, None, operation, None,
                (details or {}) | {"processId": input.get("processId"),
                                   "stepRunId": input.get("stepRunId")})


# ------------------------------------------------------------------------ start and seed (README 4)
def reset() -> None:
    """Empty state, then the seed data of the OSP company (README 4). Seed data has no events."""
    try:
        store.reset()
        target = store
    except Problem as error:
        if error.status != 501:
            raise
        # the start survives an unusable database; the seed then lands in memory, calls answer 501
        target = store.backend_memory()
        target.reset()
    attestation.reset()
    seed = config.seed_company()
    if not seed or target.get_company(config.osp_company_id()) is not None:
        return
    address = seed.get("address") or {}
    target.create_company({
        "id": seed["companyId"], "name": seed["name"], "bpn": seed.get("bpn"),
        "street": address.get("street"), "house_number": address.get("houseNumber"),
        "postal_code": address.get("postalCode"), "city": address.get("city"),
        "region": address.get("region"), "country_code": address.get("countryCode"),
        "status": "ACTIVE", "core_data_source": "MANUAL",
    })
    target.set_identifiers(seed["companyId"], seed.get("identifiers") or [])
    for role in seed.get("companyRoles") or []:
        target.add_role(seed["companyId"], role, status="ACTIVE", source_kind="SEED",
                        source_ref="ospCompanyFile")


# ---------------------------------------------------------------------------------- mapping (5)
def get_company(cid: str | None) -> dict:
    row = store.get_company(cid)
    if row is None:
        raise errors.not_found(retryable=False)
    return row


def _address(row: dict) -> dict:
    return {key: row.get(field) for key, field in
            (("street", "street"), ("houseNumber", "house_number"),
             ("addressAddition", "address_addition"), ("postalCode", "postal_code"),
             ("city", "city"), ("region", "region"), ("countryCode", "country_code"))}


def _identifiers(row: dict) -> list[dict]:
    return [{"type": entry["type"], "value": entry["value"], "source": entry["source"]}
            for entry in store.list_identifiers(row["id"])]


def _active_roles(company: str | None) -> list[str]:
    return sorted(role for role, status in store.list_roles(company).items() if status == "ACTIVE")


def _roles(row: dict) -> list[dict]:
    return [{"companyRole": role, "status": status}
            for role, status in store.list_roles(row["id"]).items()]


def company_view(cid: str | None, *, detail: bool = False) -> dict:
    """`Company` (7.1) and `CompanyDetail` (7.11) in camelCase, with the dataspace name for people."""
    row = get_company(cid)
    view = {"id": row["id"], "name": row["name"], "shortName": row["short_name"],
            "address": _address(row), "identifiers": _identifiers(row),
            "coreDataSource": row["core_data_source"],
            "coreDataVerifiedAt": row["core_data_verified_at"], "bpn": row["bpn"],
            "status": row["status"], "companyRoles": _roles(row),
            "createdAt": row["created_at"], "dataspaceName": config.dataspace_name()}
    if detail:
        view |= {"applicationId": row["application_id"], "verificationRef": row["verification_ref"],
                 "bpnAssignedAt": row["bpn_assigned_at"],
                 "deactivationReason": row["deactivation_reason"],
                 "changedAt": row["changed_at"], "activatedAt": row["activated_at"],
                 "rejectedAt": row["rejected_at"], "deactivatedAt": row["deactivated_at"],
                 "reactivatedAt": row["reactivated_at"],
                 "openChangeRequestId": (store.open_change_request(row["id"]) or {}).get("id")}
    return view


def company_internal(cid: str | None) -> dict:
    """`CompanyInternal` (9.1): address, identifiers, source and active roles for other modules."""
    row = get_company(cid)
    return {"id": row["id"], "name": row["name"], "shortName": row["short_name"],
            "address": {key: row.get(field) for key, field in
                        (("street", "street"), ("houseNumber", "house_number"),
                         ("postalCode", "postal_code"), ("city", "city"),
                         ("region", "region"), ("countryCode", "country_code"))},
            "identifiers": _identifiers(row), "coreDataSource": row["core_data_source"],
            "status": row["status"], "bpn": row["bpn"],
            "companyRoles": [role for role, status in store.list_roles(row["id"]).items()
                             if status == "ACTIVE"],
            "deactivationReason": row["deactivation_reason"], "createdAt": row["created_at"],
            "activatedAt": row["activated_at"], "deactivatedAt": row["deactivated_at"]}


def role_view(cid: str | None) -> dict:
    """`Company` of the paths for people (7.1, 7.7): roles with status, so a role can read REQUESTED."""
    row = get_company(cid)
    view = company_view(cid)
    view["companyRoles"] = [{"companyRole": role, "status": status}
                            for role, status in store.list_roles(row["id"]).items()]
    return view
