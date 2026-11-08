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
"""A new verification attestation (README 7.6) and the submission of an application (7.10)."""
from __future__ import annotations

from modules.c1_m2 import attestation, catalog, errors, gateways, store
from modules.c1_m2.errors import MODULE
from modules.c1_m2.services.checks import check_reference_data
from modules.c1_m2.services.common import ATTESTATION_MAX_CHARS, audit, err, now_iso, own, public
from modules.c1_m2.services.company_data import check_existing_identifiers, company_data_ebw, given_identifiers
from portal_common import events


def replace_attestation(application_id: str, claims: dict, token: object) -> dict:
    """7.6."""
    sub = claims["sub"]
    a = own(sub, application_id)
    if a["status"] != "CREATED" or a["verification"] == "DOCUMENTS":
        raise errors.invalid_state("only in status CREATED and the verification path EBW")
    if not (isinstance(token, str) and 0 < len(token) <= ATTESTATION_MAX_CHARS):
        raise errors.validation([err("attestation", "required, at most 16 KB")])
    header, payload = attestation.verify(token, claims)
    if a["_attestation"]["attestationId"] == payload["jti"]:
        return public(a)
    new, old = payload["company"], a["_attestationClaims"]["company"]
    fields = []
    if new["ebwoid"] != old["ebwoid"]:
        fields.append("EBWOID")
    if new["country"] != old["country"]:
        fields.append("COUNTRY")
    applicant_euid = given_identifiers(a["_given"]).get("EUID")
    euid = catalog.normalise_identifier("EUID", new["euid"]) if new.get("euid") else None
    if euid and ((old.get("euid") and catalog.normalise_identifier("EUID", old["euid"]) != euid)
                 or (applicant_euid and applicant_euid != euid)):
        fields.append("EUID")
    if fields:
        raise errors.attestation_mismatch(fields)
    data, comparison = company_data_ebw(new, a["_given"])
    check_reference_data(data, a["companyRoles"], a["verification"])
    if a["_companyRef"]:
        check_existing_identifiers(gateways.company_by_id(a["companyId"]) or {}, new["ebwoid"], euid or applicant_euid)
    with store.lock:
        if payload["jti"] in store.used_jtis:
            raise errors.attestation_used()
        if a["status"] != "CREATED":
            raise errors.invalid_state(f"application is {a['status']}")
        store.used_jtis.add(payload["jti"])
        a.update(companyData=data, comparison=comparison, changedAt=now_iso(), _attestation=attestation.summary(header, payload),
                 _raw=token, _attestationClaims={"iat": payload["iat"], "exp": payload["exp"], "company": new})
        audit(a, "replaceAttestation", sub=sub)
        return public(a)


def submit_application(application_id: str, sub: str, body: dict) -> dict:
    """7.10."""
    with store.lock:
        a = own(sub, application_id)
        if a["status"] == "SUBMITTED":
            return public(a)
        if a["status"] != "CREATED":
            raise errors.invalid_state(f"application is {a['status']}")
        consents = body.get("consents")
        valid = isinstance(consents, list) and consents and all(
            isinstance(c, dict) and isinstance(c.get("agreementKey"), str) and isinstance(c.get("version"), str)
            and c.get("language") in ("de", "en") for c in consents)
        if not valid:
            raise errors.validation([err("consents", "at least one consent with agreementKey, version and language de or en")])
        if a["verification"] == "EBW" and not attestation.usable_at_submission(a):
            raise errors.attestation_expired()
        if a["verification"] == "DOCUMENTS":
            types = {d["documentType"] for d in a["documents"]}
            missing_types = [] if "COMMERCIAL_REGISTER_EXTRACT" in types else ["COMMERCIAL_REGISTER_EXTRACT"]
            undeclared = body.get("representationDeclared") is not True
            if missing_types or undeclared:
                raise errors.documents_incomplete(missing_types, undeclared)
        required = [{"agreementKey": x["agreementKey"], "version": x["version"]} for x in catalog.required(a["companyRoles"])]
        given = {(c["agreementKey"], c["version"]) for c in consents}
        missing = [r for r in required if (r["agreementKey"], r["version"]) not in given]
        if missing:
            raise errors.consents_incomplete(missing)
        needed = {(r["agreementKey"], r["version"]) for r in required}
        extra = [c["agreementKey"] for c in consents if (c["agreementKey"], c["version"]) not in needed]
        if extra:
            raise errors.validation([err("consents", f"unknown or not required terms: {k}") for k in extra])
        now = now_iso()
        a.update(consents=[{"agreementKey": c["agreementKey"], "version": c["version"], "language": c["language"], "givenAt": now}
                           for c in consents],
                 status="SUBMITTED", submittedAt=now, changedAt=now, _requiredAgreements=required,
                 _consentRecords=[{"agreementKey": c["agreementKey"], "version": c["version"], "language": c["language"],
                                   "givenAt": now, "givenBySub": sub,
                                   "attestationId": (a.get("_attestation") or {}).get("attestationId")} for c in consents])
        if a["verification"] == "DOCUMENTS":
            a["representationDeclared"] = True
        audit(a, "submitApplication", sub=sub)
        events.publish(MODULE, "ApplicationSubmitted", {"applicationId": a["id"], "companyId": a["companyId"], "kind": a["kind"],
                                                        "existingCompany": a["existingCompany"], "applicantSub": sub})
        return public(a)
