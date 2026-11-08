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
"""Reference data for people (README 7.1): countries, identifier types, company roles and terms."""
from __future__ import annotations

from modules.c1_m2 import catalog, errors
from modules.c1_m2.services.common import err


def list_countries(lang: str) -> list[dict]:
    return sorted(({"code": c["code"], "name": c["name"].get(lang) or c["name"]["en"]}
                   for c in catalog.master()["countries"]),
                  key=lambda c: c["code"])


def list_identifier_types(country_code: str, lang: str) -> list[dict]:
    country = catalog.country(country_code)
    if country is None:
        raise errors.not_found()
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
        raise errors.validation([err("companyRole", f"unknown or not selectable role: {r}") for r in bad])
    return [{"agreementKey": a["agreementKey"], "version": a["version"], "party": a["party"], "scope": a["scope"],
             "title": a["title"].get(lang) or a["title"]["en"], "documentUrls": a["documentUrls"],
             "companyRoles": a["companyRoles"]} for a in catalog.required(company_roles)]
