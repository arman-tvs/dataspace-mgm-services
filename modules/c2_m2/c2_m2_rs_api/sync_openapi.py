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
"""Generate the public/private API definitions from the binding C2-M2 specification."""
from __future__ import annotations

import argparse
import copy
from pathlib import Path

import yaml

from portal_common import spec

DIRECTORY = Path(__file__).resolve().parent


def split_contract(source: dict, *, public: bool) -> dict:
    document = copy.deepcopy(source)
    document["info"]["title"] += " - Public API" if public else " - Private API"
    document["info"]["description"] = (
        "Public API for company users, invitations and OSP staff. "
        "Every operation requires a Portal IAM bearer token and its specified permission and scope."
        if public else
        "Private API for module queries and Process Orchestration steps. "
        "HTTP calls require query_c2_m2 or execute_steps_c2_m2. "
        "In-process calls use modules.c2_m2.interface without a token. "
        "Event schemas describe the private CloudEvents contract."
    )
    document["paths"] = {
        path: item for path, item in document["paths"].items()
        if (not path.startswith(("/internal/", "/steps/"))) == public
    }
    tags = {
        tag for item in document["paths"].values()
        for method in spec.METHODS if method in item for tag in item[method].get("tags", [])
    }
    document["tags"] = [tag for tag in document["tags"] if tag["name"] in tags]
    components: dict = {}

    def collect(value) -> None:
        if isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            if "$ref" in value:
                category, name = value["$ref"].removeprefix("#/components/").split("/")
                group = components.setdefault(category, {})
                if name not in group:
                    group[name] = copy.deepcopy(source["components"][category][name])
                    collect(group[name])
            for item in value.values():
                collect(item)

    collect(document["paths"])
    if not public:
        for name in source["components"]["schemas"]:
            if name.startswith("Event"):
                collect({"$ref": f"#/components/schemas/{name}"})
    components["securitySchemes"] = copy.deepcopy(source["components"]["securitySchemes"])
    document["components"] = {
        category: {name: source["components"][category][name] for name in source["components"][category] if name in group}
        for category, group in components.items()
    }
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if either API definition is stale.")
    args = parser.parse_args()
    source = spec.module("c2-m2").document
    header = Path(__file__).read_text(encoding="utf-8").split('"""', 1)[0]
    stale = []
    for public, filename in ((True, "openapi.yaml"), (False, "openapi-private.yaml")):
        path = DIRECTORY / filename
        document = split_contract(source, public=public)
        if args.check:
            if not path.exists() or yaml.safe_load(path.read_text(encoding="utf-8")) != document:
                stale.append(filename)
        else:
            path.write_text(header + yaml.safe_dump(document, sort_keys=False, allow_unicode=False), encoding="utf-8")
    if stale:
        parser.exit(1, f"Stale API definitions: {', '.join(stale)}; run this command without --check.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
