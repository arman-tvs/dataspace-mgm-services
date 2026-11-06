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
#  Assisted-By: Claude Code (claude-sonnet-5-5)
#################################################################################
"""Storage of C4-M1 Credentials (README 5) behind a small interface.

`CredentialStore` is the only thing `service.py` and `interface.py` talk to; `InMemoryStore` is the
implementation of this repository (everything is in memory, see the repo README "Where is the data
stored?"). A PostgreSQL store (README 4, own database `c4_m1`) can be added later without touching the
business logic: rows and keys use the table and column names of README 5 (`credential`,
`credential_history`, `issuance_run`, `audit_entry`), and `transaction(company_id)` is the single place
for the per-company advisory lock of README 6.6.

Rows are plain dicts. Timestamps are timezone-aware `datetime` objects; `dump()` turns them into ISO
strings. Rows returned by the store are copies: a change reaches the store only through a `put_*` call.
"""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import threading
from collections.abc import Iterator
from typing import Any, Protocol


class CredentialStore(Protocol):
    """Contract of the storage of C4-M1 (TEAM3-PLAN 12.3)."""

    def get_credential(self, company_id: str, credential_type: str) -> dict | None: ...

    def get_credential_by_id(self, credential_id: str) -> dict | None: ...

    def find_credential(self, bpn: str, credential_type: str) -> dict | None: ...

    def put_credential(self, row: dict) -> None: ...

    def list_credentials(self, company_id: str | None = None, statuses: list[str] | None = None,
                         credential_type: str | None = None, route: str | None = None,
                         requested_before: dt.datetime | None = None, page: int = 0,
                         size: int = 50) -> list[dict]: ...

    def count_credentials(self, company_id: str | None = None, statuses: list[str] | None = None,
                          credential_type: str | None = None, route: str | None = None,
                          requested_before: dt.datetime | None = None) -> int: ...

    def get_run(self, company_id: str) -> dict | None: ...

    def put_run(self, run: dict) -> None: ...

    def append_history(self, entry: dict) -> None: ...

    def list_history(self, credential_id: str) -> list[dict]: ...

    def append_audit(self, entry: dict) -> None: ...

    def list_audit(self) -> list[dict]: ...

    def transaction(self, company_id: str) -> contextlib.AbstractContextManager[None]: ...

    def dump(self) -> dict: ...

    def reset(self) -> None: ...


def _jsonable(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


class InMemoryStore:
    """`CredentialStore` in process memory."""

    def __init__(self) -> None:
        self._data = threading.Lock()                       # guards the dicts below
        self._lock_table = threading.Lock()                 # guards `_locks`
        self._locks: dict[str, threading.RLock] = {}
        self._credentials: dict[tuple[str, str], dict] = {}  # (company_id, credential_type) -> row
        self._runs: dict[str, dict] = {}
        self._history: list[dict] = []
        self._audit: list[dict] = []

    # --- credential ---------------------------------------------------------------------------
    def get_credential(self, company_id: str, credential_type: str) -> dict | None:
        with self._data:
            return copy.deepcopy(self._credentials.get((company_id, credential_type)))

    def get_credential_by_id(self, credential_id: str) -> dict | None:
        with self._data:
            return copy.deepcopy(next((r for r in self._credentials.values() if r["id"] == credential_id), None))

    def find_credential(self, bpn: str, credential_type: str) -> dict | None:
        """README 5 index (`bpn`, `credential_type`); the BPN is compared in upper case (7.4 step 3)."""
        wanted = (bpn or "").upper()
        with self._data:
            return copy.deepcopy(next((r for r in self._credentials.values()
                                       if r["bpn"] == wanted and r["credential_type"] == credential_type), None))

    def put_credential(self, row: dict) -> None:
        """One row per (`company_id`, `credential_type`): a put replaces the row of the key. The BPN is stored
        in upper case (README 5)."""
        stored = copy.deepcopy(row)
        if stored.get("bpn"):
            stored["bpn"] = stored["bpn"].upper()
        with self._data:
            self._credentials[(stored["company_id"], stored["credential_type"])] = stored

    def _matching(self, company_id, statuses, credential_type, route, requested_before) -> list[dict]:
        out = []
        for r in self._credentials.values():
            if company_id and r["company_id"] != company_id:
                continue
            if statuses and r["status"] not in statuses:
                continue
            if credential_type and r["credential_type"] != credential_type:
                continue
            if route and r.get("route") != route:
                continue
            if requested_before is not None and not (r.get("requested_at") and r["requested_at"] < requested_before):
                continue
            out.append(r)
        out.sort(key=lambda r: r["changed_at"], reverse=True)   # README 7.2: `changedAt` descending
        return out

    def list_credentials(self, company_id: str | None = None, statuses: list[str] | None = None,
                         credential_type: str | None = None, route: str | None = None,
                         requested_before: dt.datetime | None = None, page: int = 0,
                         size: int = 50) -> list[dict]:
        with self._data:
            rows = self._matching(company_id, statuses, credential_type, route, requested_before)
            return copy.deepcopy(rows[page * size:(page + 1) * size])

    def count_credentials(self, company_id: str | None = None, statuses: list[str] | None = None,
                          credential_type: str | None = None, route: str | None = None,
                          requested_before: dt.datetime | None = None) -> int:
        with self._data:
            return len(self._matching(company_id, statuses, credential_type, route, requested_before))

    # --- issuance_run -------------------------------------------------------------------------
    def get_run(self, company_id: str) -> dict | None:
        with self._data:
            return copy.deepcopy(self._runs.get(company_id))

    def put_run(self, run: dict) -> None:
        with self._data:
            self._runs[run["company_id"]] = copy.deepcopy(run)

    # --- credential_history, audit_entry ------------------------------------------------------
    def append_history(self, entry: dict) -> None:
        with self._data:
            self._history.append(copy.deepcopy(entry))

    def list_history(self, credential_id: str) -> list[dict]:
        with self._data:
            return copy.deepcopy([e for e in self._history if e["credential_id"] == credential_id])

    def append_audit(self, entry: dict) -> None:
        with self._data:
            self._audit.append(copy.deepcopy(entry))

    def list_audit(self) -> list[dict]:
        with self._data:
            return copy.deepcopy(self._audit)

    # --- transaction --------------------------------------------------------------------------
    @contextlib.contextmanager
    def transaction(self, company_id: str) -> Iterator[None]:
        """Steps and status reports of one company run one after the other (README 6.6, stands in for the
        PostgreSQL advisory lock). Re-entrant, so that a step may call the code path of a status report."""
        with self._lock_table:
            lock = self._locks.setdefault(company_id, threading.RLock())
        with lock:
            yield

    # --- test support -------------------------------------------------------------------------
    def dump(self) -> dict:
        """The whole state as JSON-serialisable data (for secret scans in tests)."""
        with self._data:
            return _jsonable({"credential": list(self._credentials.values()), "issuance_run": list(self._runs.values()),
                              "credential_history": self._history, "audit_entry": self._audit})

    def reset(self) -> None:
        """Empties all tables. The locks stay, so that a transaction that is still open stays valid."""
        with self._data:
            self._credentials.clear()
            self._runs.clear()
            self._history.clear()
            self._audit.clear()
