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
from modules.c2_m2.c2_m2_api.model import CompanyUser, CompanyUserDetail, Page
from modules.c2_m2.c2_m2_rs_api.apis import CompanyUsersApi

from .support import company_actor, services


class CompanyUsersApiImpl(CompanyUsersApi):
    def list_company_users(self, claims: dict, company_id: str, page: int = 0, size: int = 20,
                           status: list[str] | None = None) -> Page[CompanyUser]:
        company_actor(claims, company_id)
        return services().users.list_company_users(company_id, status, page, size)

    def get_company_user(self, claims: dict, company_id: str, user_id: str) -> CompanyUserDetail:
        company_actor(claims, company_id)
        return services().users.get_company_user(company_id, user_id)

    def set_company_user_portal_roles(self, claims: dict, company_id: str, user_id: str, body: dict) -> CompanyUser:
        actor = company_actor(claims, company_id)
        return services().users.set_company_user_portal_roles(company_id, user_id, body, actor)

    def remove_company_user(self, claims: dict, company_id: str, user_id: str) -> None:
        actor = company_actor(claims, company_id)
        services().users.remove_company_user(company_id, user_id, actor)
