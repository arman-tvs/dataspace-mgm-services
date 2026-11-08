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
"""Input checks of C1-M2 (README 6.2, 6.6, 6.7, 7.2, 7.5, 7.16); every check collects `FieldError`s."""
from __future__ import annotations

import datetime as dt
import re
import uuid

from modules.c1_m2 import attestation, catalog, errors
from modules.c1_m2.errors import FieldError
from modules.c1_m2.services.common import ATTESTATION_MAX_CHARS, IDENTIFIER_TYPES, KINDS, VERIFICATIONS, err


def check_address(address: object, field: str, invalid: list[FieldError], required: bool = True) -> None:
    if not isinstance(address, dict):
        invalid.append(err(field, "must be an object"))
        return
    limits = (("streetName", 150, True), ("streetNumber", 20, False), ("postalCode", 12, False), ("city", 150, True))
    for name, maximum, needed in limits:
        value = address.get(name)
        if value in (None, ""):
            if needed and required:
                invalid.append(err(f"{field}.{name}", "required"))
        elif not isinstance(value, str) or len(value) > maximum:
            invalid.append(err(f"{field}.{name}", f"text of at most {maximum} characters"))
    region = address.get("region")
    if region not in (None, "") and not (isinstance(region, str) and re.fullmatch(r"[A-Z0-9]{1,3}", region)):
        invalid.append(err(f"{field}.region", "code of the region, 1 to 3 characters"))
    if not (isinstance(address.get("countryCode"), str) and re.fullmatch(r"[A-Z]{2}", address["countryCode"])):
        invalid.append(err(f"{field}.countryCode", "ISO 3166-1 alpha-2"))


def check_identifiers(identifiers: object, invalid: list[FieldError]) -> None:
    if not isinstance(identifiers, list) or len(identifiers) > 10:
        invalid.append(err("identifiers", "list of at most 10 identifiers"))
        return
    seen = set()
    for i, x in enumerate(identifiers):
        if not isinstance(x, dict) or x.get("type") not in IDENTIFIER_TYPES \
                or not isinstance(x.get("value"), str) or not 1 <= len(x["value"]) <= 200:
            invalid.append(err(f"identifiers[{i}]", "needs a known type and a value of 1 to 200 characters"))
        elif x["type"] in seen:
            invalid.append(err(f"identifiers[{i}]", f"at most one identifier per type: {x['type']}"))
        else:
            seen.add(x["type"])


def check_company_fields(data: dict, invalid: list[FieldError]) -> None:
    name = data.get("legalName")
    if name is not None and not (isinstance(name, str) and 1 <= len(name) <= 160 and re.fullmatch(r"\S(.*\S)?", name)):
        invalid.append(err("legalName", "1 to 160 characters, without whitespace at the start and end"))
    short = data.get("shortName")
    if short is not None and not (isinstance(short, str) and len(short) <= 60):
        invalid.append(err("shortName", "at most 60 characters"))
    if data.get("address") is not None:
        check_address(data["address"], "address", invalid)
    if data.get("identifiers") is not None:
        check_identifiers(data["identifiers"], invalid)


def check_roles(company_roles: object, invalid: list[FieldError]) -> None:
    if not isinstance(company_roles, list) or not company_roles:
        invalid.append(err("companyRoles", "at least one company role"))
    elif len(set(map(str, company_roles))) != len(company_roles):
        invalid.append(err("companyRoles", "without duplicates"))


def is_uuid(value: object) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def check_create(body: dict) -> None:
    """7.2 step 2 with the rules of 6.2; the field errors in the order of the checks."""
    invalid: list[FieldError] = []
    _check_kind_and_path(body, invalid)
    _check_company_reference(body, invalid)
    _check_create_data(body, invalid)
    if invalid:
        raise errors.validation(invalid)


def _check_kind_and_path(body: dict, invalid: list[FieldError]) -> None:
    """`kind`, `verification` and the `attestation` the verification path needs."""
    kind, verification = body.get("kind"), body.get("verification")
    if kind not in KINDS:
        invalid.append(err("kind", f"one of {', '.join(KINDS)}"))
    if verification not in VERIFICATIONS:
        invalid.append(err("verification", f"one of {', '.join(VERIFICATIONS)}"))
    token = body.get("attestation")
    if verification == "EBW" and not (isinstance(token, str) and 0 < len(token) <= ATTESTATION_MAX_CHARS):
        invalid.append(err("attestation", "required for EBW, at most 16 KB"))
    if verification == "DOCUMENTS" and token is not None:
        invalid.append(err("attestation", "not allowed for DOCUMENTS"))


def _check_company_reference(body: dict, invalid: list[FieldError]) -> None:
    """`companyId` or `bpn` of an existing company (6.2) and the `companyRoles` that go with it."""
    kind = body.get("kind")
    reference = body.get("companyId") or body.get("bpn")
    if body.get("companyId") and body.get("bpn"):
        invalid.append(err("companyId", "companyId and bpn must not both be given"))
    if body.get("companyId") and not is_uuid(body["companyId"]):
        invalid.append(err("companyId", "must be a UUID"))
    if body.get("bpn") and not (isinstance(body["bpn"], str) and re.fullmatch(r"BPNL[A-Z0-9]{12}", body["bpn"])):
        invalid.append(err("bpn", "must be a BPN"))
    if kind == "ONBOARDING" and reference:
        invalid.append(err("companyId", "no reference for ONBOARDING"))
    if kind == "REACTIVATION" and not reference:
        invalid.append(err("companyId", "reference required for REACTIVATION"))
    if body.get("companyRoles") is not None or not reference:
        check_roles(body.get("companyRoles"), invalid)


