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

import datetime as dt
from dataclasses import dataclass, field

from modules.c2_m2.c2_m2_api.model.constants import InvitationEndReason, InvitationKind, InvitationStatus

from .utils.datetime_utils import iso, now
from .utils.id_utils import new_id


@dataclass
class Invitation:
    """Table `invitation` (README 5); only the hash of the code is stored (6.8)."""
    kind: InvitationKind
    company_id: str | None
    given_name: str | None
    family_name: str | None
    roles: list[str]
    code_hash: str
    expires_at: dt.datetime
    created_by: str | None
    id: str = field(default_factory=new_id)
    status: InvitationStatus = InvitationStatus.OPEN
    end_reason: InvitationEndReason | None = None
    failed_attempts: int = 0
    accepted_by: str | None = None
    accepted_at: dt.datetime | None = None
    created_at: dt.datetime = field(default_factory=now)
    ended_at: dt.datetime | None = None

    def is_expired(self, at: dt.datetime | None = None) -> bool:
        return self.status == InvitationStatus.OPEN and self.expires_at <= (at or now())

    def effective_status(self) -> InvitationStatus:
        """Expired open invitations count as `EXPIRED` even before the cleanup job ran (6.8)."""
        return InvitationStatus.EXPIRED if self.is_expired() else self.status

    def end(self, status: InvitationStatus, reason: InvitationEndReason | None = None) -> None:
        self.status, self.end_reason, self.ended_at = status, reason, now()
        self.given_name = self.family_name = None

    def to_api(self) -> dict:
        status = self.effective_status()
        is_open = status == InvitationStatus.OPEN
        return {"id": self.id, "kind": str(self.kind), "companyId": self.company_id,
                "givenName": self.given_name if is_open else None, "familyName": self.family_name if is_open else None,
                "roles": list(self.roles), "status": str(status),
                "endReason": str(self.end_reason) if self.end_reason else None, "expiresAt": iso(self.expires_at),
                "createdBy": self.created_by, "createdAt": iso(self.created_at), "acceptedBy": self.accepted_by,
                "acceptedAt": iso(self.accepted_at)}

    def accept_result(self) -> dict:
        return {"invitationId": self.id, "kind": str(self.kind), "userId": self.accepted_by,
                "companyId": self.company_id, "roles": list(self.roles)}
