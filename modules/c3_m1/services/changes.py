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
"""Helpers shared by the changes of core data (README 7.2, 7.3, 7.4 - 7.6, 7.12, 8.6): which fields differ,
how a merge is validated, which identifiers the wallet owns."""
from __future__ import annotations

from modules.c3_m1 import store, validation
from modules.c3_m1.errors import FieldError


def _validate_merge(row: dict, body: dict) -> dict:
    """The row after the body, flat, so the merged state is validated, not only the patch."""
    merged = {field: row.get(field) for field in row}
    merged.update(validation.flat_fields(body))
    return merged


def _changed_fields(row: dict, body: dict, identifiers: list[dict] | None) -> list[str]:
    """Names of the fields the body really changes, camelCase, for the event (README 7.2, 7.12)."""
    changed = []
    for key, value in body.items():
        field = validation.field_name(key)
        if field in CORE_TEXT_FIELDS or field == "short_name":
            before, after = row.get(field), value
            if (before or "") != (after or "") and not (
                    before and after and validation.same_value(before, after)):
                changed.append(CAMEL.get(field, field))
    if identifiers is not None:
        before = {(entry["type"], entry["value_normalized"]) for entry in store.list_identifiers(row["id"])}
        after = {(entry["type"], validation.value_normalized(entry["value"])) for entry in identifiers}
        if before != after:
            changed.append("identifiers")
    return changed


CAMEL = {snake: camel for camel, snake in validation.ALIASES.items()}


CORE_TEXT_FIELDS = ("name", "street", "house_number", "address_addition", "postal_code", "city",
                    "region", "country_code")


def _identifier_core_changed(row: dict, identifiers: list[dict]) -> bool:
    """A changed, added or dropped declared EUID/EBWOID is a change of core data (6.3).

    A wallet identifier that stays outside the request list is not a change.
    """
    stored = {entry["type"]: entry["value"] for entry in store.list_identifiers(row["id"])
              if entry["type"] in CORE_IDENTIFIERS and entry["source"] != "BUSINESS_WALLET"}
    now = {entry["type"]: entry["value"] for entry in identifiers
           if entry.get("type") in CORE_IDENTIFIERS}
    if set(stored) != set(now):
        return True
    return any(not validation.same_value(stored[kind], value) for kind, value in now.items())


def _wallet_identifier_conflict(row: dict, identifiers: list[dict]) -> list[FieldError]:
    """Identifiers of the list whose stored source is `BUSINESS_WALLET` (400, 7.4 point 4, 7.12 point 3)."""
    stored = {entry["type"] for entry in store.list_identifiers(row["id"])
              if entry["source"] == "BUSINESS_WALLET"}
    return [{"field": f"identifiers.{entry.get('type')}", "reason": "source BUSINESS_WALLET"}
            for entry in identifiers if entry.get("type") in stored]


CORE_IDENTIFIERS = ("EUID", "EBWOID")
