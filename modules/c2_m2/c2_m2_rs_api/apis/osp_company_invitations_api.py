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
"""Invitations to any company by the OSP staff (README 7.20 to 7.22), scope `osp`."""
from abc import abstractmethod

from modules.c2_m2.c2_m2_api.model import Invitation, InvitationWithCode, Page
from modules.c2_m2.c2_m2_rs_api.endpoint import (Claims, CompanyId, InvitationId, JsonBody, PageNumber, PageSize,
                                                 RestApi, StatusFilter, api)


class OspCompanyInvitationsApi(RestApi):
    @api.get("/osp/companies/{companyId}/invitations")
    @abstractmethod
    def list_invitations_as_osp(self, claims: Claims, company_id: CompanyId, page: PageNumber = 0, size: PageSize = 20,
                                status: StatusFilter = None) -> Page[Invitation]: ...

    @api.post("/osp/companies/{companyId}/invitations")
    @abstractmethod
    def create_invitation_as_osp(self, claims: Claims, company_id: CompanyId, body: JsonBody) -> InvitationWithCode: ...

    @api.delete("/osp/companies/{companyId}/invitations/{invitationId}")
    @abstractmethod
    def revoke_invitation_as_osp(self, claims: Claims, company_id: CompanyId,
                                 invitation_id: InvitationId) -> None: ...
