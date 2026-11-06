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

from modules.c2_m2.c2_m2_api.model.constants import InvitationKind
from modules.c2_m2.c2_m2_impl.dao.invitation_dao import InvitationDao
from modules.c2_m2.c2_m2_impl.dao.jdbc import InvitationRowMapper as Mapper
from modules.c2_m2.c2_m2_impl.internal.model import Invitation
from modules.c2_m2.c2_m2_impl.internal.services import Database

SELECT = f"SELECT * FROM {Mapper.TABLE}"


class PostgresInvitationDao(InvitationDao):
    def __init__(self, db: Database) -> None:
        self.db = db

    def lock(self, invitation_id: str):
        return self.db.lock(f"c2_m2:invitation:{invitation_id}")

    def lock_staff(self):
        return self.db.lock("c2_m2:staff:all")

    def get(self, invitation_id: str) -> Invitation | None:
        row = self.db.query_one(f"{SELECT} WHERE id = %s", (invitation_id,))
        return Mapper.to_model(row) if row else None

    def save(self, invitation: Invitation) -> None:
        self.db.upsert(Mapper.TABLE, Mapper.KEY, Mapper.COLUMNS, Mapper.to_params(invitation), Mapper.CASTS)

    def find_by_code_hash(self, code_hash: str) -> Invitation | None:
        row = self.db.query_one(f"{SELECT} WHERE code_hash = %s", (code_hash,))
        return Mapper.to_model(row) if row else None

    def list_of(self, kind: InvitationKind, company_id: str | None) -> list[Invitation]:
        rows = self.db.query(f"{SELECT} WHERE kind = %s AND company_id IS NOT DISTINCT FROM %s::uuid",
                             (str(kind), company_id))
        return [Mapper.to_model(r) for r in rows]

    def list_all(self) -> list[Invitation]:
        return [Mapper.to_model(r) for r in self.db.query(SELECT)]
