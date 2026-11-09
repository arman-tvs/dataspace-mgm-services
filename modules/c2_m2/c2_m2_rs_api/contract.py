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
#  Assisted-By: GitHub Copilot
#################################################################################
"""Access to the public and private API definitions (`openapi.yaml`, `openapi-private.yaml`)."""
from __future__ import annotations

from pathlib import Path

import yaml

from portal_common import spec

DIRECTORY = Path(__file__).resolve().parent


def load_contract(*, public: bool) -> dict:
    filename = "openapi.yaml" if public else "openapi-private.yaml"
    return yaml.safe_load((DIRECTORY / filename).read_text(encoding="utf-8"))


def operations(document: dict) -> dict[tuple[str, str], dict]:
    """Operations of a contract keyed by (METHOD, path)."""
    return {
        (method.upper(), path): item[method]
        for path, item in document["paths"].items()
        for method in spec.METHODS if method in item
    }


type Json = str | int | float | bool | None | list[Json] | dict[str, Json]


def resolve(value: Json, document: dict[str, Json]) -> Json:
    """Inline local references so the installation's generated OpenAPI needs no module components."""
    if isinstance(value, list):
        return [resolve(item, document) for item in value]
    if not isinstance(value, dict):
        return value
    if "$ref" in value:
        reference = value["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/"):
            raise ValueError(f"Only local contract references are supported: {reference}")
        target: Json = document
        for part in reference[2:].split("/"):
            if not isinstance(target, dict):
                raise ValueError(f"Contract reference does not point to an object: {reference}")
            target = target[part.replace("~1", "/").replace("~0", "~")]
        if not isinstance(target, dict):
            raise ValueError(f"Contract reference does not point to an object: {reference}")
        return resolve(target | {k: v for k, v in value.items() if k != "$ref"}, document)
    return {key: resolve(item, document) for key, item in value.items()}


def resolve_object(value: Json, document: dict[str, Json]) -> dict[str, Json]:
    """`resolve` for a value that must be an object (an operation, a response)."""
    resolved = resolve(value, document)
    if not isinstance(resolved, dict):
        raise ValueError("Contract value is not an object")
    return resolved
