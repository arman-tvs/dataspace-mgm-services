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

from modules.c2_m2.c2_m2_impl.dao.audit_log_dao import AuditLogDao
from modules.c2_m2.c2_m2_impl.dao.jdbc import AuditLogRowMapper as Mapper
from modules.c2_m2.c2_m2_impl.internal.model import AuditLogEntry
from modules.c2_m2.c2_m2_impl.internal.services import Database


class PostgresAuditLogDao(AuditLogDao):
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, entry: AuditLogEntry) -> None:
        self.db.execute(f"INSERT INTO {Mapper.TABLE} ({', '.join(Mapper.COLUMNS)}) "
                        f"VALUES ({', '.join(['%s'] * len(Mapper.COLUMNS))})", Mapper.to_params(entry))

    def list_all(self) -> list[AuditLogEntry]:
        return [Mapper.to_model(r) for r in self.db.query(f"SELECT * FROM {Mapper.TABLE} ORDER BY occurred_at")]
