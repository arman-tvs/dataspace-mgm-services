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
"""Applications of people (README 7.2 to 7.5, 7.11) and the lists for people and OSP staff (7.3, 7.12)."""
from __future__ import annotations

import os
import uuid

from modules.c1_m2 import attestation, catalog, errors, gateways, store
from modules.c1_m2.errors import MODULE, FieldError
from modules.c1_m2.services.checks import check_company_fields, check_create, check_reference_data, check_roles
from modules.c1_m2.services.common import OPEN, audit, err, now_iso, own, paged, public, summary
from modules.c1_m2.services.company_data import (
    build_company_data,
    check_existing_identifiers,
    company_for_reference,
    given_identifiers,
    new_company_id,
    role_name,
)
from portal_common import events


def open_of(sub: str) -> dict | None:
    return next((a for a in store.applications.values() if a["applicant"]["sub"] == sub and a["status"] in OPEN), None)


def create_application(body: dict, claims: dict) -> tuple[dict, bool]:
    """7.2, in the order of the README. Returns the application and whether it is new (201) or a repetition (200)."""
    if claims.get("company_id"):
        raise errors.account_bound()
    check_create(body)
    kind, verification = body["kind"], body["verification"]
    if verification == "DOCUMENTS" and os.environ.get("DOCUMENTS_ENABLED", "true").lower() == "false":
        raise errors.documents_disabled()
    header, payload = attestation.verify(body["attestation"], claims) if verification == "EBW" else (None, None)
    sub = claims["sub"]
    with store.lock:
        existing = open_of(sub)
        if existing:
            if payload and existing.get("_attestation") and existing["_attestation"]["attestationId"] == payload["jti"]:
                return public(existing), False
            raise errors.open_application_exists(existing["id"])
        if payload and payload["jti"] in store.used_jtis:
            raise errors.attestation_used()
    given = body.get("companyData") or {}
    company = company_for_reference(body, kind) if (body.get("companyId") or body.get("bpn")) else None
    company_claim = (payload or {}).get("company")
    company_roles = body.get("companyRoles")
    if company:
        euid = (company_claim or {}).get("euid") or given_identifiers(given).get("EUID")
        check_existing_identifiers(company, (company_claim or {}).get("ebwoid"), euid)
        if not company_roles:
            company_roles = [r for r in company.get("companyRoles") or [] if catalog.selectable(role_name(r))]
            company_roles = [role_name(r) for r in company_roles]
            if not company_roles:
                raise errors.validation([err("companyRoles", "the company has no selectable roles: give the roles")])
    data, comparison = build_company_data(verification, company_claim, given)
    check_reference_data(data, company_roles, verification)
    with store.lock:
        existing = open_of(sub)   # concurrent creation: the same answer as above
        if existing:
            raise errors.open_application_exists(existing["id"])
        if payload and payload["jti"] in store.used_jtis:
            raise errors.attestation_used()
        if company and any(a["companyId"] == company["id"] and a["status"] in OPEN for a in store.applications.values()):
            raise errors.company_has_open_application()
        now = now_iso()
        a = {"id": str(uuid.uuid4()),
             "companyId": company["id"] if company else new_company_id((company_claim or {}).get("ebwoid")),
             "kind": kind, "existingCompany": bool(company), "verification": verification,
             "applicant": {"sub": sub, "givenName": claims.get("given_name"), "familyName": claims.get("family_name")},
             "status": "CREATED", "companyData": data, "companyRoles": list(company_roles), "comparison": comparison,
             "documents": [], "representationDeclared": None, "consents": [], "declineReason": None, "createdAt": now,
             "changedAt": now, "submittedAt": None, "withdrawnAt": None, "closedAt": None, "completedAt": None,
             "_seq": next(store.seq), "_given": given, "_files": {}, "_requiredAgreements": [], "_consentRecords": [],
             "_companyRef": bool(company)}
        if payload:
            a |= {"_attestation": attestation.summary(header, payload), "_raw": body["attestation"],
                  "_attestationClaims": {"iat": payload["iat"], "exp": payload["exp"], "company": company_claim}}
            store.used_jtis.add(payload["jti"])
        store.applications[a["id"]] = a
        audit(a, "createApplication", sub=sub)
        events.publish(MODULE, "ApplicationCreated", {"applicationId": a["id"], "companyId": a["companyId"], "kind": kind,
                                                      "existingCompany": a["existingCompany"]})
        return public(a), True


