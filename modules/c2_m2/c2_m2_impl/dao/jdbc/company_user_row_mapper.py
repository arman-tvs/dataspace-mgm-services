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

import json

from modules.c2_m2.c2_m2_api.model.constants import BindingStatus, JoinedVia, RemovalReason
from modules.c2_m2.c2_m2_impl.internal.model import CompanyUser, SuspendedRoles

from .row_mapper import RowMapper


class CompanyUserRowMapper(RowMapper):
    TABLE = "company_user"
    KEY = "id"
    COLUMNS = ("id", "user_id", "company_id", "given_name", "family_name", "status", "joined_via", "invitation_id",
               "removal_reason", "suspended_roles", "created_at", "changed_at", "removed_at")
    CASTS = {"suspended_roles": "jsonb"}

    @staticmethod
    def _suspended_json(roles: SuspendedRoles | None) -> str | None:
        if roles is None:
            return None
        return json.dumps({"portalRoles": roles.portal_roles, "appRoles": [list(r) for r in roles.app_roles]})

    @staticmethod
    def _suspended_from(value) -> SuspendedRoles | None:
        if value is None:
            return None
        data = json.loads(value) if isinstance(value, str) else value
        return SuspendedRoles(portal_roles=list(data.get("portalRoles") or []),
                              app_roles=[tuple(r) for r in data.get("appRoles") or []])

    @classmethod
    def to_params(cls, b: CompanyUser) -> tuple:
        return (b.id, b.user_id, b.company_id, b.given_name, b.family_name, str(b.status), str(b.joined_via),
                b.invitation_id, cls.text(b.removal_reason), cls._suspended_json(b.suspended_roles), b.created_at,
                b.changed_at, b.removed_at)

    @classmethod
    def to_model(cls, row: dict) -> CompanyUser:
        return CompanyUser(id=cls.text(row["id"]), user_id=cls.text(row["user_id"]),
                           company_id=cls.text(row["company_id"]), joined_via=JoinedVia(row["joined_via"]),
                           given_name=row["given_name"], family_name=row["family_name"],
                           status=BindingStatus(row["status"]), invitation_id=cls.text(row["invitation_id"]),
                           removal_reason=RemovalReason(row["removal_reason"]) if row["removal_reason"] else None,
                           suspended_roles=cls._suspended_from(row["suspended_roles"]), created_at=row["created_at"],
                           changed_at=row["changed_at"], removed_at=row["removed_at"])
