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
"""The in-memory store of C2-M2 for an installation without a database (README 4, `DATABASE_URL` empty: tests,
`demo.py`, the hackathon installation), as C3-M1's `store_memory`.

Rows are values: every read returns a copy and every save stores one, as a database does. One reentrant lock
serializes the transactions, which covers the locks of 6.14; the outermost transaction is rolled back when it raises.
The sequence `client_number` is not rolled back, as in PostgreSQL.
"""
from __future__ import annotations

import contextlib
import copy
import itertools
import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager


class MemoryStore:
    """The lock, the transactions and the sequence `client_number`; the tables register themselves."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._depth = 0
        self._tables: list[Table] = []
        self._numbers = itertools.count(1)

    def register(self, table: Table) -> None:
        self._tables.append(table)

    @contextlib.contextmanager
    def transaction(self) -> Iterator[None]:
        """One transaction; nested calls join the open one, the outermost rolls back on an exception."""
        with self._lock:
            snapshot = [t.snapshot() for t in self._tables] if self._depth == 0 else None
            self._depth += 1
            try:
                yield
            except BaseException:
                if snapshot is not None:
                    for table, rows in zip(self._tables, snapshot, strict=True):
                        table.restore(rows)
                raise
            finally:
                self._depth -= 1

    def lock(self, _name: str) -> AbstractContextManager[None]:
        """A named lock of 6.14: the transaction lock covers every name, and opens a transaction when none is open."""
        return self.transaction()

    def next_number(self) -> int:
        with self._lock:
            return next(self._numbers)


class Table[T]:
    """One table of README 5 as copies of its rows by primary key."""

    def __init__(self, store: MemoryStore, key: Callable[[T], str]) -> None:
        self.store, self.key = store, key
        self.rows: dict[str, T] = {}
        store.register(self)

    def snapshot(self) -> dict[str, T]:
        return copy.deepcopy(self.rows)

    def restore(self, rows: dict[str, T]) -> None:
        self.rows = rows

    def get(self, key: str) -> T | None:
        with self.store.transaction():
            row = self.rows.get(key)
            return copy.deepcopy(row) if row is not None else None

    def save(self, row: T) -> None:
        with self.store.transaction():
            self.rows[self.key(row)] = copy.deepcopy(row)

    def where(self, keep: Callable[[T], bool]) -> list[T]:
        with self.store.transaction():
            return [copy.deepcopy(row) for row in self.rows.values() if keep(row)]
