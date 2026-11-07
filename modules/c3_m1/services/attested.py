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
"""Change with a verification attestation of the EBW-Connector (README 7.3, 6.3, 6.7)."""
from __future__ import annotations

from modules.c3_m1 import attestation, errors, store, validation
from modules.c3_m1.errors import MODULE
from portal_common import events

from .changes import _changed_fields
from .common import _timestamp, company_view, get_company


# ----------------------------------------------------- change with an attestation (7.3, 6.3, 6.7)
def _attested_values(row: dict, claims: dict) -> tuple[dict, dict[str, dict]]:
    """Name, address and identifiers from the claims (6.3); returns the fields and the identifiers."""
    company = claims.get("company") or {}
    fields = {"name": company.get("legal_name")}
    stored = {entry["type"]: entry for entry in store.list_identifiers(row["id"])}
    identifiers = [{"type": kind, "value": entry["value"], "source": entry["source"]}
                   for kind, entry in stored.items()]
    for entry in identifiers:
        if entry["type"] == "EBWOID":
            if not validation.same_value(entry["value"], company.get("ebwoid")):
                entry["value"] = company.get("ebwoid")
            entry["source"] = "BUSINESS_WALLET"
    if not any(entry["type"] == "EBWOID" for entry in identifiers):
        identifiers.append({"type": "EBWOID", "value": company.get("ebwoid"),
                            "source": "BUSINESS_WALLET"})
    if company.get("euid"):
        identifiers = [entry for entry in identifiers if entry["type"] != "EUID"]
        identifiers.append({"type": "EUID", "value": company["euid"], "source": "BUSINESS_WALLET"})

    address = company.get("address")
    if isinstance(address, dict):
        same_street = validation.same_value(
            " ".join(filter(None, (row["street"], row["house_number"]))), address.get("street_address"))
        same_city = (validation.same_value(row["postal_code"], address.get("postal_code"))
                     and validation.same_value(row["city"], address.get("locality")))
        if not (same_street and same_city):
            fields |= {"street": address.get("street_address"), "house_number": None,
                       "address_addition": None, "region": None,
                       "postal_code": address.get("postal_code"), "city": address.get("locality")}
    return fields, {entry["type"]: entry for entry in identifiers}


def update_company_from_attestation(companyId: str, body: dict, sub: str | None = None) -> dict:
    """7.3: core data from a new verification attestation, immediately and without OSP staff."""
    with store.lock(companyId):
        row = get_company(companyId)
        if row["status"] != "ACTIVE":
            raise errors.invalid_state(detail=row["status"])
        claims = attestation.verify(body.get("attestation") or "")
        claims["client_id"] = claims.get("client_id")

        if store.is_used(claims["jti"]):
            raise errors.attestation_used()
        if claims.get("representation", {}).get("confirmed") is not True:
            raise errors.representation_not_confirmed()
        company = claims.get("company") or {}
        stored = {entry["type"]: entry for entry in store.list_identifiers(companyId)}
        mismatched = []
        if not validation.same_value((stored.get("EBWOID") or {}).get("value"), company.get("ebwoid")):
            mismatched.append("EBWOID")
        if (row["country_code"] or "") != (company.get("country") or ""):
            mismatched.append("countryCode")
        if mismatched:
            raise errors.company_mismatch(fields=mismatched)
        verified_at = claims["_verified_at"].isoformat()
        stored_verified_at = _timestamp(row["core_data_verified_at"])
        if stored_verified_at is not None and claims["_verified_at"] <= stored_verified_at:
            raise errors.attestation_outdated()

        fields, identifiers = _attested_values(row, claims)
        invalid = validation.validate_company(fields, partial=True)
        invalid += validation.validate_identifiers(list(identifiers.values()), row["country_code"])
        if invalid:
            raise errors.validation(errors=invalid)

        changed = _changed_fields(row, fields, list(identifiers.values()))
        updates = dict(fields)
        updates |= {"core_data_source": "EBW", "core_data_verified_at": verified_at,
                    "verification_ref": claims["jti"]}
        store.update_company(companyId, **updates)
        store.set_identifiers(companyId, list(identifiers.values()))
        store.add_if_unused(claims["jti"], companyId)
        store.audit(companyId, sub, "updateCompanyFromAttestation", None,
                    {"changedFields": changed, "verificationRef": claims["jti"],
                     "old": {field: row.get(field) for field in
                             ("name", "street", "house_number", "postal_code", "city", "region")},
                     "new": fields})
        if changed:
            events.publish(MODULE, "CompanyDataChanged",
                           {"companyId": companyId, "changedFields": changed,
                            "coreDataChanged": True, "coreDataSource": "EBW"})
    return {"changedFields": changed, "company": company_view(companyId)}
