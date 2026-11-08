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
"""Error factories of C4-M2: one per error type of README section 12 that the module raises (ADR-0003).

Every factory sets `retryable` (README 12, FRAMEWORK 4.4): `false` unless the error is temporary
(`upstream-error`), as the module's former `_problem` helpers did. `errors.py` is the only file of the
module that builds a `Problem`.
"""
from __future__ import annotations

from portal_common.problems import Problem

MODULE = "c4-m2"


def _problem(status: int, name: str, detail: str | None, retryable: bool) -> Problem:
    return Problem(MODULE, status, name, detail=detail, retryable=retryable)


def validation(detail: str | None = None) -> Problem:
    """400: input invalid."""
    return _problem(400, "validation", detail, False)


def provider_not_enabled(detail: str | None = None) -> Problem:
    """400: provider not in `ENABLED_PROVIDERS`."""
    return _problem(400, "provider-not-enabled", detail, False)


def forbidden(detail: str | None = None) -> Problem:
    """403: wrong client on a callback (the permission itself is checked by the router); no `retryable`."""
    return Problem(MODULE, 403, "forbidden", detail=detail)


def not_found(detail: str | None = None) -> Problem:
    """404: wallet or wallet account does not exist or is not visible."""
    return _problem(404, "not-found", detail, False)


def invalid_state(detail: str | None = None) -> Problem:
    """409: the status does not allow the operation."""
    return _problem(409, "invalid-state", detail, False)


def conflict(detail: str | None = None) -> Problem:
    """409: contradictory data (other BPN, other DID, other company)."""
    return _problem(409, "conflict", detail, False)


def company_not_ready(detail: str | None = None) -> Problem:
    """409: company at C3-M1 without BPN."""
    return _problem(409, "company-not-ready", detail, False)


def company_not_active(detail: str | None = None) -> Problem:
    """409: company at C3-M1 not `ACTIVE`; no new wallet account."""
    return _problem(409, "company-not-active", detail, False)


def wallet_not_active(detail: str | None = None) -> Problem:
    """409: wallet of the company not `ACTIVE`."""
    return _problem(409, "wallet-not-active", detail, False)


def provider_rejected(detail: str | None = None) -> Problem:
    """409: the provider rejects on business grounds."""
    return _problem(409, "provider-rejected", detail, False)


def no_credentials(detail: str | None = None) -> Problem:
    """409: wallet account has no retrievable credentials."""
    return _problem(409, "no-credentials", detail, False)


def already_retrieved(detail: str | None = None) -> Problem:
    """410: credentials already retrieved."""
    return _problem(410, "already-retrieved", detail, False)


def credentials_expired(detail: str | None = None) -> Problem:
    """410: credentials deleted after the deadline."""
    return _problem(410, "credentials-expired", detail, False)


def upstream_error(detail: str | None = None) -> Problem:
    """502, retryable: the provider did not accept an order or is not reachable."""
    return _problem(502, "upstream-error", detail, True)
