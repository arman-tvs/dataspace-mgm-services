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

from collections.abc import Iterable

from modules.c2_m2.c2_m2_api.model.constants import BindingStatus
from modules.c2_m2.c2_m2_impl.dao.company_user_dao import CompanyUserDao
from modules.c2_m2.c2_m2_impl.dao.jdbc import CompanyUserRowMapper as Mapper
from modules.c2_m2.c2_m2_impl.internal.model import CompanyUser
from modules.c2_m2.c2_m2_impl.internal.services import Database

SELECT = f"SELECT * FROM {Mapper.TABLE}"


class PostgresCompanyUserDao(CompanyUserDao):
    def __init__(self, db: Database) -> None:
        self.db = db

    def lock_account(self, user_id: str):
        return self.db.lock(f"c2_m2:account:{user_id}")

    def save(self, binding: CompanyUser) -> None:
        self.db.upsert(Mapper.TABLE, Mapper.KEY, Mapper.COLUMNS, Mapper.to_params(binding), Mapper.CASTS)

    def current_of(self, user_id: str) -> CompanyUser | None:
        row = self.db.query_one(f"{SELECT} WHERE user_id = %s AND status IN ('ACTIVE', 'DISABLED')", (user_id,))
        return Mapper.to_model(row) if row else None

    def list_of(self, user_id: str, company_id: str) -> list[CompanyUser]:
        rows = self.db.query(f"{SELECT} WHERE user_id = %s AND company_id = %s ORDER BY created_at",
                             (user_id, company_id))
        return [Mapper.to_model(r) for r in rows]

    def list_of_company(self, company_id: str | None, statuses: Iterable[BindingStatus]) -> list[CompanyUser]:
        wanted = [str(s) for s in statuses]
        if company_id is None:
            rows = self.db.query(f"{SELECT} WHERE status = ANY(%s::text[])", (wanted,))
        else:
            rows = self.db.query(f"{SELECT} WHERE company_id = %s AND status = ANY(%s::text[])", (company_id, wanted))
        return [Mapper.to_model(r) for r in rows]
