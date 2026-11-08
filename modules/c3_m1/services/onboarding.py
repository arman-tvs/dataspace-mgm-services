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
"""Steps of onboarding (README 8.1 - 8.4): create, assign identifier, activate, reject."""
from __future__ import annotations

from modules.c3_m1 import config, errors, gateways, store, validation
from modules.c3_m1.errors import MODULE
from portal_common import events, standin

from .common import _active_roles, _audit, _now, get_company


# ----------------------------------------------------------------------------------- steps (8.1)
def create_company(input: dict) -> dict:
    """8.1: create the company `REQUESTED` from a submitted application of kind ONBOARDING/TRANSFER."""
    cid, application_id = input.get("companyId"), input.get("applicationId")
    existing = store.get_company(cid)
    if existing is not None:
        if existing["application_id"] == application_id:
            return standin.step_reply(input, {"companyId": cid, "status": existing["status"],
                                              "bpn": existing["bpn"],
                                              "coreDataSource": existing["core_data_source"]})
        raise errors.conflict(detail="company belongs to another application",
                      retryable=False)

    application = _onboarding_application(cid, application_id)
    data = application.get("companyData") or {}
    source_address = data.get("address") or {}
    verification = application.get("verification")
    row = {"name": data.get("legalName"), "short_name": data.get("shortName"),
           "street": source_address.get("streetName"), "house_number": source_address.get("streetNumber"),
           "postal_code": source_address.get("postalCode"), "city": source_address.get("city"),
           "region": source_address.get("region"), "country_code": source_address.get("countryCode")}
    identifiers = [{"type": entry["type"], "value": entry["value"],
                    "source": "BUSINESS_WALLET" if entry.get("source") == "ATTESTATION" else "DECLARED"}
                   for entry in data.get("identifiers") or []]
    roles = [role for role in application.get("companyRoles") or []
             if config.assignable_by(role) == "COMPANY"]
    _check_new_company(row, identifiers, application.get("companyRoles") or [], verification)

    attestation = application.get("attestation") or {}
    with store.lock(cid):
        store.create_company(row | {
            "id": cid, "status": "REQUESTED",
            "core_data_source": "EBW" if verification == "EBW" else "MANUAL",
            "core_data_verified_at": attestation.get("verifiedAt") if verification == "EBW" else None,
            "verification_ref": attestation.get("attestationId") if verification == "EBW" else None,
            "application_id": application_id,
        })
        store.set_identifiers(cid, identifiers)
        for role in roles:
            store.add_role(cid, role, status="REQUESTED", source_kind="APPLICATION",
                           source_ref=application_id)
        _audit(cid, "stepCreateCompany", input, {"applicationId": application_id})
        created = get_company(cid)
        events.publish(MODULE, "CompanyCreated", {"companyId": cid, "applicationId": application_id,
                                                  "coreDataSource": created["core_data_source"]})
    return standin.step_reply(input, {"companyId": cid, "status": created["status"],
                                      "bpn": created["bpn"],
                                      "coreDataSource": created["core_data_source"]})


def _onboarding_application(cid: str | None, application_id: str | None) -> dict:
    """The submitted or approved application of 8.1, of kind ONBOARDING or TRANSFER, for this company."""
    application = gateways.application(application_id)
    if application.get("companyId") != cid:
        raise errors.conflict(detail="application has another companyId", retryable=False)
    if application.get("kind") == "REACTIVATION":
        raise errors.conflict(detail="reactivation uses reactivate-company", retryable=False)
    if application.get("status") not in ("SUBMITTED", "APPROVED"):
        raise errors.invalid_state(detail=f"application {application.get('status')}", retryable=False)
    return application


def _check_new_company(row: dict, identifiers: list[dict], roles: list[str], verification: object) -> None:
    """400 `validation` for invalid core data, identifiers or roles; an EBW verification needs an EBWOID."""
    invalid = validation.validate_company(row)
    invalid += validation.validate_identifiers(identifiers, row["country_code"])
    for role in roles:
        invalid += validation.validate_company_role(role, config.role_catalogue())
    if verification == "EBW" and not any(entry["type"] == "EBWOID" for entry in identifiers):
        invalid.append({"field": "identifiers", "message": "EBWOID required with a verification"})
    if invalid:
        raise errors.validation(errors=invalid, retryable=False)


# ----------------------------------------------------------------------------------- steps (8.2)
def assign_identifier(input: dict) -> dict:
    """8.2: take over the BPN from `CompanyRegisteredAtCsp`."""
    cid, raw = input.get("companyId"), input.get("bpn") or ""
    with store.lock(cid):
        row = get_company(cid)
        invalid = validation.validate_bpn(raw)
        if invalid:
            raise errors.validation(errors=invalid, retryable=False)
        bpn = raw.strip().upper()
        if row["bpn"]:
            if row["bpn"] == bpn:
                return standin.step_reply(input, {"companyId": cid, "status": row["status"], "bpn": bpn})
            raise errors.bpn_mismatch(detail=f"company has {row['bpn']}",
                          retryable=False)
        if row["status"] != "REQUESTED":
            raise errors.invalid_state(detail=row["status"], retryable=False)
        taken = next((other for other in store.find_companies(bpn=bpn, size=5)[0]
                      if other["id"] != cid and other["status"] != "REJECTED"), None)
        if taken is not None:
            raise errors.bpn_taken(detail=taken["id"], retryable=False)
        store.update_company(cid, bpn=bpn, bpn_assigned_at=_now())
        _audit(cid, "stepAssignIdentifier", input, {"bpn": bpn})
        events.publish(MODULE, "CompanyIdentifierAssigned", {"companyId": cid, "bpn": bpn})
    return standin.step_reply(input, {"companyId": cid, "status": row["status"], "bpn": bpn})