def list_own(sub: str, status: list[str] | None, page: int, size: int) -> dict:
    found = sorted((a for a in store.applications.values() if a["applicant"]["sub"] == sub and (not status or a["status"] in status)),
                   key=lambda a: a["_seq"], reverse=True)
    return paged([summary(a) for a in found], page, size)


def list_all(status: list[str] | None, kind: list[str] | None, verification: list[str] | None, company_id: str | None,
             page: int, size: int) -> dict:
    found = sorted((a for a in store.applications.values() if (not status or a["status"] in status) and (not kind or a["kind"] in kind)
                    and (not verification or a["verification"] in verification)
                    and (not company_id or a["companyId"] == company_id)), key=lambda a: a["_seq"], reverse=True)
    return paged([summary(a) for a in found], page, size)


def update_application(application_id: str, sub: str, body: dict) -> dict:
    """7.5."""
    a = own(sub, application_id)
    if a["status"] != "CREATED":
        raise errors.invalid_state(f"application is {a['status']}")
    allowed = ("legalName", "shortName", "address", "identifiers", "companyRoles")
    change = {k: body[k] for k in allowed if k in body}
    if not change:
        raise errors.validation([err("body", f"at least one of {', '.join(allowed)}")])
    invalid: list[FieldError] = [err(k, "must not be null") for k in ("legalName", "address", "identifiers")
                          if k in change and change[k] is None]
    check_company_fields(change, invalid)
    if "companyRoles" in change:
        check_roles(change["companyRoles"], invalid)
    if a["verification"] == "DOCUMENTS" and change.get("identifiers") == []:
        invalid.append(err("identifiers", "at least one identifier for DOCUMENTS"))
    if invalid:
        raise errors.validation(invalid)
    company_claim = (a.get("_attestationClaims") or {}).get("company")
    given = {**a["_given"], **{k: v for k, v in change.items() if k != "companyRoles"}}
    if "identifiers" in change and a["_companyRef"]:
        company = gateways.company_by_id(a["companyId"]) or {}
        euid = (company_claim or {}).get("euid") or given_identifiers(given).get("EUID")
        check_existing_identifiers(company, (company_claim or {}).get("ebwoid"), euid)
    data, comparison = build_company_data(a["verification"], company_claim, given)
    roles = change.get("companyRoles", a["companyRoles"])
    check_reference_data(data, roles, a["verification"])
    with store.lock:
        if a["status"] != "CREATED":
            raise errors.invalid_state(f"application is {a['status']}")
        a.update(companyData=data, comparison=comparison, companyRoles=list(roles), changedAt=now_iso(), _given=given)
        audit(a, "updateApplication", sub=sub)
        return public(a)


def withdraw_application(application_id: str, sub: str) -> dict:
    """7.11."""
    a = own(sub, application_id)
    if a["status"] == "WITHDRAWN":
        return public(a)
    if a["status"] not in OPEN:
        raise errors.invalid_state(f"application is {a['status']}")
    if a["status"] == "SUBMITTED":
        review = gateways.review_status(a["id"])   # not reachable: 502, nothing changed
        if review in ("APPROVED", "DECLINED"):
            raise errors.already_decided(review)
    with store.lock:
        if a["status"] == "WITHDRAWN":
            return public(a)
        if a["status"] not in OPEN:
            raise errors.invalid_state(f"application is {a['status']}")
        submitted = a["status"] == "SUBMITTED"
        now = now_iso()
        a.update(status="WITHDRAWN", withdrawnAt=now, changedAt=now)
        audit(a, "withdrawApplication", sub=sub)
        if submitted:
            events.publish(MODULE, "ApplicationWithdrawn", {"applicationId": a["id"], "companyId": a["companyId"], "kind": a["kind"],
                                                            "existingCompany": a["existingCompany"]})
        return public(a)
