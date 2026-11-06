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
"""People of all companies for the OSP staff (README 7.11 to 7.14), scope `osp`."""
from abc import abstractmethod
from typing import Annotated

from fastapi import Query

from modules.c2_m2.c2_m2_api.model import CompanyUser, Page, UserAccount
from modules.c2_m2.c2_m2_rs_api.endpoint import (Claims, CompanyId, JsonBody, PageNumber, PageSize, RestApi,
                                                 StatusFilter, UserId, api)

CompanyFilter = Annotated[str | None, Query(alias="companyId")]


class OspUsersApi(RestApi):
    @api.get("/osp/users")
    @abstractmethod
    def list_users(self, claims: Claims, page: PageNumber = 0, size: PageSize = 20, company_id: CompanyFilter = None,
                   status: StatusFilter = None) -> Page[CompanyUser]: ...

    @api.get("/osp/users/{userId}")
    @abstractmethod
    def get_user_account(self, claims: Claims, user_id: UserId) -> UserAccount: ...

    @api.put("/osp/companies/{companyId}/users/{userId}/portal-roles")
    @abstractmethod
    def set_user_portal_roles_as_osp(self, claims: Claims, company_id: CompanyId, user_id: UserId,
                                     body: JsonBody) -> CompanyUser: ...

    @api.delete("/osp/companies/{companyId}/users/{userId}")
    @abstractmethod
    def remove_user_as_osp(self, claims: Claims, company_id: CompanyId, user_id: UserId) -> None: ...
