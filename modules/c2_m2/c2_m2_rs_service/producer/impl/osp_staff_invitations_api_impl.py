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
from modules.c2_m2.c2_m2_rs_api.apis import OspStaffInvitationsApi

from .support import osp_actor, services


class OspStaffInvitationsApiImpl(OspStaffInvitationsApi):
    def list_staff_invitations(self, claims: dict, page: int = 0, size: int = 20,
                               status: list[str] | None = None) -> Page[Invitation]:
        return services().invitations.list(InvitationKind.STAFF, None, status, page, size)

    def create_staff_invitation(self, claims: dict, body: dict) -> InvitationWithCode:
        return services().invitations.create(InvitationKind.STAFF, None, body, osp_actor(claims),
                                             "createStaffInvitation")

    def revoke_staff_invitation(self, claims: dict, invitation_id: str) -> None:
        services().invitations.revoke(InvitationKind.STAFF, None, invitation_id, osp_actor(claims),
                                      "revokeStaffInvitation")
