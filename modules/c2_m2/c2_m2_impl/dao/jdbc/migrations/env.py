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
"""Alembic environment of the database c2_m2: the connection of `PostgresDatabase.migrate`, or DATABASE_URL (CLI)."""
from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool

from modules.c2_m2.c2_m2_impl.impl.postgres_database import VERSION_TABLE, sqlalchemy_url

MIGRATION_LOCK = "SELECT pg_advisory_xact_lock(hashtextextended('c2_m2:migrations', 0))"


def _url():
    return sqlalchemy_url(os.environ.get("DATABASE_URL") or "")


def run_offline() -> None:
    context.configure(url=_url(), literal_binds=True, version_table=VERSION_TABLE)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    # one transaction for all pending migrations; the lock keeps replicas that start at once apart
    connection.exec_driver_sql(MIGRATION_LOCK)
    context.configure(connection=connection, version_table=VERSION_TABLE)
    with context.begin_transaction():
        context.run_migrations()
    connection.commit()


def run_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    with create_engine(_url(), poolclass=pool.NullPool).connect() as connection:
        _run(connection)


if context.is_offline_mode():
    run_offline()
else:
    run_online()
