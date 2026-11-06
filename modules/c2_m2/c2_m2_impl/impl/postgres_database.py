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
#  Assisted-By: GitHub Copilot (claude-opus-5-5)
#################################################################################
from __future__ import annotations

import contextlib
import contextvars
from collections.abc import Iterator, Sequence
from pathlib import Path

from modules.c2_m2.c2_m2_api.exception import C2M2BaseException
from modules.c2_m2.c2_m2_impl.internal.services import Database
from portal_common.problems import Problem

VERSION_TABLE = "alembic_version_c2_m2"


def sqlalchemy_url(url: str):
    """`postgresql://…` of DATABASE_URL as SQLAlchemy URL with the pg8000 driver."""
    from sqlalchemy.engine import make_url
    parsed = make_url(url)
    if parsed.get_backend_name() not in ("postgresql", "postgres"):
        raise ValueError("DATABASE_URL must start with postgresql://")
    return parsed.set(drivername="postgresql+pg8000", database=parsed.database or "c2_m2")


class PostgresDatabase(Database):
    """The module's own database `c2_m2` (README 4, `DATABASE_URL`): SQLAlchemy sessions over pg8000, schema
    versions by Alembic. The URL is never logged because it carries the password."""

    def __init__(self, url: str) -> None:
        from sqlalchemy import create_engine   # only needed when DATABASE_URL is set
        from sqlalchemy.orm import sessionmaker
        self.engine = create_engine(sqlalchemy_url(url), pool_pre_ping=True)
        self._sessions = sessionmaker(self.engine)
        self._current = contextvars.ContextVar(f"c2_m2_session_{id(self)}", default=None)

    @contextlib.contextmanager
    def transaction(self) -> Iterator[None]:
        """One transaction for everything inside; nested calls join it. Domain errors (Problem Details) commit
        what was saved before them, as the README expects (for example failed name checks); other errors roll back."""
        if self._current.get() is not None:
            yield
            return
        with self._sessions() as session:
            token = self._current.set(session)
            try:
                yield
            except (C2M2BaseException, Problem):
                session.commit()
                raise
            except BaseException:
                session.rollback()
                raise
            else:
                session.commit()
            finally:
                self._current.reset(token)

    def query(self, sql: str, params: Sequence = ()) -> list[dict]:
        with self.transaction():
            result = self._current.get().connection().exec_driver_sql(sql, tuple(params) or None)
            return [dict(row) for row in result.mappings()] if result.returns_rows else []

    @contextlib.contextmanager
    def lock(self, name: str) -> Iterator[None]:
        with self.transaction():
            self.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (name,))
            yield

    def execute(self, sql: str, params: Sequence = ()) -> None:
        self.query(sql, params)

    def upsert(self, table: str, key: str, columns: Sequence[str], params: Sequence,
               casts: dict[str, str] | None = None) -> None:
        """INSERT … ON CONFLICT (key) DO UPDATE with every other column."""
        casts = casts or {}
        values = ", ".join(f"%s::{casts[c]}" if c in casts else "%s" for c in columns)
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != key)
        self.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({values}) "
                     f"ON CONFLICT ({key}) DO UPDATE SET {updates}", params)

    def migrate(self, location: Path) -> None:
        from alembic import command
        from alembic.config import Config as AlembicConfig
        config = AlembicConfig()
        config.set_main_option("script_location", str(location))
        with self.engine.connect() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
