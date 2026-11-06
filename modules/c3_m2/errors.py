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
"""Module id and the error types of C3-M2 (README 12) as `Problem` factories."""
from __future__ import annotations

from portal_common.problems import Problem

MODULE = "c3-m2"


def validation(detail: str) -> Problem:
    """400: invalid input."""
    return Problem(MODULE, 400, "validation", detail=detail, retryable=False)


def not_found(detail: str = "company without registration") -> Problem:
    """404: no registration for the company (GET /companies/{companyId})."""
    return Problem(MODULE, 404, "not-found", detail=detail)


def unknown_company(detail: str) -> Problem:
    """404: a notification of the CSP for an unknown BPN or operation."""
    return Problem(MODULE, 404, "unknown-company", detail=detail)


def invalid_state(detail: str) -> Problem:
    """409: a precondition of a step is missing, for example the company is not REGISTERED."""
    return Problem(MODULE, 409, "invalid-state", detail=detail, retryable=False)


def registered_at_other_osp(home_osp_id: str | None) -> Problem:
    """409: the CSP reports another home OSP; final for the step."""
    ext = {"homeOspId": home_osp_id} if home_osp_id else {}
    return Problem(MODULE, 409, "registered-at-other-osp",
                   detail="the CSP reports another home OSP for this company", retryable=False, **ext)


def upstream_error(detail: str) -> Problem:
    """502, retryable: the CSP is not reachable or answered 5xx; C12 tries the step again."""
    return Problem(MODULE, 502, "upstream-error", detail=detail, retryable=True)


def csp_rejected(detail: str, csp_type: str | None) -> Problem:
    """502, not retryable: the CSP rejects for business reasons; `cspType` keeps the CSP's own error type."""
    ext = {"cspType": csp_type} if csp_type else {}
    return Problem(MODULE, 502, "csp-rejected", detail=detail, retryable=False, **ext)
