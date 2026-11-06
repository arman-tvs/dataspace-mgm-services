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
"""Calls of C1-M3 to its neighbours (README 11) with the built-in stand-ins.

Address per FRAMEWORK 4.7 through `portal_common.neighbours`: `in-process` or a URL calls the
neighbour, an empty address answers from the stand-in files `STUB_APPLICATIONS_FILE`,
`STUB_COMPANIES_FILE` and `STUB_CSP_FILE` (README 11, 14). The files are read on every call; the
JSON string "unavailable" instead of a list means "not reachable" (502 `upstream-error`).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from portal_common import neighbours
from portal_common.problems import Problem

MODULE = "c1-m3"
C1_M2, C3_M1, C3_M2 = "c1-m2", "c3-m1", "c3-m2"


def _stub(var: str, target: str) -> list[dict]:
    path = os.environ.get(var, "")
    if not path:
        raise Problem(MODULE, 502, "upstream-error", detail=f"{target} stand-in: {var} not set", retryable=True)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data == "unavailable" or not isinstance(data, list):
        raise Problem(MODULE, 502, "upstream-error", detail=f"{target} not reachable", retryable=True)
    return data


def _norm(value: object) -> str:
    """Comparison per identifier type in upper case without spaces, `.`, `-`, `/` (11.2)."""
    return re.sub(r"[\s.\-/]", "", str(value)).upper()


# ------------------------------------------------------------------------- C1-M2 Registration (11.1)
def get_application(application_id: str) -> dict | None:
    """`ApplicationInternal` (C1-M2 9.1), None if unknown."""
    if not neighbours.is_standin(C1_M2):
        return neighbours.query(MODULE, C1_M2, "get_application_internal", applicationId=application_id)
    return next((a for a in _stub("STUB_APPLICATIONS_FILE", C1_M2) if a.get("id") == application_id), None)


def list_applications(application_ids: list[str]) -> list[dict]:
    """`ApplicationSummary` (C1-M2 9.2) of the given applications."""
    if not application_ids:
        return []
    if not neighbours.is_standin(C1_M2):
        return neighbours.query(MODULE, C1_M2, "list_applications_internal", applicationId=application_ids) or []
    return [{"id": a["id"], "companyId": a["companyId"], "kind": a["kind"], "existingCompany": a["existingCompany"],
             "verification": a["verification"], "status": a["status"], "legalName": a["companyData"]["legalName"],
             "countryCode": (a["companyData"].get("address") or {}).get("countryCode"),
             "companyRoles": a.get("companyRoles", []), "createdAt": a.get("createdAt"),
             "submittedAt": a.get("submittedAt")}
            for a in _stub("STUB_APPLICATIONS_FILE", C1_M2) if a.get("id") in application_ids]


def application_status(application_id: str) -> str | None:
    found = list_applications([application_id])
    return found[0]["status"] if found else None


# ---------------------------------------------------------------------- C3-M1 Company Profile (11.2)
def identifier_matches(identifiers: list[dict], exclude_company_id: str, statuses: list[str]) -> list[dict]:
    """`matches` of C3-M1 `findIdentifierMatches` (9.3): `companyId`, `status`, `bpn`, `matchedOn`."""
    if not neighbours.is_standin(C3_M1):
        found = neighbours.query(MODULE, C3_M1, "find_identifier_matches", identifiers=identifiers,
                                 excludeCompanyId=exclude_company_id, statuses=statuses) or {}
        return found.get("matches", [])
    wanted = {(i["type"], _norm(i["value"])) for i in identifiers}
    out = []
    for c in _stub("STUB_COMPANIES_FILE", C3_M1):
        if c["id"] == exclude_company_id or c["status"] not in statuses:
            continue
        on = sorted({t for t, _ in wanted & {(i["type"], _norm(i["value"])) for i in c.get("identifiers", [])}})
        if on:
            out.append({"companyId": c["id"], "status": c["status"], "bpn": c.get("bpn"), "matchedOn": on})
    return out


def get_company(company_id: str) -> dict | None:
    """C3-M1 `queryCompany` (9.1): `CompanyInternal`, of which `id`, `status`, `bpn`; None if unknown."""
    if not neighbours.is_standin(C3_M1):
        return neighbours.query(MODULE, C3_M1, "query_company", companyId=company_id)
    return next((c for c in _stub("STUB_COMPANIES_FILE", C3_M1) if c["id"] == company_id), None)


# --------------------------------------------------------------------- C3-M2 CSP Connection (11.3)
def find_companies(ebwoid: str | None, euid: str | None, legal_name: str | None, country: str | None) -> list[dict]:
    """List of `CspCompanyMatch` (C3-M2 9), one entry per match; `matchedBy` is one type."""
    if not neighbours.is_standin(C3_M2):
        found = neighbours.query(MODULE, C3_M2, "find_companies", ebwoid=ebwoid, euid=euid, legalName=legal_name,
                                 country=country) or []
        return found.get("items", []) if isinstance(found, dict) else found
    out = []
    for c in _stub("STUB_CSP_FILE", C3_M2):
        if ebwoid and c.get("ebwoid") == ebwoid:
            by = "EBWOID"
        elif euid and c.get("euid") == euid:
            by = "EUID"
        elif legal_name and country and (c.get("legalName") or "").casefold() == legal_name.casefold() \
                and (c.get("country") or "").casefold() == country.casefold():
            by = "NAME"
        else:
            continue
        out.append({k: c.get(k) for k in ("bpn", "legalName", "country", "homeOspId", "homeOspName", "homeIsThisOsp",
                                          "memberActive")} | {"matchedBy": by})
    return out
