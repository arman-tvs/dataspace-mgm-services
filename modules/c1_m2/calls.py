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
"""Calls of C1-M2 to its neighbours (README 11) with the built-in stand-ins.

Address per FRAMEWORK 4.7 through `portal_common.neighbours`: `in-process` or a URL calls the neighbour, an
empty address answers from `STUB_COMPANIES_FILE` and `STUB_REVIEWS_FILE` (README 14.5). The files are read on
every call; the JSON string "unavailable" instead of a list means "not reachable" (502 `upstream-error`).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from portal_common import neighbours
from portal_common.problems import Problem

MODULE = "c1-m2"
C3_M1, C1_M3 = "c3-m1", "c1-m3"


def _stub(var: str, target: str) -> list[dict]:
    path = os.environ.get(var, "")
    if not path:
        raise Problem(MODULE, 502, "upstream-error", detail=f"{target} stand-in: {var} not set", retryable=True)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise Problem(MODULE, 502, "upstream-error", detail=f"{target} not reachable", retryable=True)
    return data


def company_by_id(company_id: str) -> dict | None:
    """`CompanyInternal` (C3-M1 9.1), None if unknown."""
    if not neighbours.is_standin(C3_M1):
        return neighbours.query(MODULE, C3_M1, "query_company", companyId=company_id)
    return next((c for c in _stub("STUB_COMPANIES_FILE", C3_M1) if c.get("id") == company_id), None)


def company_by_bpn(bpn: str) -> dict | None:
    """`CompanyInternal` with this BPN (C3-M1 9.2), None if unknown."""
    if not neighbours.is_standin(C3_M1):
        found = neighbours.query(MODULE, C3_M1, "query_companies", bpn=[bpn]) or {}
        return next(iter(found.get("items", [])), None)
    return next((c for c in _stub("STUB_COMPANIES_FILE", C3_M1) if c.get("bpn") == bpn), None)


def review_status(application_id: str) -> str | None:
    """Status of the review case of the application in C1-M3, None if there is none."""
    if not neighbours.is_standin(C1_M3):
        found = neighbours.query(MODULE, C1_M3, "get_review_status_by_application", applicationId=application_id)
        return (found or {}).get("status")
    entry = next((r for r in _stub("STUB_REVIEWS_FILE", C1_M3) if r.get("applicationId") == application_id), None)
    return (entry or {}).get("status")
