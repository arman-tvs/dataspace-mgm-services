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
from modules.c2_m2.c2_m2_api.model import AppRolesResult, CompanyAppRoles
from modules.c2_m2.c2_m2_rs_api.apis import CompanyAppRolesApi

from .support import company_actor, services


class CompanyAppRolesApiImpl(CompanyAppRolesApi):
    def get_company_app_roles(self, claims: dict, company_id: str, app_id: str,
                              lang: str | None = None) -> CompanyAppRoles:
        company_actor(claims, company_id)
        return services().users.get_company_app_roles(company_id, app_id, lang)

    def set_user_app_roles(self, claims: dict, company_id: str, user_id: str, app_id: str,
                           body: dict) -> AppRolesResult:
        actor = company_actor(claims, company_id)
        return services().users.set_user_app_roles(company_id, user_id, app_id, body, actor)