def _check_create_data(body: dict, invalid: list[FieldError]) -> None:
    """`companyData`; for the verification path `DOCUMENTS` name, address and an identifier are required."""
    data = body.get("companyData")
    if data is not None and not isinstance(data, dict):
        invalid.append(err("companyData", "must be an object"))
    elif data:
        check_company_fields(data, invalid)
    if body.get("verification") == "DOCUMENTS":
        data = data if isinstance(data, dict) else {}
        for name in ("legalName", "address"):
            if not data.get(name):
                invalid.append(err(f"companyData.{name}", "required for DOCUMENTS"))
        if not data.get("identifiers"):
            invalid.append(err("companyData.identifiers", "at least one identifier for DOCUMENTS"))


def check_reference_data(a_data: dict, company_roles: list[str], verification: str) -> None:
    """7.2 step 9: country, identifier types, formats (6.6), selectable roles (6.7)."""
    invalid: list[FieldError] = []
    code = a_data["address"].get("countryCode")
    if catalog.country(code) is None:
        invalid.append(err("address.countryCode", f"unknown country {code}"))
    else:
        for i, x in enumerate(a_data["identifiers"]):
            if verification == "DOCUMENTS" and x["type"] == "EBWOID":
                invalid.append(err(f"identifiers[{i}]", "EBWOID is not allowed without a Business Wallet"))
            elif message := catalog.identifier_error(x["type"], x["value"], code):
                invalid.append(err(f"identifiers[{i}]", message))
    if len(a_data["identifiers"]) > 10:
        invalid.append(err("identifiers", "at most 10 identifiers"))
    invalid += [err("companyRoles", f"not selectable: {r}") for r in company_roles if not catalog.selectable(r)]
    if invalid:
        raise errors.validation(invalid)


def check_agreement(body: dict) -> list[FieldError]:
    """7.16: a new version of terms; the field errors in the order of the checks."""
    invalid: list[FieldError] = []
    _check_agreement_identity(body, invalid)
    _check_agreement_scope(body, invalid)
    _check_agreement_texts(body, invalid)
    _check_reconsent(body, invalid)
    return invalid


def _check_agreement_identity(body: dict, invalid: list[FieldError]) -> None:
    if not (isinstance(body.get("agreementKey"), str) and re.fullmatch(r"[a-z0-9-]{1,64}", body["agreementKey"])):
        invalid.append(err("agreementKey", "lower case letters, digits and hyphens, at most 64"))
    if not (isinstance(body.get("version"), str) and 1 <= len(body["version"]) <= 20):
        invalid.append(err("version", "1 to 20 characters"))
    if body.get("party") not in ("OSP", "DATASPACE"):
        invalid.append(err("party", "OSP or DATASPACE"))


def _check_agreement_scope(body: dict, invalid: list[FieldError]) -> None:
    scope, company_roles = body.get("scope"), body.get("companyRoles")
    if scope not in ("ALL", "COMPANY_ROLE"):
        invalid.append(err("scope", "ALL or COMPANY_ROLE"))
    if scope == "COMPANY_ROLE":
        check_roles(company_roles, invalid)
        if isinstance(company_roles, list):
            invalid += [err("companyRoles", f"not selectable: {r}")
                        for r in company_roles if not catalog.selectable(r)]
    elif company_roles:
        invalid.append(err("companyRoles", "only for scope COMPANY_ROLE"))


def _check_agreement_texts(body: dict, invalid: list[FieldError]) -> None:
    title = body.get("title")
    if not (isinstance(title, dict)
            and all(isinstance(title.get(k), str) and 1 <= len(title[k]) <= 200 for k in ("de", "en"))):
        invalid.append(err("title", "de and en, 1 to 200 characters"))
    urls = body.get("documentUrls")
    if not (isinstance(urls, dict) and urls and set(urls) <= {"de", "en"}
            and all(isinstance(u, str) and u.startswith("https://") for u in urls.values())):
        invalid.append(err("documentUrls", "de or en, at least one, HTTPS"))


def _check_reconsent(body: dict, invalid: list[FieldError]) -> None:
    if not isinstance(body.get("reconsentRequired"), bool):
        invalid.append(err("reconsentRequired", "required"))
    if body.get("reconsentRequired"):
        try:
            due = dt.datetime.fromisoformat(str(body.get("reconsentDueAt")).replace("Z", "+00:00"))
            if due.tzinfo is None or due.timestamp() <= attestation.now():
                invalid.append(err("reconsentDueAt", "must be in the future"))
        except ValueError:
            invalid.append(err("reconsentDueAt", "required with reconsentRequired, date-time"))
