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

from modules.c2_m2.c2_m2_api.model.constants import InvitationEndReason, InvitationKind, InvitationStatus
from modules.c2_m2.c2_m2_impl.internal.model import Invitation

from .row_mapper import RowMapper


class InvitationRowMapper(RowMapper):
    TABLE = "invitation"
    KEY = "id"
    COLUMNS = ("id", "kind", "company_id", "given_name", "family_name", "roles", "code_hash", "status", "end_reason",
               "failed_attempts", "expires_at", "created_by", "accepted_by", "accepted_at", "created_at", "ended_at")
    CASTS = {"roles": "text[]"}

    @classmethod
    def to_params(cls, i: Invitation) -> tuple:
        return (i.id, str(i.kind), i.company_id, i.given_name, i.family_name, list(i.roles), i.code_hash,
                str(i.status), cls.text(i.end_reason), i.failed_attempts, i.expires_at, i.created_by, i.accepted_by,
                i.accepted_at, i.created_at, i.ended_at)

    @classmethod
    def to_model(cls, row: dict) -> Invitation:
        return Invitation(id=cls.text(row["id"]), kind=InvitationKind(row["kind"]),
                          company_id=cls.text(row["company_id"]), given_name=row["given_name"],
                          family_name=row["family_name"], roles=list(row["roles"] or []), code_hash=row["code_hash"],
                          status=InvitationStatus(row["status"]),
                          end_reason=InvitationEndReason(row["end_reason"]) if row["end_reason"] else None,
                          failed_attempts=row["failed_attempts"], expires_at=row["expires_at"],
                          created_by=cls.text(row["created_by"]), accepted_by=cls.text(row["accepted_by"]),
                          accepted_at=row["accepted_at"], created_at=row["created_at"], ended_at=row["ended_at"])
