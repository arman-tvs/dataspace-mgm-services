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
"""Changes of the core data by people (README 7.2) and corrections by OSP staff (7.12)."""
from __future__ import annotations

from modules.c3_m1 import errors, store, validation
from modules.c3_m1.errors import MODULE
from portal_common import events

from .changes import (
    CORE_TEXT_FIELDS,
    _changed_fields,
    _identifier_core_changed,
    _validate_merge,
    _wallet_identifier_conflict,
)
from .common import _now, company_view, get_company

# ------------------------------------------------------------------------ change by people (7.2)






def _identifiers_from(body: dict) -> list[dict] | None:
    if "identifiers" not in body:
        return None
    return [{"type": entry.get("type"), "value": entry.get("value"),
             "source": entry.get("source") or "DECLARED"} for entry in body.get("identifiers") or []]


def update_company(companyId: str, body: dict, sub: str | None = None) -> dict:
    """7.2: the Company Admin changes the short name."""
    with store.lock(companyId):
        row = get_company(companyId)
        if row["status"] != "ACTIVE":
            raise errors.invalid_state(detail=row["status"])
        locked = [key for key in body if validation.field_name(key) not in ("short_name",)]
        if locked:
            raise errors.field_locked(fields=locked)
        invalid = validation.validate_company(body, partial=True)
        if invalid:
            raise errors.validation(errors=invalid)
        changed = _changed_fields(row, body, None)
        if not changed:
            return company_view(companyId)
        before = {"short_name": row["short_name"]}
        store.update_company(companyId, short_name=validation.flat_fields(body).get("short_name"))
        store.audit(companyId, sub, "updateCompany", None,
                    {"changedFields": changed, "old": before,
                     "new": {key: body.get(key) for key in body}})
        events.publish(MODULE, "CompanyDataChanged",
                       {"companyId": companyId, "changedFields": changed, "coreDataChanged": False,
                        "coreDataSource": row["core_data_source"]})
    return company_view(companyId)


# ----------------------------------------------------------------- correction by OSP staff (7.12)
OSP_LOCKED_FIELDS = {"bpn", "status", "coreDataSource", "applicationId", "verificationRef",
                     "deactivationReason", "createdAt", "changedAt"}


def _locked_for_staff(row: dict, fields: dict) -> list[str]:
    """Fields OSP staff may not correct (6.6, 7.12); the country only while REQUESTED and without a BPN."""
    locked = [key for key in fields if key not in CORE_TEXT_FIELDS + ("short_name",)]
    if "country_code" in fields and (row["status"] != "REQUESTED" or row["bpn"]):
        locked.append("countryCode")
    return locked


def correct_company(companyId: str, body: dict, sub: str | None = None) -> dict:
    """7.12: correction by OSP staff, always with a justification."""
    with store.lock(companyId):
        row = get_company(companyId)
        if row["status"] in ("REJECTED", "INACTIVE"):
            raise errors.invalid_state(detail=row["status"])
        invalid = validation.validate_reason(body.get("reason"))
        identifiers = _identifiers_from(body)
        fields = {key: value for key, value in validation.flat_fields(body).items()
                  if key not in ("reason", "identifiers")}

        locked = _locked_for_staff(row, fields)
        if locked:
            raise errors.field_locked(fields=locked)

        if identifiers is not None:
            wallet = [{"type": entry["type"], "value": entry["value"], "source": entry["source"]}
                      for entry in store.list_identifiers(companyId)
                      if entry["source"] == "BUSINESS_WALLET"]
            invalid += validation.validate_identifiers(list(identifiers) + wallet, row["country_code"])
            invalid += _wallet_identifier_conflict(row, identifiers)
        invalid += validation.validate_company(_validate_merge(row, fields), partial=False)
        if invalid:
            raise errors.validation(errors=invalid)

        changed = _changed_fields(row, fields, identifiers)
        if not changed:
            return company_view(companyId, detail=True)

        core_changed = any(validation.field_name(key) in CORE_TEXT_FIELDS for key in fields)
        if identifiers is not None and _identifier_core_changed(row, identifiers):
            core_changed = True
        updates = validation.flat_fields(fields)
        if core_changed:
            updates["core_data_verified_at"] = _now()
            if row["core_data_source"] == "EBW":
                updates["core_data_source"] = "MANUAL"
                updates["verification_ref"] = None
        store.update_company(companyId, **updates)
        if identifiers is not None:
            store.set_identifiers(companyId, identifiers)
        store.audit(companyId, sub, "correctCompany", None,
                    {"changedFields": changed, "reason": body.get("reason"),
                     "old": {field: row.get(field) for field in updates},
                     "new": fields})
        events.publish(MODULE, "CompanyDataChanged",
                       {"companyId": companyId, "changedFields": changed,
                        "coreDataChanged": core_changed,
                        "coreDataSource": updates.get("core_data_source", row["core_data_source"])})
    return company_view(companyId, detail=True)
