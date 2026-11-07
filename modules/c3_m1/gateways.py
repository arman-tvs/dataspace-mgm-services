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
"""Calls of C3-M1 to its neighbour C1-M2 (README 11.1), the only file that uses `portal_common.neighbours`.

Each function handles the built-in stand-in (empty address, FRAMEWORK 4.7) and answers with the field names of C1-M2's
spec. A failed call is an error (`502` from `neighbours.query`), never "not found" (skill 5).
"""
from __future__ import annotations

import json
from typing import Any

from portal_common import neighbours
from tools import testdata

from . import config, errors
from .errors import MODULE


def stub_applications() -> dict[str, dict[str, Any]]:
    """Built-in stand-in for C1-M2 (11.1): `STUB_APPLICATIONS_FILE` in `ApplicationInternal` form."""
    path = config.stub_applications_file()
    if path is None:
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    entries = document.get("applications") if isinstance(document, dict) else document
    return {entry["id"]: entry for entry in entries or []}


def application(application_id: str | None) -> dict[str, Any]:
    """C1-M2 `getApplicationInternal`: the application, or 404 `not-found` when unknown."""
    config.apply_registration_url()
    if neighbours.is_standin("c1-m2"):
        found = stub_applications().get(application_id or "")
    else:
        found = neighbours.query(MODULE, "c1-m2", "get_application_internal", applicationId=application_id)
    if not found:
        raise errors.not_found(detail="application unknown", retryable=False)
    result: dict[str, Any] = found
    return result


def agreements() -> list[dict[str, Any]]:
    """C1-M2 `listAgreementsInternal`: the terms; the stand-in answers with the initial values of 14.3."""
    config.apply_registration_url()
    if neighbours.is_standin("c1-m2"):
        return testdata.agreements()
    answer: list[dict[str, Any]] = neighbours.query(MODULE, "c1-m2", "list_agreements_internal") or []
    return answer
