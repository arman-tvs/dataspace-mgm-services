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
from __future__ import annotations

DESCRIPTION_PREFIX = "description."


class AppRoleRepresentation:
    """An app role as the Portal IAM keeps it: descriptions as attributes `description.{lang}` (6.2)."""

    @staticmethod
    def build(name: str, descriptions: list[dict], existing: dict | None = None) -> dict:
        english = next((d["text"] for d in descriptions if d["lang"] == "en"), descriptions[0]["text"])
        other = {k: v for k, v in ((existing or {}).get("attributes") or {}).items()
                 if not k.startswith(DESCRIPTION_PREFIX)}
        attrs = other | {f"{DESCRIPTION_PREFIX}{d['lang']}": [d["text"]] for d in descriptions}
        return (existing or {}) | {"name": name, "description": english, "attributes": attrs}

    @staticmethod
    def descriptions(role: dict) -> list[dict]:
        attrs = role.get("attributes") or {}
        return [{"lang": k.removeprefix(DESCRIPTION_PREFIX), "text": v[0]}
                for k, v in sorted(attrs.items()) if k.startswith(DESCRIPTION_PREFIX) and v]

    @classmethod
    def same(cls, role: dict, wanted: dict) -> bool:
        return role.get("description") == wanted["description"] and \
            cls.descriptions(role) == cls.descriptions(wanted)

    @classmethod
    def to_api(cls, role: dict, lang: str) -> dict:
        """`description` in `lang`, otherwise English, otherwise the first one (9.1)."""
        ds = cls.descriptions(role)
        text = next((d["text"] for d in ds if d["lang"] == lang), None) or \
            next((d["text"] for d in ds if d["lang"] == "en"), None) or (ds[0]["text"] if ds else None)
        return {"name": role["name"], "description": text, "descriptions": ds}
