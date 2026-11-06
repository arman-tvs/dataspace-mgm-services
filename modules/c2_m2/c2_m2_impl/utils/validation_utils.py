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
#  Assisted-By: GitHub Copilot (claude-opus-5-5)
#################################################################################
"""Input checks of C2-M2; every failure is 400 `validation` (README section 12)."""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

from modules.c2_m2.c2_m2_api.exception import ValidationException

UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
BPN = re.compile(r"^BPNL[0-9A-Z]{12}$")
LANG = re.compile(r"^[a-z]{2}$")


def invalid(detail: str) -> ValidationException:
    return ValidationException(detail)


class Validator:
    """Checks of README sections 5, 6.2, 6.8 and 7 against the configuration."""

    def __init__(self, languages: tuple[str, ...]) -> None:
        self.languages = languages

    @staticmethod
    def uuid(data: dict, key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not UUID.match(value):
            raise invalid(f"{key}: UUID expected")
        return value

    @staticmethod
    def optional_uuid(data: dict, key: str) -> str | None:
        return None if data.get(key) is None else Validator.uuid(data, key)

    @staticmethod
    def text(data: dict, key: str, max_len: int = 255) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not 1 <= len(value) <= max_len:
            raise invalid(f"{key}: 1 to {max_len} characters")
        return value

    @staticmethod
    def person_name(data: dict, key: str) -> str:
        value = Validator.text(data, key)
        if any(unicodedata.category(c) == "Cc" for c in value):
            raise invalid(f"{key}: control characters are not allowed")
        return value

    @staticmethod
    def bpn(data: dict, key: str = "bpn") -> str:
        value = data.get(key)
        if not isinstance(value, str) or not BPN.match(value):
            raise invalid(f"{key}: {BPN.pattern} expected")
        return value

    @staticmethod
    def instance_url(data: dict, key: str = "instanceUrl") -> str:
        value = data.get(key)
        if not isinstance(value, str) or len(value) > 255 or "#" in value:
            raise invalid(f"{key}: absolute http or https URL without '#', up to 255 characters")
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise invalid(f"{key}: absolute http or https URL expected")
        return value

    @staticmethod
    def role_list(data: dict, key: str, allowed: tuple[str, ...], allow_empty: bool = False) -> list[str]:
        value = data.get(key)
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise invalid(f"{key}: list of role names expected")
        if not value and not allow_empty:
            raise invalid(f"{key}: at least one role")
        if len(set(value)) != len(value):
            raise invalid(f"{key}: duplicate roles")
        unknown = sorted(set(value) - set(allowed)) if allowed else []
        if unknown:
            raise invalid(f"{key}: unknown roles {unknown}")
        return list(value)

    def role_inputs(self, data: dict, key: str = "roles") -> list[dict]:
        """`RoleInput` list (6.2): unique names, at least one description, one per allowed language."""
        roles = data.get(key)
        if not isinstance(roles, list) or not roles:
            raise invalid(f"{key}: at least one role")
        names: set[str] = set()
        out = []
        for i, role in enumerate(roles):
            if not isinstance(role, dict):
                raise invalid(f"{key}[{i}]: object expected")
            name = self.text(role, "name")
            if name in names:
                raise invalid(f"{key}: role {name!r} given twice")
            names.add(name)
            out.append({"name": name, "descriptions": self.descriptions(role.get("descriptions"), f"{key}[{i}]")})
        return out

    def descriptions(self, value: object, where: str) -> list[dict]:
        if not isinstance(value, list) or not value:
            raise invalid(f"{where}.descriptions: at least one description")
        langs: set[str] = set()
        out = []
        for d in value:
            if not isinstance(d, dict):
                raise invalid(f"{where}.descriptions: object expected")
            lang, text = d.get("lang"), d.get("text")
            if not isinstance(lang, str) or lang not in self.languages:
                raise invalid(f"{where}.descriptions: language one of {list(self.languages)}")
            if lang in langs:
                raise invalid(f"{where}.descriptions: language {lang} given twice")
            if not isinstance(text, str) or not 1 <= len(text) <= 255:
                raise invalid(f"{where}.descriptions: text 1 to 255 characters")
            langs.add(lang)
            out.append({"lang": lang, "text": text})
        return out

    @staticmethod
    def lang(value: str | None) -> str:
        value = value or "en"
        if not LANG.match(value):
            raise invalid("lang: two lower-case letters")
        return value
