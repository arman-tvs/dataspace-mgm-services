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
#  Assisted-By: Claude Code (claude-opus-5-5)
#################################################################################
"""Public interface of C1-M2 Registration: the steps `complete-application` and `close-application`, the
queries 9.1 to 9.3, and the operations of people and OSP staff that `router.py` calls.

Applications, consents, supporting documents and the audit log are kept in memory (README 5); one lock
stands for the row locks and partial unique indexes of 6.11. Calls to neighbours and to the JWKS run outside it.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import os
import re
import threading
import unicodedata
import uuid

from portal_common import events
from portal_common.problems import Problem
from tools import testdata

from . import attestation, calls, catalog

MODULE = "c1-m2"
KINDS = ("ONBOARDING", "REACTIVATION", "TRANSFER")
VERIFICATIONS = ("EBW", "DOCUMENTS")
OPEN = ("CREATED", "SUBMITTED")
DOCUMENT_TYPES = ("COMMERCIAL_REGISTER_EXTRACT", "POWER_OF_ATTORNEY", "OTHER")
IDENTIFIER_TYPES = ("EUID", "EBWOID", "COMMERCIAL_REG_NUMBER", "VAT_ID", "LEI_CODE", "EORI")
SIGNATURES = ((b"%PDF-", "application/pdf"), (b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"))
ATTESTATION_MAX_CHARS = 16384
SUMMARY_KEYS = ("attestationId", "issuer", "issuedAt", "expiresAt", "verifiedAt", "person", "representation")

applications: dict[str, dict] = {}
used_jtis: set[str] = set()
audit_log: list[dict] = []
_lock = threading.RLock()
_seq = itertools.count()


def reset() -> None:
    with _lock:
        applications.clear()
        used_jtis.clear()
        audit_log.clear()
        catalog.reset()
        attestation.reset()


def _now() -> str:
    return dt.datetime.fromtimestamp(attestation.now(), dt.UTC).isoformat()


def _audit(a: dict, operation: str, sub: str | None = None, step: dict | None = None, object_id: str | None = None) -> None:
    audit_log.append({"at": _now(), "sub": sub, "processId": (step or {}).get("processId"),
                      "stepRunId": (step or {}).get("stepRunId"), "companyId": a["companyId"], "operation": operation,
                      "applicationId": a["id"], "objectId": object_id})


def _validation(errors: list[dict], **ext) -> Problem:
    return Problem(MODULE, 400, "validation", errors=errors, **ext)


def _err(field: str, message: str) -> dict:
    return {"field": field, "message": message}


# ------------------------------------------------------------------------------------- views
def public(a: dict) -> dict:
    """`Application`: without the JWT and with the extract of the attestation only."""
    out = {k: v for k, v in a.items() if not k.startswith("_")}
    current = a.get("_attestation")
    out["attestation"] = {k: current[k] for k in SUMMARY_KEYS} if current else None
    return out


def summary(a: dict) -> dict:
    """`ApplicationSummary`."""
    return {"id": a["id"], "companyId": a["companyId"], "kind": a["kind"], "existingCompany": a["existingCompany"],
            "verification": a["verification"], "status": a["status"], "legalName": a["companyData"]["legalName"],
            "countryCode": a["companyData"]["address"].get("countryCode"), "companyRoles": a["companyRoles"],
            "createdAt": a["createdAt"], "submittedAt": a.get("submittedAt")}


def _review_status(a: dict) -> str:
    """`reviewStatus` of 7.4."""
    if a["status"] == "CREATED":
        return "NONE"
    try:
        return calls.review_status(a["id"]) or "NONE"
    except Problem:
        return "UNKNOWN"


def with_review(a: dict) -> dict:
    return public(a) | {"reviewStatus": _review_status(a)}


def _page(items: list[dict], page: int, size: int) -> dict:
    return {"items": items[page * size:(page + 1) * size], "page": page, "size": size, "total": len(items)}


# ----------------------------------------------------------------------------- reference data
def list_countries(lang: str) -> list[dict]:
    return sorted(({"code": c["code"], "name": c["name"].get(lang) or c["name"]["en"]} for c in catalog.master()["countries"]),
                  key=lambda c: c["code"])


def list_identifier_types(country_code: str, lang: str) -> list[dict]:
    country = catalog.country(country_code)
    if country is None:
        raise Problem(MODULE, 404, "not-found")
    out = []
    for t in catalog.master()["identifierTypes"]:
        if t["type"] in country.get("identifierTypes", []):
            out.append({"type": t["type"], "name": t["name"].get(lang) or t["name"]["en"],
                        "pattern": catalog.identifier_pattern(t["type"], country_code)})
    return out


def list_company_roles(lang: str) -> list[dict]:
    active = catalog.active()
    return [{"role": r["role"], "name": r["name"].get(lang) or r["name"]["en"],
             "description": r["description"].get(lang) or r["description"]["en"],
             "agreementKeys": [a["agreementKey"] for a in active if r["role"] in a["companyRoles"]]}
            for r in catalog.all_roles() if r.get("selectable")]


def list_agreements(company_roles: list[str], lang: str) -> list[dict]:
    bad = [r for r in company_roles if not catalog.selectable(r)]
    if bad:
        raise _validation([_err("companyRole", f"unknown or not selectable role: {r}") for r in bad])
    return [{"agreementKey": a["agreementKey"], "version": a["version"], "party": a["party"], "scope": a["scope"],
             "title": a["title"].get(lang) or a["title"]["en"], "documentUrls": a["documentUrls"],
             "companyRoles": a["companyRoles"]} for a in catalog.required(company_roles)]


# ------------------------------------------------------------------------------ input checks
def _check_address(address: object, field: str, errors: list[dict], required: bool = True) -> None:
    if not isinstance(address, dict):
        errors.append(_err(field, "must be an object"))
        return
    limits = (("streetName", 150, True), ("streetNumber", 20, False), ("postalCode", 12, False), ("city", 150, True))
    for name, maximum, needed in limits:
        value = address.get(name)
        if value in (None, ""):
            if needed and required:
                errors.append(_err(f"{field}.{name}", "required"))
        elif not isinstance(value, str) or len(value) > maximum:
            errors.append(_err(f"{field}.{name}", f"text of at most {maximum} characters"))
    region = address.get("region")
    if region not in (None, "") and not (isinstance(region, str) and re.fullmatch(r"[A-Z0-9]{1,3}", region)):
        errors.append(_err(f"{field}.region", "code of the region, 1 to 3 characters"))
    if not (isinstance(address.get("countryCode"), str) and re.fullmatch(r"[A-Z]{2}", address["countryCode"])):
        errors.append(_err(f"{field}.countryCode", "ISO 3166-1 alpha-2"))


def _check_identifiers(identifiers: object, errors: list[dict]) -> None:
    if not isinstance(identifiers, list) or len(identifiers) > 10:
        errors.append(_err("identifiers", "list of at most 10 identifiers"))
        return
    seen = set()
    for i, x in enumerate(identifiers):
        if not isinstance(x, dict) or x.get("type") not in IDENTIFIER_TYPES \
                or not isinstance(x.get("value"), str) or not 1 <= len(x["value"]) <= 200:
            errors.append(_err(f"identifiers[{i}]", "needs a known type and a value of 1 to 200 characters"))
        elif x["type"] in seen:
            errors.append(_err(f"identifiers[{i}]", f"at most one identifier per type: {x['type']}"))
        else:
            seen.add(x["type"])


def _check_company_fields(data: dict, errors: list[dict]) -> None:
    name = data.get("legalName")
    if name is not None and not (isinstance(name, str) and 1 <= len(name) <= 160 and re.fullmatch(r"\S(.*\S)?", name)):
        errors.append(_err("legalName", "1 to 160 characters, without whitespace at the start and end"))
    short = data.get("shortName")
    if short is not None and not (isinstance(short, str) and len(short) <= 60):
        errors.append(_err("shortName", "at most 60 characters"))
    if data.get("address") is not None:
        _check_address(data["address"], "address", errors)
    if data.get("identifiers") is not None:
        _check_identifiers(data["identifiers"], errors)


def _check_roles(company_roles: object, errors: list[dict]) -> None:
    if not isinstance(company_roles, list) or not company_roles:
        errors.append(_err("companyRoles", "at least one company role"))
    elif len(set(map(str, company_roles))) != len(company_roles):
        errors.append(_err("companyRoles", "without duplicates"))


def _is_uuid(value: object) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def _check_create(body: dict) -> None:
    """7.2 step 2 with the rules of 6.2."""
    errors: list[dict] = []
    kind, verification = body.get("kind"), body.get("verification")
    if kind not in KINDS:
        errors.append(_err("kind", f"one of {', '.join(KINDS)}"))
    if verification not in VERIFICATIONS:
        errors.append(_err("verification", f"one of {', '.join(VERIFICATIONS)}"))
    token = body.get("attestation")
    if verification == "EBW" and not (isinstance(token, str) and 0 < len(token) <= ATTESTATION_MAX_CHARS):
        errors.append(_err("attestation", "required for EBW, at most 16 KB"))
    if verification == "DOCUMENTS" and token is not None:
        errors.append(_err("attestation", "not allowed for DOCUMENTS"))
    reference = body.get("companyId") or body.get("bpn")
    if body.get("companyId") and body.get("bpn"):
        errors.append(_err("companyId", "companyId and bpn must not both be given"))
    if body.get("companyId") and not _is_uuid(body["companyId"]):
        errors.append(_err("companyId", "must be a UUID"))
    if body.get("bpn") and not (isinstance(body["bpn"], str) and re.fullmatch(r"BPNL[A-Z0-9]{12}", body["bpn"])):
        errors.append(_err("bpn", "must be a BPN"))
    if kind == "ONBOARDING" and reference:
        errors.append(_err("companyId", "no reference for ONBOARDING"))
    if kind == "REACTIVATION" and not reference:
        errors.append(_err("companyId", "reference required for REACTIVATION"))
    if body.get("companyRoles") is not None or not reference:
        _check_roles(body.get("companyRoles"), errors)
    data = body.get("companyData")
    if data is not None and not isinstance(data, dict):
        errors.append(_err("companyData", "must be an object"))
    elif data:
        _check_company_fields(data, errors)
    if verification == "DOCUMENTS":
        data = data if isinstance(data, dict) else {}
        for name in ("legalName", "address"):
            if not data.get(name):
                errors.append(_err(f"companyData.{name}", "required for DOCUMENTS"))
        if not data.get("identifiers"):
            errors.append(_err("companyData.identifiers", "at least one identifier for DOCUMENTS"))
    if errors:
        raise _validation(errors)


def _check_reference_data(a_data: dict, company_roles: list[str], verification: str) -> None:
    """7.2 step 9: country, identifier types, formats (6.6), selectable roles (6.7)."""
    errors: list[dict] = []
    code = a_data["address"].get("countryCode")
    if catalog.country(code) is None:
        errors.append(_err("address.countryCode", f"unknown country {code}"))
    else:
        for i, x in enumerate(a_data["identifiers"]):
            if verification == "DOCUMENTS" and x["type"] == "EBWOID":
                errors.append(_err(f"identifiers[{i}]", "EBWOID is not allowed without a Business Wallet"))
            elif message := catalog.identifier_error(x["type"], x["value"], code):
                errors.append(_err(f"identifiers[{i}]", message))
    if len(a_data["identifiers"]) > 10:
        errors.append(_err("identifiers", "at most 10 identifiers"))
    errors += [_err("companyRoles", f"not selectable: {r}") for r in company_roles if not catalog.selectable(r)]
    if errors:
        raise _validation(errors)


# ------------------------------------------------------------------------------ company data
def _same(a: str, b: str) -> bool:
    """Comparison of 6.5: NFKC, whitespace trimmed and collapsed, case ignored."""
    def norm(s: str) -> str:
        return " ".join(unicodedata.normalize("NFKC", s).split()).casefold()
    return norm(a) == norm(b)


def _compare(field: str, mine: str | None, claim: str | None) -> dict | None:
    if not mine and not claim:
        return None
    if mine and claim:
        return {"field": field, "result": "MATCH" if _same(mine, claim) else "MISMATCH"}
    return {"field": field, "result": "NOT_IN_ATTESTATION" if mine else "FROM_ATTESTATION"}


def _given_identifiers(given: dict) -> dict[str, str]:
    return {x["type"]: catalog.normalise_identifier(x["type"], x["value"]) for x in given.get("identifiers") or []}


def _company_data_ebw(company: dict, given: dict) -> tuple[dict, list[dict]]:
    """6.5: the attestation is the basis; fixed fields must be equal, compared fields are recorded."""
    ids = _given_identifiers(given)
    ebwoid, euid = company["ebwoid"], company.get("euid")
    address, claim = given.get("address"), company.get("address") or {}
    fields = []
    if "EBWOID" in ids and ids["EBWOID"] != ebwoid:
        fields.append("EBWOID")
    if euid and "EUID" in ids and ids["EUID"] != catalog.normalise_identifier("EUID", euid):
        fields.append("EUID")
    if address and address.get("countryCode") != company["country"]:
        fields.append("COUNTRY")
    if fields:
        raise Problem(MODULE, 400, "attestation-mismatch", fields=fields)
    if not address and not (claim.get("street_address") and claim.get("locality")):
        raise _validation([_err("companyData.address", "the attestation has no address: streetName and city required")])
    identifiers = [{"type": "EBWOID", "value": ebwoid, "source": "ATTESTATION"}]
    if euid:
        identifiers.append({"type": "EUID", "value": catalog.normalise_identifier("EUID", euid), "source": "ATTESTATION"})
    identifiers += [{"type": t, "value": v, "source": "APPLICANT"} for t, v in ids.items()
                    if t != "EBWOID" and not (t == "EUID" and euid)]
    street = " ".join(p for p in (address.get("streetName"), address.get("streetNumber")) if p) if address else None
    final = ({**address, "postalCode": address.get("postalCode") or claim.get("postal_code")} if address else
             {"streetName": claim.get("street_address"), "streetNumber": None, "postalCode": claim.get("postal_code"),
              "city": claim.get("locality"), "region": None, "countryCode": company["country"]})
    comparison = [{"field": "EBWOID", "result": "FROM_ATTESTATION"},
                  {"field": "EUID", "result": "FROM_ATTESTATION"} if euid else _compare("EUID", ids.get("EUID"), None),
                  {"field": "COUNTRY", "result": "MATCH" if address else "FROM_ATTESTATION"},
                  _compare("LEGAL_NAME", given.get("legalName"), company["legal_name"]) if given.get("legalName")
                  else {"field": "LEGAL_NAME", "result": "FROM_ATTESTATION"},
                  _compare("STREET", street, claim.get("street_address")),
                  _compare("POSTAL_CODE", address.get("postalCode") if address else None, claim.get("postal_code")),
                  _compare("CITY", address.get("city") if address else None, claim.get("locality"))]
    return ({"legalName": given.get("legalName") or company["legal_name"], "shortName": given.get("shortName"),
             "address": final, "identifiers": identifiers}, [c for c in comparison if c])


def _company_data_documents(given: dict) -> tuple[dict, list[dict]]:
    """6.9: all data from the person."""
    return ({"legalName": given["legalName"], "shortName": given.get("shortName"), "address": given["address"],
             "identifiers": [{"type": t, "value": v, "source": "APPLICANT"} for t, v in _given_identifiers(given).items()]}, [])


def _build_company_data(verification: str, company: dict | None, given: dict) -> tuple[dict, list[dict]]:
    return _company_data_ebw(company, given) if verification == "EBW" else _company_data_documents(given)


def _check_existing_identifiers(company: dict, ebwoid: str | None, euid: str | None) -> None:
    """6.2: the company of the application must be the existing one."""
    kept = {i["type"]: i["value"] for i in company.get("identifiers") or []}
    fields = []
    if ebwoid and kept.get("EBWOID") and kept["EBWOID"] != ebwoid:
        fields.append("EBWOID")
    if euid and kept.get("EUID") and catalog.normalise_identifier("EUID", kept["EUID"]) != catalog.normalise_identifier("EUID", euid):
        fields.append("EUID")
    if fields:
        raise Problem(MODULE, 400, "attestation-mismatch", fields=fields)


def _company_for_reference(body: dict, kind: str) -> dict:
    """6.2: read the company at C3-M1 and check that status and reason fit the application kind."""
    company = calls.company_by_id(body["companyId"]) if body.get("companyId") else calls.company_by_bpn(body["bpn"])
    if company is None:
        raise Problem(MODULE, 409, "company-not-eligible", detail="company unknown")
    transferred = company.get("deactivationReason") == "TRANSFERRED"
    eligible = company.get("status") == "INACTIVE" and (transferred if kind == "TRANSFER" else not transferred)
    if not eligible:
        raise Problem(MODULE, 409, "company-not-eligible", companyStatus=company.get("status"))
    return company


def _new_company_id(ebwoid: str | None) -> str:
    """7.2 generates the `companyId`; a test company takes its ID of FRAMEWORK 7a once (OPEN-QUESTIONS 3)."""
    cid = testdata.test_company_id(ebwoid)
    if cid and not any(a["companyId"] == cid for a in applications.values()):
        return cid
    return str(uuid.uuid4())


# --------------------------------------------------------------------------- applications (7.2 to 7.11)
def _open_of(sub: str) -> dict | None:
    return next((a for a in applications.values() if a["applicant"]["sub"] == sub and a["status"] in OPEN), None)


def create_application(body: dict, claims: dict) -> tuple[dict, bool]:
    """7.2, in the order of the README. Returns the application and whether it is new (201) or a repetition (200)."""
    if claims.get("company_id"):
        raise Problem(MODULE, 403, "account-bound")
    _check_create(body)
    kind, verification = body["kind"], body["verification"]
    if verification == "DOCUMENTS" and os.environ.get("DOCUMENTS_ENABLED", "true").lower() == "false":
        raise Problem(MODULE, 400, "documents-disabled")
    header, payload = attestation.verify(body["attestation"], claims) if verification == "EBW" else (None, None)
    sub = claims["sub"]
    with _lock:
        existing = _open_of(sub)
        if existing:
            if payload and existing.get("_attestation") and existing["_attestation"]["attestationId"] == payload["jti"]:
                return public(existing), False
            raise Problem(MODULE, 409, "open-application-exists", existingApplicationId=existing["id"])
        if payload and payload["jti"] in used_jtis:
            raise Problem(MODULE, 409, "attestation-used")
    given = body.get("companyData") or {}
    company = _company_for_reference(body, kind) if (body.get("companyId") or body.get("bpn")) else None
    company_claim = (payload or {}).get("company")
    company_roles = body.get("companyRoles")
    if company:
        euid = (company_claim or {}).get("euid") or _given_identifiers(given).get("EUID")
        _check_existing_identifiers(company, (company_claim or {}).get("ebwoid"), euid)
        if not company_roles:
            company_roles = [r for r in company.get("companyRoles") or [] if catalog.selectable(_role_name(r))]
            company_roles = [_role_name(r) for r in company_roles]
            if not company_roles:
                raise _validation([_err("companyRoles", "the company has no selectable roles: give the roles")])
    data, comparison = _build_company_data(verification, company_claim, given)
    _check_reference_data(data, company_roles, verification)
    with _lock:
        existing = _open_of(sub)   # concurrent creation: the same answer as above
        if existing:
            raise Problem(MODULE, 409, "open-application-exists", existingApplicationId=existing["id"])
        if payload and payload["jti"] in used_jtis:
            raise Problem(MODULE, 409, "attestation-used")
        if company and any(a["companyId"] == company["id"] and a["status"] in OPEN for a in applications.values()):
            raise Problem(MODULE, 409, "company-has-open-application")
        now = _now()
        a = {"id": str(uuid.uuid4()),
             "companyId": company["id"] if company else _new_company_id((company_claim or {}).get("ebwoid")),
             "kind": kind, "existingCompany": bool(company), "verification": verification,
             "applicant": {"sub": sub, "givenName": claims.get("given_name"), "familyName": claims.get("family_name")},
             "status": "CREATED", "companyData": data, "companyRoles": list(company_roles), "comparison": comparison,
             "documents": [], "representationDeclared": None, "consents": [], "declineReason": None, "createdAt": now,
             "changedAt": now, "submittedAt": None, "withdrawnAt": None, "closedAt": None, "completedAt": None,
             "_seq": next(_seq), "_given": given, "_files": {}, "_requiredAgreements": [], "_consentRecords": [],
             "_companyRef": bool(company)}
        if payload:
            a |= {"_attestation": attestation.summary(header, payload), "_raw": body["attestation"],
                  "_attestationClaims": {"iat": payload["iat"], "exp": payload["exp"], "company": company_claim}}
            used_jtis.add(payload["jti"])
        applications[a["id"]] = a
        _audit(a, "createApplication", sub=sub)
        events.publish(MODULE, "ApplicationCreated", {"applicationId": a["id"], "companyId": a["companyId"], "kind": kind,
                                                      "existingCompany": a["existingCompany"]})
        return public(a), True


def _role_name(role: object) -> str:
    """Company roles of C3-M1 come as names or as `{companyRole, status}`."""
    return role.get("companyRole") if isinstance(role, dict) else role


def own(sub: str, application_id: str) -> dict:
    """Scope `own` (6.3): for other people the application does not exist."""
    a = applications.get(application_id)
    if not a or a["applicant"]["sub"] != sub:
        raise Problem(MODULE, 404, "not-found")
    return a


def any_application(application_id: str) -> dict:
    a = applications.get(application_id)
    if not a:
        raise Problem(MODULE, 404, "not-found")
    return a


def list_own(sub: str, status: list[str] | None, page: int, size: int) -> dict:
    found = sorted((a for a in applications.values() if a["applicant"]["sub"] == sub and (not status or a["status"] in status)),
                   key=lambda a: a["_seq"], reverse=True)
    return _page([summary(a) for a in found], page, size)


def list_all(status: list[str] | None, kind: list[str] | None, verification: list[str] | None, company_id: str | None,
             page: int, size: int) -> dict:
    found = sorted((a for a in applications.values() if (not status or a["status"] in status) and (not kind or a["kind"] in kind)
                    and (not verification or a["verification"] in verification)
                    and (not company_id or a["companyId"] == company_id)), key=lambda a: a["_seq"], reverse=True)
    return _page([summary(a) for a in found], page, size)


def update_application(application_id: str, sub: str, body: dict) -> dict:
    """7.5."""
    a = own(sub, application_id)
    if a["status"] != "CREATED":
        raise Problem(MODULE, 409, "invalid-state", detail=f"application is {a['status']}")
    allowed = ("legalName", "shortName", "address", "identifiers", "companyRoles")
    change = {k: body[k] for k in allowed if k in body}
    if not change:
        raise _validation([_err("body", f"at least one of {', '.join(allowed)}")])
    errors: list[dict] = [_err(k, "must not be null") for k in ("legalName", "address", "identifiers")
                          if k in change and change[k] is None]
    _check_company_fields(change, errors)
    if "companyRoles" in change:
        _check_roles(change["companyRoles"], errors)
    if a["verification"] == "DOCUMENTS" and change.get("identifiers") == []:
        errors.append(_err("identifiers", "at least one identifier for DOCUMENTS"))
    if errors:
        raise _validation(errors)
    company_claim = (a.get("_attestationClaims") or {}).get("company")
    given = {**a["_given"], **{k: v for k, v in change.items() if k != "companyRoles"}}
    if "identifiers" in change and a["_companyRef"]:
        company = calls.company_by_id(a["companyId"]) or {}
        euid = (company_claim or {}).get("euid") or _given_identifiers(given).get("EUID")
        _check_existing_identifiers(company, (company_claim or {}).get("ebwoid"), euid)
    data, comparison = _build_company_data(a["verification"], company_claim, given)
    roles = change.get("companyRoles", a["companyRoles"])
    _check_reference_data(data, roles, a["verification"])
    with _lock:
        if a["status"] != "CREATED":
            raise Problem(MODULE, 409, "invalid-state", detail=f"application is {a['status']}")
        a.update(companyData=data, comparison=comparison, companyRoles=list(roles), changedAt=_now(), _given=given)
        _audit(a, "updateApplication", sub=sub)
        return public(a)


def replace_attestation(application_id: str, claims: dict, token: object) -> dict:
    """7.6."""
    sub = claims["sub"]
    a = own(sub, application_id)
    if a["status"] != "CREATED" or a["verification"] == "DOCUMENTS":
        raise Problem(MODULE, 409, "invalid-state", detail="only in status CREATED and the verification path EBW")
    if not (isinstance(token, str) and 0 < len(token) <= ATTESTATION_MAX_CHARS):
        raise _validation([_err("attestation", "required, at most 16 KB")])
    header, payload = attestation.verify(token, claims)
    if a["_attestation"]["attestationId"] == payload["jti"]:
        return public(a)
    new, old = payload["company"], a["_attestationClaims"]["company"]
    fields = []
    if new["ebwoid"] != old["ebwoid"]:
        fields.append("EBWOID")
    if new["country"] != old["country"]:
        fields.append("COUNTRY")
    applicant_euid = _given_identifiers(a["_given"]).get("EUID")
    euid = catalog.normalise_identifier("EUID", new["euid"]) if new.get("euid") else None
    if euid and ((old.get("euid") and catalog.normalise_identifier("EUID", old["euid"]) != euid)
                 or (applicant_euid and applicant_euid != euid)):
        fields.append("EUID")
    if fields:
        raise Problem(MODULE, 400, "attestation-mismatch", fields=fields)
    data, comparison = _company_data_ebw(new, a["_given"])
    _check_reference_data(data, a["companyRoles"], a["verification"])
    if a["_companyRef"]:
        _check_existing_identifiers(calls.company_by_id(a["companyId"]) or {}, new["ebwoid"], euid or applicant_euid)
    with _lock:
        if payload["jti"] in used_jtis:
            raise Problem(MODULE, 409, "attestation-used")
        if a["status"] != "CREATED":
            raise Problem(MODULE, 409, "invalid-state", detail=f"application is {a['status']}")
        used_jtis.add(payload["jti"])
        a.update(companyData=data, comparison=comparison, changedAt=_now(), _attestation=attestation.summary(header, payload),
                 _raw=token, _attestationClaims={"iat": payload["iat"], "exp": payload["exp"], "company": new})
        _audit(a, "replaceAttestation", sub=sub)
        return public(a)


def submit_application(application_id: str, sub: str, body: dict) -> dict:
    """7.10."""
    with _lock:
        a = own(sub, application_id)
        if a["status"] == "SUBMITTED":
            return public(a)
        if a["status"] != "CREATED":
            raise Problem(MODULE, 409, "invalid-state", detail=f"application is {a['status']}")
        consents = body.get("consents")
        valid = isinstance(consents, list) and consents and all(
            isinstance(c, dict) and isinstance(c.get("agreementKey"), str) and isinstance(c.get("version"), str)
            and c.get("language") in ("de", "en") for c in consents)
        if not valid:
            raise _validation([_err("consents", "at least one consent with agreementKey, version and language de or en")])
        if a["verification"] == "EBW" and not attestation.usable_at_submission(a):
            raise Problem(MODULE, 409, "attestation-expired")
        if a["verification"] == "DOCUMENTS":
            types = {d["documentType"] for d in a["documents"]}
            missing_types = [] if "COMMERCIAL_REGISTER_EXTRACT" in types else ["COMMERCIAL_REGISTER_EXTRACT"]
            undeclared = body.get("representationDeclared") is not True
            if missing_types or undeclared:
                raise Problem(MODULE, 400, "documents-incomplete", missingDocumentTypes=missing_types,
                              representationDeclarationMissing=undeclared)
        required = [{"agreementKey": x["agreementKey"], "version": x["version"]} for x in catalog.required(a["companyRoles"])]
        given = {(c["agreementKey"], c["version"]) for c in consents}
        missing = [r for r in required if (r["agreementKey"], r["version"]) not in given]
        if missing:
            raise Problem(MODULE, 400, "consents-incomplete", missing=missing)
        needed = {(r["agreementKey"], r["version"]) for r in required}
        extra = [c["agreementKey"] for c in consents if (c["agreementKey"], c["version"]) not in needed]
        if extra:
            raise _validation([_err("consents", f"unknown or not required terms: {k}") for k in extra])
        now = _now()
        a.update(consents=[{"agreementKey": c["agreementKey"], "version": c["version"], "language": c["language"], "givenAt": now}
                           for c in consents],
                 status="SUBMITTED", submittedAt=now, changedAt=now, _requiredAgreements=required,
                 _consentRecords=[{"agreementKey": c["agreementKey"], "version": c["version"], "language": c["language"],
                                   "givenAt": now, "givenBySub": sub,
                                   "attestationId": (a.get("_attestation") or {}).get("attestationId")} for c in consents])
        if a["verification"] == "DOCUMENTS":
            a["representationDeclared"] = True
        _audit(a, "submitApplication", sub=sub)
        events.publish(MODULE, "ApplicationSubmitted", {"applicationId": a["id"], "companyId": a["companyId"], "kind": a["kind"],
                                                        "existingCompany": a["existingCompany"], "applicantSub": sub})
        return public(a)


def withdraw_application(application_id: str, sub: str) -> dict:
    """7.11."""
    a = own(sub, application_id)
    if a["status"] == "WITHDRAWN":
        return public(a)
    if a["status"] not in OPEN:
        raise Problem(MODULE, 409, "invalid-state", detail=f"application is {a['status']}")
    if a["status"] == "SUBMITTED":
        review = calls.review_status(a["id"])   # not reachable: 502, nothing changed
        if review in ("APPROVED", "DECLINED"):
            raise Problem(MODULE, 409, "already-decided", reviewStatus=review)
    with _lock:
        if a["status"] == "WITHDRAWN":
            return public(a)
        if a["status"] not in OPEN:
            raise Problem(MODULE, 409, "invalid-state", detail=f"application is {a['status']}")
        submitted = a["status"] == "SUBMITTED"
        now = _now()
        a.update(status="WITHDRAWN", withdrawnAt=now, changedAt=now)
        _audit(a, "withdrawApplication", sub=sub)
        if submitted:
            events.publish(MODULE, "ApplicationWithdrawn", {"applicationId": a["id"], "companyId": a["companyId"], "kind": a["kind"],
                                                            "existingCompany": a["existingCompany"]})
        return public(a)


# --------------------------------------------------------------------- supporting documents (7.7 to 7.9)
def document_max_bytes() -> int:
    return int(os.environ.get("DOCUMENT_MAX_BYTES") or 10485760)


def upload_document(application_id: str, sub: str, document_type: str, file_name: str | None, content: bytes) -> dict:
    a = own(sub, application_id)
    if a["status"] != "CREATED" or a["verification"] == "EBW":
        raise Problem(MODULE, 409, "invalid-state", detail="only in status CREATED and the verification path DOCUMENTS")
    errors: list[dict] = []
    if document_type not in DOCUMENT_TYPES:
        errors.append(_err("documentType", f"one of {', '.join(DOCUMENT_TYPES)}"))
    if not file_name or len(file_name) > 200 or re.search(r"[/\\\x00-\x1f]", file_name):
        errors.append(_err("file", "file name of 1 to 200 characters, without path parts and control characters"))
    content_type = next((t for magic, t in SIGNATURES if content.startswith(magic)), None)
    if content_type is None:
        errors.append(_err("file", "PDF, PNG or JPEG, checked by the first bytes"))
    maximum = document_max_bytes()
    if not 1 <= len(content) <= maximum:
        errors.append(_err("file", f"1 to {maximum} bytes"))
    with _lock:
        if a["status"] != "CREATED":
            raise Problem(MODULE, 409, "invalid-state", detail=f"application is {a['status']}")
        if len(a["documents"]) >= int(os.environ.get("DOCUMENT_MAX_COUNT") or 10):
            errors.append(_err("file", "too many supporting documents"))
        if errors:
            raise _validation(errors)
        info = {"documentId": str(uuid.uuid4()), "documentType": document_type, "fileName": file_name,
                "contentType": content_type, "sizeBytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                "uploadedAt": _now()}
        a["documents"].append(info)
        a["_files"][info["documentId"]] = content
        a["changedAt"] = _now()
        _audit(a, "uploadDocument", sub=sub, object_id=info["documentId"])
        return info


def document(a: dict, document_id: str) -> tuple[dict, bytes]:
    info = next((d for d in a["documents"] if d["documentId"] == document_id), None)
    if info is None:
        raise Problem(MODULE, 404, "not-found")
    return info, a["_files"][document_id]


def staff_document(application_id: str, document_id: str, sub: str) -> tuple[dict, bytes]:
    """7.14: every retrieval is in the audit log."""
    a = any_application(application_id)
    found = document(a, document_id)
    with _lock:
        _audit(a, "getAnyDocument", sub=sub, object_id=document_id)
    return found


def delete_document(application_id: str, document_id: str, sub: str) -> None:
    a = own(sub, application_id)
    with _lock:
        if a["status"] != "CREATED":
            raise Problem(MODULE, 409, "invalid-state", detail=f"application is {a['status']}")
        document(a, document_id)
        a["documents"] = [d for d in a["documents"] if d["documentId"] != document_id]
        a["_files"].pop(document_id, None)
        a["changedAt"] = _now()
        _audit(a, "deleteDocument", sub=sub, object_id=document_id)


# ---------------------------------------------------------------------------- terms (7.15, 7.16)
def list_agreement_versions(agreement_key: str | None, status: str | None, page: int, size: int) -> dict:
    found = [a for a in catalog.versions() if (not agreement_key or a["agreementKey"] == agreement_key)
             and (not status or a["status"] == status)]
    found.sort(key=lambda a: a["createdAt"], reverse=True)
    found.sort(key=lambda a: a["agreementKey"])
    return _page(found, page, size)


def _check_agreement(body: dict) -> list[dict]:
    errors: list[dict] = []
    if not (isinstance(body.get("agreementKey"), str) and re.fullmatch(r"[a-z0-9-]{1,64}", body["agreementKey"])):
        errors.append(_err("agreementKey", "lower case letters, digits and hyphens, at most 64"))
    if not (isinstance(body.get("version"), str) and 1 <= len(body["version"]) <= 20):
        errors.append(_err("version", "1 to 20 characters"))
    if body.get("party") not in ("OSP", "DATASPACE"):
        errors.append(_err("party", "OSP or DATASPACE"))
    scope, company_roles = body.get("scope"), body.get("companyRoles")
    if scope not in ("ALL", "COMPANY_ROLE"):
        errors.append(_err("scope", "ALL or COMPANY_ROLE"))
    if scope == "COMPANY_ROLE":
        _check_roles(company_roles, errors)
        if isinstance(company_roles, list):
            errors += [_err("companyRoles", f"not selectable: {r}") for r in company_roles if not catalog.selectable(r)]
    elif company_roles:
        errors.append(_err("companyRoles", "only for scope COMPANY_ROLE"))
    title = body.get("title")
    if not (isinstance(title, dict) and all(isinstance(title.get(k), str) and 1 <= len(title[k]) <= 200 for k in ("de", "en"))):
        errors.append(_err("title", "de and en, 1 to 200 characters"))
    urls = body.get("documentUrls")
    if not (isinstance(urls, dict) and urls and set(urls) <= {"de", "en"}
            and all(isinstance(u, str) and u.startswith("https://") for u in urls.values())):
        errors.append(_err("documentUrls", "de or en, at least one, HTTPS"))
    if not isinstance(body.get("reconsentRequired"), bool):
        errors.append(_err("reconsentRequired", "required"))
    if body.get("reconsentRequired"):
        try:
            due = dt.datetime.fromisoformat(str(body.get("reconsentDueAt")).replace("Z", "+00:00"))
            if due.tzinfo is None or due.timestamp() <= attestation.now():
                errors.append(_err("reconsentDueAt", "must be in the future"))
        except ValueError:
            errors.append(_err("reconsentDueAt", "required with reconsentRequired, date-time"))
    return errors


def create_agreement_version(body: dict, sub: str) -> dict:
    """7.16."""
    errors = _check_agreement(body)
    if errors:
        raise _validation(errors)
    with _lock:
        versions = catalog.versions()
        if any(a["agreementKey"] == body["agreementKey"] and a["version"] == body["version"] for a in versions):
            raise Problem(MODULE, 409, "conflict", detail="this version of the terms already exists")
        for a in versions:
            if a["agreementKey"] == body["agreementKey"]:
                a["status"] = "INACTIVE"
        new = {"agreementKey": body["agreementKey"], "version": body["version"], "party": body["party"], "scope": body["scope"],
               "companyRoles": list(body.get("companyRoles") or []), "title": body["title"], "documentUrls": body["documentUrls"],
               "status": "ACTIVE", "reconsentRequired": body["reconsentRequired"], "reconsentDueAt": body.get("reconsentDueAt"),
               "createdAt": _now(), "createdBy": sub}
        versions.append(new)
        audit_log.append({"at": _now(), "sub": sub, "processId": None, "stepRunId": None, "companyId": None,
                          "operation": "createAgreementVersion", "applicationId": None,
                          "objectId": f"{new['agreementKey']}:{new['version']}"})
        events.publish(MODULE, "AgreementVersionActivated", {"agreementKey": new["agreementKey"], "version": new["version"],
                                                             "party": new["party"], "reconsentRequired": new["reconsentRequired"],
                                                             "reconsentDueAt": new["reconsentDueAt"]})
        return new


# --------------------------------------------------------------------------------- steps (README 8)
def _step_application(input: dict) -> dict:
    a = applications.get(input.get("applicationId"))
    if not a:
        raise Problem(MODULE, 404, "not-found", retryable=False)
    return a


def _step_result(input: dict, a: dict) -> dict:
    return {"stepRunId": input.get("stepRunId"), "state": "DONE",
            "result": {"applicationId": a["id"], "companyId": a["companyId"], "kind": a["kind"], "status": a["status"]}}


def complete_application(input: dict) -> dict:
    with _lock:
        a = _step_application(input)
        if a["status"] == "SUBMITTED":
            now = _now()
            a.update(status="COMPLETED", completedAt=now, changedAt=now)
            events.publish(MODULE, "ApplicationCompleted", {"applicationId": a["id"], "companyId": a["companyId"], "kind": a["kind"]})
        elif a["status"] != "COMPLETED":
            raise Problem(MODULE, 409, "invalid-state", detail=f"application is {a['status']}", retryable=False)
        _audit(a, "stepCompleteApplication", step=input)
        return _step_result(input, a)


def close_application(input: dict) -> dict:
    reason = input.get("reason")
    if not (isinstance(reason, str) and 1 <= len(reason) <= 1000):
        raise Problem(MODULE, 400, "validation", errors=[_err("reason", "1 to 1000 characters")], retryable=False)
    with _lock:
        a = _step_application(input)
        if a["status"] == "SUBMITTED":
            now = _now()
            a.update(status="DECLINED", declineReason=reason, closedAt=now, changedAt=now)
        elif a["status"] not in ("DECLINED", "WITHDRAWN"):
            raise Problem(MODULE, 409, "invalid-state", detail=f"application is {a['status']}", retryable=False)
        _audit(a, "stepCloseApplication", step=input)
        return _step_result(input, a)


# ------------------------------------------------------------------------------- queries (README 9)
def get_application_internal(*, applicationId: str, **_other) -> dict:
    a = applications.get(applicationId)
    if not a:
        raise Problem(MODULE, 404, "not-found")
    detail = None
    if a.get("_attestation"):
        detail = a["_attestation"] | {"signatureCheck": attestation.signature_check(a["_raw"])}
    return public(a) | {"attestation": detail, "requiredAgreements": a["_requiredAgreements"]}


def list_applications_internal(*, applicationId: list[str] | str | None = None, **_other) -> list[dict]:
    """`ApplicationSummary` in the order of the request; unknown IDs are left out."""
    ids = [applicationId] if isinstance(applicationId, str) else applicationId or []
    return [summary(a) for i in ids if (a := applications.get(i))]


def list_agreements_internal(*, status: str | None = None, **_other) -> list[dict]:
    wanted = status or "ACTIVE"
    return [a for a in catalog.versions() if a["status"] == wanted]
