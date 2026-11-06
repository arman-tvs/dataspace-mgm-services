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

from modules.c2_m2.c2_m2_impl.dao.app_instance_client_dao import AppInstanceClientDao
from modules.c2_m2.c2_m2_impl.dao.jdbc import AppInstanceClientRowMapper as Mapper
from modules.c2_m2.c2_m2_impl.internal.model import AppInstanceClient
from modules.c2_m2.c2_m2_impl.internal.services import Database

SELECT = f"SELECT * FROM {Mapper.TABLE}"


class PostgresAppInstanceClientDao(AppInstanceClientDao):
    def __init__(self, db: Database) -> None:
        self.db = db

    def _one(self, where: str, params: tuple) -> AppInstanceClient | None:
        row = self.db.query_one(f"{SELECT} WHERE {where}", params)
        return Mapper.to_model(row) if row else None

    def _many(self, where: str, params: tuple) -> list[AppInstanceClient]:
        return [Mapper.to_model(r) for r in self.db.query(f"{SELECT} {where} ORDER BY created_at", params)]

    def get(self, instance_client_id: str) -> AppInstanceClient | None:
        return self._one("id = %s", (instance_client_id,))

    def save(self, instance_client: AppInstanceClient) -> None:
        self.db.upsert(Mapper.TABLE, Mapper.KEY, Mapper.COLUMNS, Mapper.to_params(instance_client), Mapper.CASTS)

    def find_by_subscription(self, offer_subscription_id: str) -> AppInstanceClient | None:
        return self._one("offer_subscription_id = %s", (offer_subscription_id,))

    def find_single(self, app_id: str) -> AppInstanceClient | None:
        return self._one("app_id = %s AND instance_kind = 'SINGLE' AND status <> 'DISABLED'", (app_id,))

    def find_by_iam_client_id(self, iam_client_id: str) -> AppInstanceClient | None:
        return self._one("iam_client_id = %s", (iam_client_id,))

    def list_of_app(self, app_id: str) -> list[AppInstanceClient]:
        return self._many("WHERE app_id = %s", (app_id,))

    def list_all(self) -> list[AppInstanceClient]:
        return self._many("", ())

    def next_client_number(self) -> int:
        return int(self.db.query_one("SELECT nextval('client_number') AS n")["n"])
