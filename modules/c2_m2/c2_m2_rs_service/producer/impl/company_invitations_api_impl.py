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
#  Assisted-By: GitHub Copilot
#################################################################################
from modules.c2_m2.c2_m2_api.model import Invitation, InvitationWithCode, Page
from modules.c2_m2.c2_m2_api.model.constants import InvitationKind
from modules.c2_m2.c2_m2_rs_api.apis import CompanyInvitationsApi

from .support import company_actor, services


class CompanyInvitationsApiImpl(CompanyInvitationsApi):
    def list_invitations(self, claims: dict, company_id: str, page: int = 0, size: int = 20,
                         status: list[str] | None = None) -> Page[Invitation]:
        company_actor(claims, company_id)
        return services().invitations.list(InvitationKind.COMPANY, company_id, status, page, size)

    def create_invitation(self, claims: dict, company_id: str, body: dict) -> InvitationWithCode:
        actor = company_actor(claims, company_id)
        return services().invitations.create(InvitationKind.COMPANY, company_id, body, actor, "createInvitation")

    def revoke_invitation(self, claims: dict, company_id: str, invitation_id: str) -> None:
        actor = company_actor(claims, company_id)
        services().invitations.revoke(InvitationKind.COMPANY, company_id, invitation_id, actor, "revokeInvitation")
