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
"""Reference data of C1-M2: countries and identifier types from `masterDataFile` (FRAMEWORK 4.8), company
roles and terms from `CATALOG_FILE` (README 14.3), by default the shared catalogue of `testdata/`."""
from __future__ import annotations

import functools
import json
import os
import re
from pathlib import Path

from portal_common import settings
from tools import testdata

INITIAL_AT = "2026-01-01T00:00:00Z"
# README 14.3; the agreements of a role come from the catalogue
ROLES = [
    {"role": "ACTIVE_PARTICIPANT", "selectable": True, "name": {"de": "Teilnehmer", "en": "Participant"},
     "description": {"de": "Datenanbieter, Datenkonsument, App-Nutzer", "en": "Data provider, data consumer, app user"}},
    {"role": "APP_PROVIDER", "selectable": True, "name": {"de": "App-Anbieter", "en": "App provider"},
     "description": {"de": "bietet Apps im Marktplatz an", "en": "offers apps in the marketplace"}},
    {"role": "SERVICE_PROVIDER", "selectable": True, "name": {"de": "Service-Anbieter", "en": "Service provider"},
     "description": {"de": "bietet Services im Marktplatz an", "en": "offers services in the marketplace"}},
    {"role": "ONBOARDING_SERVICE_PROVIDER", "selectable": False,
     "name": {"de": "Onboarding-Dienstleister", "en": "Onboarding service provider"},
     "description": {"de": "Unternehmen des OSP", "en": "Company of the OSP"}},
]

agreements: list[dict] = []
roles: list[dict] = []


def _version(x: dict) -> dict:
    return {"agreementKey": x["agreementKey"], "version": x["version"], "party": x["party"], "scope": x["scope"],
            "companyRoles": list(x.get("companyRoles") or []), "title": x["title"], "documentUrls": x["documentUrls"],
            "status": "ACTIVE", "reconsentRequired": False, "reconsentDueAt": None, "createdAt": INITIAL_AT,
            "createdBy": None}


def reset() -> None:
    """Initial values, taken over at start (README 5)."""
    agreements.clear()
    roles.clear()
    path = os.environ.get("CATALOG_FILE")
    if path:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        roles.extend(data["companyRoles"])
        for x in data["agreements"]:
            assigned = [r["role"] for r in data["companyRoles"] if x["key"] in r.get("agreements", [])]
            agreements.append(_version({**x, "agreementKey": x["key"], "companyRoles": assigned}))
    else:
        roles.extend(ROLES)
        agreements.extend(_version(x) for x in testdata.agreements())


@functools.lru_cache(maxsize=4)
def _master(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def master() -> dict:
    return _master(str(settings.resolve_path(settings.get("masterDataFile"))))


def country(code: str | None) -> dict | None:
    return next((c for c in master()["countries"] if c["code"] == code), None)


def identifier_pattern(type_: str, code: str) -> str | None:
    """Regular expression per country, otherwise `Worldwide` (6.6)."""
    entry = next((t for t in master()["identifierTypes"] if t["type"] == type_), None)
    return (entry or {}).get("patterns", {}).get(code) or (entry or {}).get("patterns", {}).get("Worldwide")


def identifier_error(type_: str, value: str, code: str) -> str | None:
    """Why this identifier is not allowed for this country (6.6), or None."""
    c = country(code)
    if c is None or type_ not in c.get("identifierTypes", []):
        return f"identifier type {type_} is not allowed for country {code}"
    pattern = identifier_pattern(type_, code)
    if pattern and not re.fullmatch(pattern, value):
        return f"{type_} has an invalid format for country {code}"
    if type_ == "EUID" and value[:2] != code:
        return "EUID must start with the country of the company"
    return None


def normalise_identifier(type_: str, value: str) -> str:
    """6.6: whitespace removed at both ends; `EUID`, `VAT_ID`, `LEI_CODE`, `EORI` in upper case."""
    value = value.strip()
    return value.upper() if type_ in ("EUID", "VAT_ID", "LEI_CODE", "EORI") else value


def all_roles() -> list[dict]:
    if not roles:
        reset()
    return roles


def versions() -> list[dict]:
    if not agreements:
        reset()
    return agreements


def selectable(role: str) -> bool:
    return any(r["role"] == role and r.get("selectable") for r in all_roles())


def active() -> list[dict]:
    return [a for a in versions() if a["status"] == "ACTIVE"]


def required(company_roles: list[str]) -> list[dict]:
    """Required terms (6.8): active with scope ALL, plus active ones assigned to a selected role."""
    return [a for a in active() if a["scope"] == "ALL" or set(a["companyRoles"]) & set(company_roles)]
