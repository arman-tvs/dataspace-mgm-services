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
"""App roles of people of the company (README 7.5, 7.6), scope `company`."""
from abc import abstractmethod

from modules.c2_m2.c2_m2_api.model import AppRolesResult, CompanyAppRoles
from modules.c2_m2.c2_m2_rs_api.endpoint import AppId, Claims, CompanyId, JsonBody, Lang, RestApi, UserId, api


class CompanyAppRolesApi(RestApi):
    @api.get("/companies/{companyId}/apps/{appId}/roles")
    @abstractmethod
    def get_company_app_roles(self, claims: Claims, company_id: CompanyId, app_id: AppId,
                              lang: Lang = None) -> CompanyAppRoles: ...

    @api.put("/companies/{companyId}/users/{userId}/apps/{appId}/roles")
    @abstractmethod
    def set_user_app_roles(self, claims: Claims, company_id: CompanyId, user_id: UserId, app_id: AppId,
                           body: JsonBody) -> AppRolesResult: ...
