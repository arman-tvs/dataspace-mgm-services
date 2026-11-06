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
"""The automatic pre-check of C1-M3 (README 6.2, 6.3).

Each check takes the application (`ApplicationInternal` of C1-M2) and returns
`(result, details)`. A neighbour that is not reachable gives `ERROR` with `error` in the finding.
Findings carry no names of people and no values of the application's identifiers.
"""
from __future__ import annotations

import datetime as dt
import os

from portal_common import settings
from portal_common.problems import Problem

from . import calls

ORDER = ["ATTESTATION_VALID", "REPRESENTATION_CONFIRMED", "COMPANY_DATA_MATCH", "NO_DUPLICATE",
         "CSP_MATCH_EXPECTED", "CONSENTS_COMPLETE"]
ATTESTATION_CHECKS = {"ATTESTATION_VALID", "REPRESENTATION_CONFIRMED", "COMPANY_DATA_MATCH"}
DUPLICATE_STATUSES = ["REQUESTED", "ACTIVE", "INACTIVE"]
MATCH_ORDER = ["EBWOID", "EUID", "NAME"]
REJECTED = "_rejected"


def _time(value: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _identifiers(app: dict) -> dict[str, str]:
    return {i["type"]: i["value"] for i in (app.get("companyData") or {}).get("identifiers", [])}


def attestation_valid(app: dict) -> tuple[str, dict]:
    att = app.get("attestation") or {}
    sig = (att.get("signatureCheck") or app.get("signatureCheck") or {}).get("result")
    if sig == "UNAVAILABLE":
        return "ERROR", {"signatureCheck": sig, "error": "signature check of C1-M2 unavailable"}
    issued, expires, submitted = _time(att.get("issuedAt")), _time(att.get("expiresAt")), _time(app.get("submittedAt"))
    expired = bool(expires and submitted and submitted >= expires)
    in_time = bool(issued and expires and submitted and issued <= submitted < expires)
    return ("PASSED" if sig == "VALID" and in_time else "FAILED"), {"signatureCheck": sig, "expiredAtSubmission": expired}


def representation_confirmed(app: dict) -> tuple[str, dict]:
    rep = (app.get("attestation") or {}).get("representation") or {}
    reasons = list(rep.get("reasons") or [])
    return ("PASSED" if rep.get("confirmed") is True else "FAILED"), {"representationReasons": reasons}


def company_data_match(app: dict) -> tuple[str, dict]:
    comparison = app.get("comparison") or []
    mismatched = [c["field"] for c in comparison if c.get("result") == "MISMATCH"]
    unverified = [c["field"] for c in comparison if c.get("result") == "NOT_IN_ATTESTATION"]
    return ("FAILED" if mismatched else "PASSED"), {"mismatchedFields": mismatched, "unverifiedFields": unverified}


def _neighbour_failed(name: str, problem: Problem) -> tuple[str, dict]:
    """`ERROR` of a check. A rejected request (502 `neighbour-rejected`) would be rejected again; `open-review`
    reads the private mark, which is not part of the finding, to answer that a repetition does not help."""
    if problem.ext.get("retryable") is False:
        return "ERROR", {"error": f"{name} rejected the request", REJECTED: True}
    return "ERROR", {"error": f"{name} not reachable"}


def no_duplicate(app: dict) -> tuple[str, dict]:
    types = [t.strip() for t in os.environ.get("DUPLICATE_CHECK_IDENTIFIER_TYPES", "EUID,EBWOID,VAT_ID,LEI_CODE")
             .split(",") if t.strip()]
    ids = [{"type": t, "value": v} for t, v in _identifiers(app).items() if t in types]
    if not ids:
        return "PASSED", {"duplicates": []}
    try:
        found = calls.identifier_matches(ids, app["companyId"], DUPLICATE_STATUSES)
    except Problem as p:
        return _neighbour_failed("C3-M1", p)
    dups = [{"companyId": m["companyId"], "companyStatus": m["status"], "matchedOn": m["matchedOn"]} for m in found]
    return ("FAILED" if dups else "PASSED"), {"duplicates": dups}


def _merge(found: list[dict]) -> list[dict]:
    """Matches with the same BPN become one, `matchedBy` as a list (6.3)."""
    merged: dict[str, dict] = {}
    for f in found:
        m = merged.setdefault(f["bpn"], {"bpn": f["bpn"], "matchedBy": [], "homeOspId": f.get("homeOspId"),
                                         "homeOspName": f.get("homeOspName"),
                                         "homeIsThisOsp": f.get("homeIsThisOsp",
                                                                f.get("homeOspId") == settings.get("ospId")),
                                         "memberActive": f.get("memberActive"), "expected": False})
        by = f.get("matchedBy")
        for b in by if isinstance(by, list) else [by]:
            if b and b not in m["matchedBy"]:
                m["matchedBy"].append(b)
    for m in merged.values():
        m["matchedBy"].sort(key=lambda b: MATCH_ORDER.index(b) if b in MATCH_ORDER else len(MATCH_ORDER))
    return list(merged.values())


def _evaluate(kind: str, matches: list[dict], company_bpn: str | None, existing: bool) -> tuple[str, dict | None]:
    """Table of 6.3, the first matching row applies. Returns `cspOutcome` and the expected match."""
    here = [m for m in matches if m["homeIsThisOsp"]]
    if kind == "ONBOARDING":
        return ("NO_MATCH" if not matches else "REGISTERED_HERE" if here else "REGISTERED_AT_OTHER_OSP"), None
    if not matches:
        return "NO_MATCH", None
    if kind == "TRANSFER":
        if here:
            return "REGISTERED_HERE", None
        if len(matches) > 1:
            return "MULTIPLE_MATCHES", None
        only = matches[0]
        if not {"EBWOID", "EUID"} & set(only["matchedBy"]):
            return "NAME_MATCH_ONLY", None
        if existing and only["bpn"] != company_bpn:
            return "BPN_MISMATCH", None
        return "EXPECTED_MATCH", only
    own = next((m for m in matches if company_bpn and m["bpn"] == company_bpn), None)   # REACTIVATION
    if own is None:
        return "BPN_MISMATCH", None
    if not own["homeIsThisOsp"]:
        return "REGISTERED_AT_OTHER_OSP", None
    if len(matches) > 1:
        return "MULTIPLE_MATCHES", None
    return "EXPECTED_MATCH", own


def csp_match_expected(app: dict) -> tuple[str, dict]:
    ids, data = _identifiers(app), app.get("companyData") or {}
    kind, existing = app["kind"], bool(app.get("existingCompany"))
    try:
        found = calls.find_companies(ids.get("EBWOID"), ids.get("EUID"), data.get("legalName"),
                                     (data.get("address") or {}).get("countryCode"))
    except Problem as p:
        return _neighbour_failed("C3-M2", p)
    matches = _merge(found)
    company_bpn = None
    if matches and (kind == "REACTIVATION" or (kind == "TRANSFER" and existing)):
        try:
            company = calls.get_company(app["companyId"])
        except Problem as p:
            return _neighbour_failed("C3-M1", p)
        company_bpn = (company or {}).get("bpn")
    outcome, expected = _evaluate(kind, matches, company_bpn, existing)
    if expected is not None:
        expected["expected"] = True
    passed = outcome == ("NO_MATCH" if kind == "ONBOARDING" else "EXPECTED_MATCH")
    return ("PASSED" if passed else "FAILED"), {"cspOutcome": outcome, "cspMatches": matches}


def consents_complete(app: dict) -> tuple[str, dict]:
    given = {(c.get("agreementKey"), c.get("version")) for c in app.get("consents") or []}
    missing = [{"agreementKey": r["agreementKey"], "version": r["version"]}
               for r in app.get("requiredAgreements") or [] if (r["agreementKey"], r["version"]) not in given]
    return ("FAILED" if missing else "PASSED"), {"missing": missing}


CHECKS = {"ATTESTATION_VALID": attestation_valid, "REPRESENTATION_CONFIRMED": representation_confirmed,
          "COMPANY_DATA_MATCH": company_data_match, "NO_DUPLICATE": no_duplicate,
          "CSP_MATCH_EXPECTED": csp_match_expected, "CONSENTS_COMPLETE": consents_complete}


def run(key: str, app: dict) -> tuple[str, dict]:
    if key in ATTESTATION_CHECKS and app.get("verification") == "DOCUMENTS":
        return "NOT_APPLICABLE", {}
    return CHECKS[key](app)
