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
"""Own data of C3-M2 (README 5), in memory for the hackathon.

One dataclass per table (`csp_registration`, `csp_connector`, `csp_notification`, `audit_entry`),
with the column names of README 5. `interface.registration_view` maps a registration to the
camelCase of the API. Nothing here holds company data beyond the BPN, and the audit log holds no
response content and no tokens (README 5).

Concurrency: steps run in the worker thread of C12, HTTP requests (the CSP's callbacks) in FastAPI's
thread pool. `lock` serialises every check-then-change of the tables together with the event it
publishes, so a repeated step racing a callback changes a row once and publishes once (FRAMEWORK
4.4). Calls to the CSP are made outside the lock; two concurrent calls of the same step may both
call the CSP (its calls are idempotent), but only the first changes the row and publishes. A
database with transactions (README 4 `DATABASE_URL`, OPEN-QUESTIONS 13) replaces this module after
the hackathon. The audit list is capped at `AUDIT_MAX` entries (oldest dropped) until it moves to
the table `audit_entry`.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
from dataclasses import dataclass, field
from typing import Literal

from portal_common import settings

RegistrationStatus = Literal["PENDING", "REGISTERED", "FAILED", "TRANSFERRED_AWAY"]   # README 6.1
Membership = Literal["NONE", "REGISTERED", "DEREGISTERED"]
ConnectorStatus = Literal["REGISTERED", "DEREGISTERED"]
NotificationType = Literal["OperationCompleted", "CompanyTransferredAway"]


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(slots=True)
class Registration:
    """Row of `csp_registration`: one company of the installation at the CSP."""
    company_id: str
    bpn: str | None = None
    status: RegistrationStatus | None = None    # None: row exists, but the CSP has not answered yet
    failure_reason: str | None = None
    pending_operation_id: str | None = None
    did: str | None = None
    membership: Membership = "NONE"
    registered_at: str | None = None
    updated_at: str = field(default_factory=now)
    last_update_step_run: str | None = None     # repetition of update-company (OPEN-QUESTIONS 5)
    returning: bool = False                     # a transfer-company back from TRANSFERRED_AWAY is running


    def touch(self) -> None:
        self.updated_at = now()


@dataclass(slots=True)
class Connector:
    """Row of `csp_connector`: one connector entered in the discovery of the CSP."""
    connector_id: str
    company_id: str
    bpn: str
    endpoint_url: str
    status: ConnectorStatus
    registered_at: str
    updated_at: str


@dataclass(slots=True, frozen=True)
class Notification:
    """Row of `csp_notification`: one accepted notification of the CSP."""
    notification_id: str
    type: NotificationType
    bpn: str | None
    received_at: str


@dataclass(slots=True, frozen=True)
class AuditEntry:
    """Row of `audit_entry`: one call to the CSP or one notification. No content, no tokens."""
    time: str
    operation: str
    company_id: str | None
    bpn: str | None
    http_status: int | None
    error_type: str | None


@dataclass(slots=True, frozen=True)
class EarlyCompletion:
    """An `OperationCompleted` that arrived before the 202 answer of its operation was stored
    (OPEN-QUESTIONS 15). Applied as soon as the step stores that operation id."""
    notification_id: str
    operation_id: str
    outcome: Literal["SUCCEEDED", "FAILED"]
    bpn: str | None
    reason: str | None
    received_at: str


EARLY_COMPLETIONS_MAX = 100   # bound, so unknown operation ids from the CSP cannot grow memory without limit
AUDIT_MAX = 10_000            # bound of the in-memory audit list (README 5 `audit_entry`), oldest dropped first

lock = threading.RLock()      # see the module docstring: check-then-change of the tables plus its event

registrations: dict[str, Registration] = {}    # company_id -> row
connectors: dict[str, Connector] = {}          # connector_id -> row
notifications: dict[str, Notification] = {}    # notification_id -> row
audit: list[AuditEntry] = []
early_completions: dict[str, EarlyCompletion] = {}   # operation_id -> notification, oldest first


def reset() -> None:
    with lock:   # a request in flight never sees half-emptied tables
        registrations.clear()
        connectors.clear()
        notifications.clear()
        audit.clear()
        early_completions.clear()
        seed()


def seed() -> None:
    """README 4 "Seed data": the OSP company from `ospCompanyFile` as `REGISTERED`, without a call
    to the CSP and without events. A second run changes nothing."""
    path = settings.resolve_path(settings.get("ospCompanyFile"))
    if path is None or not path.exists():
        return
    company: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(company, dict):
        return
    company_id, bpn = company.get("companyId"), company.get("bpn")
    if not isinstance(company_id, str) or not isinstance(bpn, str) or company_id in registrations:
        return
    stamp = now()
    registrations[company_id] = Registration(company_id, bpn=bpn, status="REGISTERED", membership="REGISTERED",
                                             registered_at=stamp, updated_at=stamp)


def registration_row(company_id: str) -> Registration:
    """The row of the company; created (without status) if there is none yet."""
    row = registrations.get(company_id)
    if row is None:
        row = registrations[company_id] = Registration(company_id)
    return row


def find_by_operation(operation_id: str) -> Registration | None:
    return next((r for r in registrations.values() if r.pending_operation_id == operation_id), None)


def find_by_bpn(bpn: str, *, exclude: str | None = None,
                status: RegistrationStatus | None = None) -> Registration | None:
    """First registration with this BPN, optionally of another company or in one status."""
    return next((r for r in registrations.values()
                 if r.bpn == bpn and r.company_id != exclude and (status is None or r.status == status)), None)


def keep_early_completion(early: EarlyCompletion) -> None:
    """Remember a completion for an operation id that is not known yet; drops the oldest beyond the bound."""
    early_completions.pop(early.operation_id, None)
    early_completions[early.operation_id] = early
    while len(early_completions) > EARLY_COMPLETIONS_MAX:
        early_completions.pop(next(iter(early_completions)))


def record_audit(operation: str, company_id: str | None, bpn: str | None, http_status: int | None,
                 error_type: str | None = None) -> None:
    """One `audit_entry` (README 5): only status and error type, never the body or a token."""
    with lock:
        audit.append(AuditEntry(now(), operation, company_id, bpn, http_status, error_type))
        if len(audit) > AUDIT_MAX:
            del audit[:len(audit) - AUDIT_MAX]
