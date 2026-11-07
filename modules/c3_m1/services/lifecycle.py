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
"""Deactivation, return and reactivation (README 7.13, 8.5, 8.6)."""
from __future__ import annotations

from modules.c3_m1 import errors, gateways, store, validation
from modules.c3_m1.errors import MODULE
from portal_common import events, standin

from .changes import CORE_IDENTIFIERS, _changed_fields
from .common import _active_roles, _now, company_view, get_company


# ---------------------------------------------------------------- deactivation and return (7.13, 8.5, 8.6)
def deactivate_company(input: dict) -> dict:
    """8.5: deactivation by Process Orchestration with reason `MANUAL` or `TRANSFERRED`."""
    cid, reason = input.get("companyId"), input.get("reason")
    with store.lock(cid):
        row = get_company(cid)
        if row["status"] == "INACTIVE":
            _check_deactivation_reason(reason)
            if reason == "TRANSFERRED" and row["deactivation_reason"] == "MANUAL":
                store.update_company(cid, deactivation_reason="TRANSFERRED")
                store.audit(cid, None, "stepDeactivateCompany", None,
                            {"deactivationReason": ["MANUAL", "TRANSFERRED"],
                             "processId": input.get("processId"),
                             "stepRunId": input.get("stepRunId")})
            return standin.step_reply(input, {"companyId": cid, "status": row["status"],
                                              "deactivationReason": row["deactivation_reason"]})
        if row["status"] != "ACTIVE":
            raise errors.invalid_state(detail=row["status"], retryable=False)
        _check_deactivation_reason(reason)
        store.update_company(cid, status="INACTIVE", deactivation_reason=reason,
                             deactivated_at=_now())
        store.audit(cid, None, "stepDeactivateCompany", None,
                    {"deactivationReason": reason, "processId": input.get("processId"),
                     "stepRunId": input.get("stepRunId")})
        events.publish(MODULE, "CompanyDeactivated", {"companyId": cid, "reason": reason})
    return standin.step_reply(input, {"companyId": cid, "status": "INACTIVE",
                                      "deactivationReason": reason})


def _check_deactivation_reason(reason: object) -> None:
    if reason not in store.DEACTIVATION_REASONS:
        raise errors.validation(errors=[{"field": "reason", "reason": "MANUAL or TRANSFERRED"}],
                      retryable=False)


def deactivate_company_by_staff(companyId: str, body: dict, sub: str | None = None) -> dict:
    """7.13: manual deactivation by OSP staff, always with a justification."""
    with store.lock(companyId):
        row = get_company(companyId)
        if row["status"] == "INACTIVE":
            return company_view(companyId, detail=True)
        if row["status"] != "ACTIVE":
            raise errors.invalid_state(detail=row["status"])
        invalid = validation.validate_reason(body.get("reason"))
        if invalid:
            raise errors.validation(errors=invalid)
        store.update_company(companyId, status="INACTIVE", deactivation_reason="MANUAL",
                             deactivated_at=_now())
        store.audit(companyId, sub, "deactivateCompany", None, {"reason": body.get("reason")})
        events.publish(MODULE, "CompanyDeactivated", {"companyId": companyId, "reason": "MANUAL"})
    return company_view(companyId, detail=True)


def reactivate_company(input: dict) -> dict:
    """8.6: back to ACTIVE from an approved application of the matching kind."""
    cid, application_id = input.get("companyId"), input.get("applicationId")
    with store.lock(cid):
        row = get_company(cid)
        if row["status"] == "ACTIVE":
            return standin.step_reply(input, {"companyId": cid, "status": row["status"],
                                              "bpn": row["bpn"], "companyRoles": _active_roles(cid),
                                              "changedFields": []})
        if row["status"] != "INACTIVE":
            raise errors.invalid_state(detail=row["status"], retryable=False)

        application = _reactivation_application(cid, application_id, row)
        data = application.get("companyData") or {}
        verification = application.get("verification")
        fields = _reactivated_fields(row, data, verification)
        stored = {entry["type"]: entry for entry in store.list_identifiers(cid)}
        _check_same_company(row, fields, data, verification, stored)
        identifiers = _reactivated_identifiers(stored, data, verification)

        invalid = validation.validate_company(fields)
        invalid += validation.validate_identifiers(identifiers, fields["country_code"])
        if invalid:
            raise errors.validation(errors=invalid, retryable=False)

        updates = _reactivation_updates(fields, verification, application.get("attestation") or {})
        changed = _changed_fields(row, fields, identifiers)
        store.update_company(cid, **updates)
        store.set_identifiers(cid, identifiers)
        store.audit(cid, None, "stepReactivateCompany", None,
                    {"applicationId": application_id, "changedFields": changed,
                     "processId": input.get("processId"), "stepRunId": input.get("stepRunId")})
        if changed:
            events.publish(MODULE, "CompanyDataChanged",
                           {"companyId": cid, "changedFields": changed, "coreDataChanged": True,
                            "coreDataSource": updates["core_data_source"]})
        roles = sorted(role for role, status in store.list_roles(cid).items() if status == "ACTIVE")
        events.publish(MODULE, "CompanyReactivated",
                       {"companyId": cid, "bpn": row["bpn"], "companyRoles": roles})
    return standin.step_reply(input, {"companyId": cid, "status": "ACTIVE", "bpn": row["bpn"],
                                      "companyRoles": roles, "changedFields": changed})


