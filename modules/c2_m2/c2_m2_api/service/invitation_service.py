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

import abc

from modules.c2_m2.c2_m2_api.model import AcceptInvitationResult, Actor, Invitation, InvitationWithCode, Page
from modules.c2_m2.c2_m2_api.model.constants import InvitationKind


class InvitationService(abc.ABC):
    """Invitations of kind `COMPANY` and `STAFF`: operations 7.7 to 7.10 and 7.17 to 7.22.
    `company_id` is None for `STAFF`; `operation` is the operationId for the audit log."""

    @abc.abstractmethod
    def create(self, kind: InvitationKind, company_id: str | None, body: dict, actor: Actor,
               operation: str) -> InvitationWithCode: ...

    @abc.abstractmethod
    def list(self, kind: InvitationKind, company_id: str | None, status: list[str] | None, page: int,
             size: int) -> Page[Invitation]: ...

    @abc.abstractmethod
    def revoke(self, kind: InvitationKind, company_id: str | None, invitation_id: str, actor: Actor,
               operation: str) -> None: ...

    @abc.abstractmethod
    def accept(self, body: dict, claims: dict) -> AcceptInvitationResult: ...
