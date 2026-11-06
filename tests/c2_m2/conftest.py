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
"""C2-M2 tests that run against the database of `DATABASE_URL` start with empty tables, like the in-memory
data of the other modules. Only the test database is emptied; the schema and its Alembic version stay."""
import os

import pytest

from modules.c2_m2 import module


def _truncate(url: str) -> None:
    from sqlalchemy import create_engine, text

    from modules.c2_m2.c2_m2_impl.impl.postgres_database import VERSION_TABLE, sqlalchemy_url
    engine = create_engine(sqlalchemy_url(url))
    try:
        with engine.begin() as conn:
            tables = [r[0] for r in conn.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() AND tablename <> :v"),
                {"v": VERSION_TABLE})]
            if tables:
                conn.execute(text(f"TRUNCATE {', '.join(f'"{t}"' for t in tables)} RESTART IDENTITY CASCADE"))
            # standalone sequences such as `client_number` (6.1) are not owned by a table
            for (seq,) in conn.execute(text(
                    "SELECT sequencename FROM pg_sequences WHERE schemaname = current_schema()")):
                conn.execute(text(f'ALTER SEQUENCE "{seq}" RESTART'))
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def _empty_c2_m2_database():
    url = os.environ.get("DATABASE_URL")
    if url:
        module.reset()
        _truncate(url)
    yield
