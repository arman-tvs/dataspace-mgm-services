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
#  Assisted-By: Hermes Agent (deepseek-v4.1-flash)
#################################################################################
"""Field rules of C3-M1 README 5 and the identifier rules of README 6.4.

Every function returns a list of `{"field": ..., "reason": ...}` dicts and never raises, so the
caller can collect all errors into one 400 `validation` Problem (`errors`, README 12). Reason
tokens are short and stable: `required`, `type`, `too-long`, `too-short`, `whitespace`, `format`,
`unknown`, `unknown-country`, `duplicate-type`, `missing`, `business-wallet-source`, `path-parts`,
`media-type`, `too-large`.

Patterns come from the shared reference data (`masterDataFile`, settings key of the same name,
resolved relative to the settings file, OP-13). If the file or a type is missing, the fallback
patterns of README 6.4 apply.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from portal_common import settings

IDENTIFIER_TYPES = ("EUID", "EBWOID", "VAT_ID", "COMMERCIAL_REG_NUMBER", "LEI_CODE", "EORI")
IDENTIFIER_SOURCES = ("BUSINESS_WALLET", "DECLARED")
STATUSES = ("REQUESTED", "ACTIVE", "REJECTED", "INACTIVE")
DEACTIVATION_REASONS = ("MANUAL", "TRANSFERRED")
CORE_DATA_SOURCES = ("EBW", "MANUAL")
MEDIA_TYPES = ("application/pdf", "image/png", "image/jpeg")

NAME_MAX = 160
SHORT_NAME_MAX = 100
STREET_MAX = 255
HOUSE_NUMBER_MAX = 50
ADDRESS_ADDITION_MAX = 255
POSTAL_CODE_MAX = 12
CITY_MAX = 255
REGION_PATTERN = re.compile(r"^[A-Z0-9]{1,3}$")
COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")
BPN_PATTERN = re.compile(r"^BPNL[A-Z0-9]{12}$")
COMMENT_MAX = 1000
REASON_MAX = 500
DECISION_REASON_MAX = 1000
FILE_NAME_MAX = 200
NORMALISE_STRIP = re.compile(r"[\s.\-/]")

#: README 6.4 fallbacks, used when the reference data file or the type in it is missing.
FALLBACK_PATTERNS: dict[str, dict[str, str]] = {
    "EUID": {"Worldwide": r"^[A-Za-z0-9.\-]{4,100}$"},
    "EBWOID": {"Worldwide": r"^\S{1,255}$"},
    "VAT_ID": {"Worldwide": r"^(?!.*\s$)([A-Za-z0-9](\.|\s|-|\/)?){5,18}$", "DE": r"^DE\d{9}$"},
    "COMMERCIAL_REG_NUMBER": {
        "Worldwide": r"^(?!.*\s$)([A-Za-zÀ-ÿ0-9.()](\.|\s|-|_)?){4,50}$",
        "DE": r"^(?!.*\s$)([A-Za-zÀ-ÿ])([A-Za-zÀ-ÿ0-9.()](\s|-|_)?){4,50}$",
        "FR": r"^\d{9}$",
    },
    "LEI_CODE": {"Worldwide": r"^[A-Za-z0-9]{20}$"},
    "EORI": {"Worldwide": r"^[A-Z]{2}[A-Za-z0-9]{1,15}$"},
}

#: camelCase of the API -> snake_case of README 5 (`address` is nested, see `flat_fields`).
ALIASES = {
    "shortName": "short_name", "houseNumber": "house_number",
    "addressAddition": "address_addition", "postalCode": "postal_code",
    "countryCode": "country_code", "coreDataSource": "core_data_source",
    "bpnAssignedAt": "bpn_assigned_at", "coreDataVerifiedAt": "core_data_verified_at",
    "verificationRef": "verification_ref", "applicationId": "application_id",
    "deactivationReason": "deactivation_reason", "createdAt": "created_at",
    "changedAt": "changed_at", "activatedAt": "activated_at", "rejectedAt": "rejected_at",
    "deactivatedAt": "deactivated_at", "reactivatedAt": "reactivated_at",
}
ADDRESS_FIELDS = ("street", "house_number", "address_addition", "postal_code", "city", "region",
                  "country_code")

_reference_cache: tuple[str, int, dict | None] | None = None


# ------------------------------------------------------------------------ comparison (5, 6.3)
def normalise(value) -> str:
    """NFKC, trimmed, inner whitespace collapsed to one space; case stays (6.3)."""
    return " ".join(unicodedata.normalize("NFKC", str(value)).split())


def value_normalized(value) -> str:
    """Upper case without spaces, `.`, `-` and `/` (5, 6.4) — what the duplicate search compares."""
    return NORMALISE_STRIP.sub("", unicodedata.normalize("NFKC", str(value))).upper()


def same_value(left, right) -> bool:
    """Comparison of 6.3: equal after normalisation, case ignored."""
    return normalise(left).casefold() == normalise(right).casefold()


# ------------------------------------------------------------------------- reference data (6.4)
def _reference_path() -> Path | None:
    try:
        return settings.resolve_path(settings.get("masterDataFile"))
    except Exception:      # no settings file, or an unreadable one: fall back to README 6.4
        return None


def _reference_data() -> dict | None:
    global _reference_cache
    path = _reference_path()
    if path is None or not path.is_file():
        return None
    try:
        stat = path.stat()
        if _reference_cache and _reference_cache[:2] == (str(path), stat.st_mtime_ns):
            return _reference_cache[2]
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    _reference_cache = (str(path), stat.st_mtime_ns, data)
    return data


def known_countries() -> set[str] | None:
    """Country codes of the reference data; `None` if there is no usable reference data."""
    data = _reference_data()
    if data is None:
        return None
    return {c["code"] for c in data.get("countries") or [] if isinstance(c, dict) and c.get("code")}


def pattern_for(identifier_type: str, country_code: str | None) -> str | None:
    """Pattern for a type and country, per country with the Worldwide fallback (6.4)."""
    data = _reference_data()
    if data is not None:
        entry = next((t for t in data.get("identifierTypes") or []
                      if isinstance(t, dict) and t.get("type") == identifier_type), None)
        if entry is not None:
            patterns = entry.get("patterns") or {}
            pattern = patterns.get(country_code or "") or patterns.get("Worldwide")
            if pattern:
                return pattern
    fallback = FALLBACK_PATTERNS.get(identifier_type) or {}
    return fallback.get(country_code or "") or fallback.get("Worldwide")


# ---------------------------------------------------------------------------------- helpers
def _error(field: str, reason: str) -> dict:
    return {"field": field, "reason": reason}


def _text(errors: list[dict], field: str, value, *, required: bool = False,
          min_length: int = 0, max_length: int | None = None, strip: bool = False) -> None:
    if value is None:
        if required:
            errors.append(_error(field, "required"))
        return
    if not isinstance(value, str):
        errors.append(_error(field, "type"))
        return
    if not value.strip():
        if required:
            errors.append(_error(field, "required"))
        return
    if strip and value != value.strip():
        errors.append(_error(field, "whitespace"))
    if max_length is not None and len(value) > max_length:
        errors.append(_error(field, "too-long"))
    if min_length and len(value.strip()) < min_length:
        errors.append(_error(field, "too-short"))


def field_name(key: str) -> str:
    return ALIASES.get(key, key)


def flat_fields(data: dict) -> dict:
    """camelCase and a nested `address` to the flat snake_case fields of README 5."""
    if not isinstance(data, dict):
        return {}
    flat = {}
    for key, value in data.items():
        if key == "address" and isinstance(value, dict):
            flat.update({field_name(k): v for k, v in value.items()})
        else:
            flat[field_name(key)] = value
    return flat


# --------------------------------------------------------------------------- company fields (5)
def validate_company(data: dict, *, partial: bool = False) -> list[dict]:
    """Field rules of README 5. `partial`: only the fields given are checked."""
    flat = flat_fields(data)
    errors: list[dict] = []
    _text(errors, "name", flat.get("name"), required=not partial, min_length=1,
          max_length=NAME_MAX, strip=True)
    _text(errors, "short_name", flat.get("short_name"), max_length=SHORT_NAME_MAX)
    _text(errors, "street", flat.get("street"), required=not partial, min_length=1,
          max_length=STREET_MAX)
    _text(errors, "house_number", flat.get("house_number"), max_length=HOUSE_NUMBER_MAX)
    _text(errors, "address_addition", flat.get("address_addition"),
          max_length=ADDRESS_ADDITION_MAX)
    _text(errors, "postal_code", flat.get("postal_code"), max_length=POSTAL_CODE_MAX)
    _text(errors, "city", flat.get("city"), required=not partial, min_length=1,
          max_length=CITY_MAX)
    region = flat.get("region")
    if region not in (None, "") and not (isinstance(region, str) and REGION_PATTERN.match(region)):
        errors.append(_error("region", "format"))
    errors += validate_country_code(flat.get("country_code"), required=not partial)
    if flat.get("bpn") not in (None, ""):
        bpn = flat["bpn"]
        if not isinstance(bpn, str) or not BPN_PATTERN.match(bpn.upper()):
            errors.append(_error("bpn", "format"))
    if flat.get("status") not in (None, ""):
        if flat["status"] not in STATUSES:
            errors.append(_error("status", "unknown"))
    if flat.get("deactivation_reason") not in (None, ""):
        if flat["deactivation_reason"] not in DEACTIVATION_REASONS:
            errors.append(_error("deactivation_reason", "unknown"))
    if flat.get("core_data_source") not in (None, ""):
        if flat["core_data_source"] not in CORE_DATA_SOURCES:
            errors.append(_error("core_data_source", "unknown"))
    return errors


def validate_country_code(country_code, *, required: bool = True) -> list[dict]:
    if country_code in (None, ""):
        return [_error("country_code", "required")] if required else []
    if not isinstance(country_code, str) or not COUNTRY_PATTERN.match(country_code):
        return [_error("country_code", "format")]
    countries = known_countries()
    if countries is not None and country_code not in countries:
        return [_error("country_code", "unknown-country")]
    return []


# ------------------------------------------------------------------------------- identifiers (6.4)
def validate_identifier(entry: dict, country_code: str | None, field: str) -> list[dict]:
    if not isinstance(entry, dict):
        return [_error(field, "type")]
    errors: list[dict] = []
    kind, value = entry.get("type"), entry.get("value")
    if kind in (None, ""):
        errors.append(_error(f"{field}.type", "required"))
    elif kind not in IDENTIFIER_TYPES:
        errors.append(_error(f"{field}.type", "unknown"))
    if "source" in entry and entry["source"] not in IDENTIFIER_SOURCES:
        errors.append(_error(f"{field}.source", "unknown"))
    if value in (None, ""):
        errors.append(_error(f"{field}.value", "required"))
        return errors
    if not isinstance(value, str):
        errors.append(_error(f"{field}.value", "type"))
        return errors
    if kind in IDENTIFIER_TYPES:
        pattern = pattern_for(kind, country_code)
        if pattern and not _matches(pattern, value):
            errors.append(_error(f"{field}.value", "format"))
    return errors


def _matches(pattern: str, value: str) -> bool:
    try:
        return re.search(pattern, value) is not None
    except re.error:
        return True


def validate_identifiers(identifiers, country_code: str | None,
                         *, allow_business_wallet: bool = True) -> list[dict]:
    """At least one identifier, at most one per type, format per country (6.4)."""
    if identifiers is None:
        return [_error("identifiers", "missing")]
    if not isinstance(identifiers, list):
        return [_error("identifiers", "type")]
    errors: list[dict] = []
    if not identifiers:
        errors.append(_error("identifiers", "missing"))
    seen: set[str] = set()
    for index, entry in enumerate(identifiers):
        field = f"identifiers[{index}]"
        errors += validate_identifier(entry, country_code, field)
        if isinstance(entry, dict):
            kind = entry.get("type")
            if kind:
                if kind in seen:
                    errors.append(_error(f"{field}.type", "duplicate-type"))
                seen.add(kind)
            if not allow_business_wallet and entry.get("source") == "BUSINESS_WALLET":
                errors.append(_error(f"{field}.source", "business-wallet-source"))
    return errors


# ------------------------------------------------------------------ change request, docs (7.4)
def validate_change_request(data: dict, country_code: str | None) -> list[dict]:
    """7.4: at least one change, comment 1..1000, identifiers complete with source `DECLARED`."""
    flat = flat_fields(data)
    errors: list[dict] = []
    has_name = flat.get("name") not in (None, "")
    has_address = any(flat.get(field) not in (None, "") for field in ADDRESS_FIELDS)
    if has_address:
        for required in ("street", "city"):
            if flat.get(required) in (None, ""):
                errors.append(_error(required, "required"))
    has_identifiers = flat.get("identifiers") is not None
    if not (has_name or has_address or has_identifiers):
        errors.append(_error("changes", "missing"))
    if has_name or has_address:
        errors += validate_company(flat, partial=True)
    if has_identifiers:
        errors += validate_identifiers(flat["identifiers"], country_code,
                                       allow_business_wallet=False)
    errors += validate_comment(flat.get("comment"))
    return errors


def validate_comment(comment) -> list[dict]:
    errors: list[dict] = []
    _text(errors, "comment", comment, required=True, min_length=1, max_length=COMMENT_MAX)
    return errors


def validate_reason(reason, *, max_length: int = REASON_MAX) -> list[dict]:
    """Justification 1..500, for decisions 1..1000 (7.13, 7.18)."""
    errors: list[dict] = []
    _text(errors, "reason", reason, required=True, min_length=1, max_length=max_length)
    return errors


def validate_decision_reason(reason) -> list[dict]:
    return validate_reason(reason, max_length=DECISION_REASON_MAX)


# --------------------------------------------------------------------------- documents (5, 7.4)
def validate_file_name(file_name) -> list[dict]:
    errors: list[dict] = []
    _text(errors, "file_name", file_name, required=True, min_length=1, max_length=FILE_NAME_MAX)
    if isinstance(file_name, str) and ("/" in file_name or "\\" in file_name):
        errors.append(_error("file_name", "path-parts"))
    return errors


def detect_media_type(content) -> str | None:
    """Media type from the first bytes, `None` for anything else (README 4, 5)."""
    if not isinstance(content, (bytes, bytearray)):
        return None
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def validate_document(file_name, content, *, stated_media_type: str | None = None,
                      max_bytes: int | None = None) -> list[dict]:
    """File name rules and type from the bytes; `stated_media_type` is ignored on purpose."""
    del stated_media_type
    errors = validate_file_name(file_name)
    if content in (None, b""):
        errors.append(_error("document", "required"))
        return errors
    if not isinstance(content, (bytes, bytearray)):
        errors.append(_error("document", "type"))
        return errors
    if max_bytes is not None and len(content) > max_bytes:
        errors.append(_error("document", "too-large"))
    if detect_media_type(content) is None:
        errors.append(_error("document", "media-type"))
    return errors


# --------------------------------------------------------------------------------- misc (6.5)
def validate_company_role(company_role, catalogue: dict | None = None) -> list[dict]:
    """Role must be in the catalogue (7.8, 7.9)."""
    if not company_role:
        return [_error("companyRole", "required")]
    if catalogue is not None and company_role not in catalogue:
        return [_error("companyRole", "unknown")]
    return []


def validate_media_type(media_type) -> list[dict]:
    if media_type not in MEDIA_TYPES:
        return [_error("media_type", "unknown")]
    return []


def validate_bpn(bpn) -> list[dict]:
    if not isinstance(bpn, str) or not BPN_PATTERN.match(bpn.upper()):
        return [_error("bpn", "format")]
    return []
