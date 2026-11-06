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
from modules.c2_m2.c2_m2_api.model import CompanyUser, Page, UserAccount
from modules.c2_m2.c2_m2_rs_api.apis import OspUsersApi

from .support import osp_actor, services


class OspUsersApiImpl(OspUsersApi):
    def list_users(self, claims: dict, page: int = 0, size: int = 20, company_id: str | None = None,
                   status: list[str] | None = None) -> Page[CompanyUser]:
        return services().users.list_company_users(company_id, status, page, size)

    def get_user_account(self, claims: dict, user_id: str) -> UserAccount:
        return services().users.get_user_account(user_id)

    def set_user_portal_roles_as_osp(self, claims: dict, company_id: str, user_id: str, body: dict) -> CompanyUser:
        return services().users.set_company_user_portal_roles(company_id, user_id, body, osp_actor(claims),
                                                              as_osp=True)

    def remove_user_as_osp(self, claims: dict, company_id: str, user_id: str) -> None:
        services().users.remove_company_user(company_id, user_id, osp_actor(claims), as_osp=True)