# ----------------------------------------------------------------------------------- steps (8.3)
def _terms_of_roles() -> dict[str, set[str]]:
    """agreementKey -> roles it belongs to, from the terms of C1-M2 (11.1).

    Without an address for C1-M2 the built-in stand-in answers with the initial values of 14.3.
    """
    terms: dict[str, set[str]] = {}
    for agreement in gateways.agreements():
        if agreement.get("scope") != "COMPANY_ROLE":
            continue
        for role in agreement.get("companyRoles") or []:
            terms.setdefault(agreement["agreementKey"], set()).add(role)
    return terms


def activate_company(input: dict) -> dict:
    """8.3: activate, taking over the consents of the application."""
    cid, application_id = input.get("companyId"), input.get("applicationId")
    with store.lock(cid):
        row = get_company(cid)
        if row["status"] == "ACTIVE":
            return standin.step_reply(input, {"companyId": cid, "status": row["status"],
                                              "bpn": row["bpn"],
                                              "companyRoles": _active_roles(cid),
                                              "pendingCompanyRoles": []})
        if row["status"] in ("REJECTED", "INACTIVE"):
            raise errors.invalid_state(detail=row["status"], retryable=False)
        if not row["bpn"]:
            raise errors.identifier_missing(retryable=False)
        if application_id != row["application_id"]:
            raise errors.conflict(detail="application does not match",
                          retryable=False)

        application = gateways.application(application_id)
        terms = _terms_of_roles()
        given = {consent.get("agreementKey"): consent for consent in application.get("consents") or []}
        active, pending = _roles_with_consent(cid, terms, given)
        if not active:
            raise errors.roles_without_consent(missing=sorted(pending), retryable=False)
        _take_over_roles(cid, application_id, application, active, terms, given)
        fields = {"status": "ACTIVE", "activated_at": _now()}
        if row["core_data_source"] == "MANUAL" and not row["core_data_verified_at"]:
            fields["core_data_verified_at"] = _now()
        store.update_company(cid, **fields)
        _audit(cid, "stepActivateCompany", input, {"applicationId": application_id,
                                                   "companyRoles": sorted(active)})
        events.publish(MODULE, "CompanyActivated", {"companyId": cid, "bpn": row["bpn"],
                                                    "companyRoles": sorted(active)})
    return standin.step_reply(input, {"companyId": cid, "status": "ACTIVE", "bpn": row["bpn"],
                                      "companyRoles": sorted(active), "pendingCompanyRoles": pending})


def _roles_with_consent(cid: str | None, terms: dict[str, set[str]], given: dict) -> tuple[list[str], list[str]]:
    """The REQUESTED roles whose terms all have a consent in the application, and the others."""
    active, pending = [], []
    for role, status in store.list_roles(cid).items():
        if status != "REQUESTED":
            continue
        needed = {key for key, roles in terms.items() if role in roles}
        if needed <= set(given):
            active.append(role)
        else:
            pending.append(role)
    return active, pending


def _take_over_roles(cid: str | None, application_id: str | None, application: dict, active: list[str],
                     terms: dict[str, set[str]], given: dict) -> None:
    """The roles become ACTIVE with the consents of the application (8.3)."""
    applicant = (application.get("applicant") or {}).get("sub")
    for role in active:
        store.add_role(cid, role, status="ACTIVE", source_kind="APPLICATION", source_ref=application_id)
        for key in (key for key, roles in terms.items() if role in roles):
            store.set_consent(cid, key, version=given[key].get("version"), status="ACTIVE",
                              source_kind="APPLICATION", source_ref=application_id,
                              consented_by=applicant, consented_at=given[key].get("givenAt"))


# ----------------------------------------------------------------------------------- steps (8.4)
def reject_company(input: dict) -> dict:
    """8.4: `REJECTED`, final; an assigned BPN becomes free."""
    cid = input.get("companyId")
    with store.lock(cid):
        row = get_company(cid)
        if row["status"] == "REJECTED":
            return standin.step_reply(input, {"companyId": cid, "status": row["status"]})
        if row["status"] in ("ACTIVE", "INACTIVE"):
            raise errors.invalid_state(detail=row["status"], retryable=False)
        store.update_company(cid, status="REJECTED", rejected_at=_now())
        _audit(cid, "stepRejectCompany", input)
        events.publish(MODULE, "CompanyRejected", {"companyId": cid})
    return standin.step_reply(input, {"companyId": cid, "status": "REJECTED"})
