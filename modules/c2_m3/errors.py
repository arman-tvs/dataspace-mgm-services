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
"""Error types of C2-M3 (README section 12); the only file that builds a `Problem` (ADR-0003).

Every factory sets `retryable` as README 12 defines it for steps; C2-M3 also sends it on the answers of people's
operations, as before. `iam-error` is retryable except when the Portal IAM refused the request itself.
"""
from __future__ import annotations

from portal_common.problems import Problem

MODULE = "c2-m3"


def validation(detail: str) -> Problem:
    """400: invalid input."""
    return Problem(MODULE, 400, "validation", detail=detail, retryable=False)


def role_not_assignable(detail: str) -> Problem:
    """400: role not assignable or unknown."""
    return Problem(MODULE, 400, "role-not-assignable", detail=detail, retryable=False)


def not_owner() -> Problem:
    """403: a co-viewing company tries to change the account or rotate the secret."""
    return Problem(MODULE, 403, "not-owner", retryable=False)


def not_found() -> Problem:
    """404: the account does not exist or is not visible, or the path names another company."""
    return Problem(MODULE, 404, "not-found", retryable=False)


def company_not_ready() -> Problem:
    """409: the company is not `ACTIVE` or has no BPN."""
    return Problem(MODULE, 409, "company-not-ready", retryable=False)


def invalid_state() -> Problem:
    """409: status or deactivation does not allow the operation or the step."""
    return Problem(MODULE, 409, "invalid-state", retryable=False)


def wallet_in_progress() -> Problem:
    """409: wallet access is still being created."""
    return Problem(MODULE, 409, "wallet-in-progress", retryable=False)


def wallet_role_change() -> Problem:
    """409: adding or removing a wallet role through a change."""
    return Problem(MODULE, 409, "wallet-role-change", retryable=False)


def in_use() -> Problem:
    """409: a connector uses the account, or the subscription is active."""
    return Problem(MODULE, 409, "in-use", retryable=False)


def iam_error(detail: str, *, retryable: bool = True) -> Problem:
    """502: the Portal IAM did not respond as expected; not retryable when it refused the request itself."""
    return Problem(MODULE, 502, "iam-error", detail=detail, retryable=retryable)


def upstream_error(detail: str | None = None) -> Problem:
    """502: a neighbouring module (or a file of README 4) did not respond as expected."""
    return Problem(MODULE, 502, "upstream-error", detail=detail, retryable=True)
