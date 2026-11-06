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

from modules.c2_m2.c2_m2_api.model.constants import RoleKind
from modules.c2_m2.c2_m2_impl.internal.model import RoleAssignmentLogEntry

from .row_mapper import RowMapper


class RoleAssignmentLogRowMapper(RowMapper):
    TABLE = "role_assignment_log"
    KEY = "id"
    COLUMNS = ("id", "occurred_at", "user_id", "company_id", "role_kind", "iam_client_id", "app_id",
               "app_instance_client_id", "role_name", "action", "actor_type", "actor_sub", "process_id", "step_run_id",
               "operation")

    @classmethod
    def to_params(cls, e: RoleAssignmentLogEntry) -> tuple:
        return (e.id, e.occurred_at, e.user_id, e.company_id, str(e.role_kind), e.iam_client_id, e.app_id,
                e.app_instance_client_id, e.role_name, e.action, *cls.actor_params(e.actor), e.operation)

    @classmethod
    def to_model(cls, row: dict) -> RoleAssignmentLogEntry:
        return RoleAssignmentLogEntry(user_id=cls.text(row["user_id"]), company_id=cls.text(row["company_id"]),
                                      role_kind=RoleKind(row["role_kind"]), iam_client_id=row["iam_client_id"],
                                      role_name=row["role_name"], action=row["action"], actor=cls.actor_from(row),
                                      operation=row["operation"], app_id=cls.text(row["app_id"]),
                                      app_instance_client_id=cls.text(row["app_instance_client_id"]),
                                      id=cls.text(row["id"]), occurred_at=row["occurred_at"])