def _reactivation_application(cid: str | None, application_id: str | None, row: dict) -> dict:
    """The approved application of 8.6, of the kind that matches the deactivation reason."""
    application = gateways.application(application_id)
    if application.get("companyId") != cid:
        raise errors.conflict(detail="application has another companyId", retryable=False)
    expected = "TRANSFER" if row["deactivation_reason"] == "TRANSFERRED" else "REACTIVATION"
    if application.get("kind") != expected:
        raise errors.invalid_state(detail=f"kind {application.get('kind')} does not match the reason",
                                   retryable=False)
    # C12 calls this step after ApplicationApproved and before complete-application (flows
    # `reactivation` and `return`), so C1-M2 still has the application SUBMITTED; a repetition
    # after the flow may find it COMPLETED. C1-M2's ApplicationStatus has no APPROVED: the
    # approval is C1-M3's (C1-M2 openapi ApplicationStatus; OPEN-QUESTIONS 12).
    if application.get("status") not in ("SUBMITTED", "COMPLETED"):
        raise errors.invalid_state(detail=f"application {application.get('status')}", retryable=False)
    return application


def _reactivated_fields(row: dict, data: dict, verification: object) -> dict:
    """The core data of the application, in the columns of README 5."""
    source_address = data.get("address") or {}
    fields = {"name": data.get("legalName"), "short_name": data.get("shortName"),
              "street": source_address.get("streetName"),
              "house_number": source_address.get("streetNumber"),
              "postal_code": source_address.get("postalCode"), "city": source_address.get("city"),
              "region": source_address.get("region"),
              "country_code": source_address.get("countryCode")}
    if verification == "EBW" and validation.same_value(row["name"], data.get("legalName")):
        fields["name"] = row["name"]   # 6.3: an equal value keeps its stored spelling
    return fields


def _check_same_company(row: dict, fields: dict, data: dict, verification: object, stored: dict) -> None:
    """409 `company-mismatch` when the country, or with EBW the EBWOID, is not the company's."""
    mismatched = []
    if fields["country_code"] != row["country_code"]:
        mismatched.append("countryCode")
    if verification == "EBW":
        claimed_ebwoid = next((entry["value"] for entry in data.get("identifiers") or []
                               if entry.get("type") == "EBWOID"), None)
        if validation.value_normalized(claimed_ebwoid or "") != \
                (stored.get("EBWOID") or {}).get("value_normalized"):
            mismatched.append("EBWOID")
    if mismatched:
        raise errors.company_mismatch(fields=mismatched, retryable=False)


def _reactivated_identifiers(stored: dict, data: dict, verification: object) -> list[dict]:
    """The stored identifiers with those of the application; with EBW only the core identifiers change."""
    identifiers = list(stored.values())
    for entry in data.get("identifiers") or []:
        if entry.get("type") == "EBWOID":
            continue
        if verification == "EBW" and entry.get("type") not in CORE_IDENTIFIERS:
            continue
        wallet = (stored.get(entry["type"]) or {}).get("source") == "BUSINESS_WALLET"
        source = "BUSINESS_WALLET" if wallet else "DECLARED"
        identifiers = [item for item in identifiers if item["type"] != entry["type"]]
        identifiers.append({"type": entry["type"], "value": entry["value"], "source": source})
    return [{"type": entry["type"], "value": entry["value"], "source": entry["source"]}
            for entry in identifiers]


def _reactivation_updates(fields: dict, verification: object, attestation_claims: dict) -> dict:
    """The columns to write: the core data, ACTIVE, and the source of the core data (6.3)."""
    updates = dict(fields)
    updates |= {"status": "ACTIVE", "deactivation_reason": None, "reactivated_at": _now()}
    if verification == "EBW":
        updates |= {"core_data_source": "EBW",
                    "core_data_verified_at": attestation_claims.get("verifiedAt"),
                    "verification_ref": attestation_claims.get("attestationId")}
    else:
        updates |= {"core_data_source": "MANUAL", "core_data_verified_at": _now()}
    return updates
