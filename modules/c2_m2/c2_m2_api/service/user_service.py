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

from modules.c2_m2.c2_m2_api.model import (AppRolesResult, AssignCompanyAdminResult, CompanyAppRoles, CompanyUser,
                                           CompanyUserDetail, CompanyUserRef, CompanyUsersResult, Page, StaffMember,
                                           UserAccount)
from modules.c2_m2.c2_m2_api.model.common import Actor


class UserService(abc.ABC):
    """People, portal roles, app roles and OSP staff: operations 7.1 to 7.6 and 7.11 to 7.16,
    steps 8.8 to 8.10 and query 9.4. `as_osp` selects the variant for OSP staff (scope `osp`)."""

    @abc.abstractmethod
    def list_company_users(self, company_id: str | None, status: list[str] | None, page: int,
                           size: int) -> Page[CompanyUser]: ...

    @abc.abstractmethod
    def get_company_user(self, company_id: str, user_id: str) -> CompanyUserDetail: ...

    @abc.abstractmethod
    def set_company_user_portal_roles(self, company_id: str, user_id: str, body: dict, actor: Actor,
                                      as_osp: bool = False) -> CompanyUser: ...

    @abc.abstractmethod
    def remove_company_user(self, company_id: str, user_id: str, actor: Actor, as_osp: bool = False) -> None: ...

    @abc.abstractmethod
    def set_user_app_roles(self, company_id: str, user_id: str, app_id: str, body: dict,
                           actor: Actor) -> AppRolesResult: ...

    @abc.abstractmethod
    def get_company_app_roles(self, company_id: str, app_id: str, lang: str | None) -> CompanyAppRoles: ...

    @abc.abstractmethod
    def get_user_account(self, user_id: str) -> UserAccount: ...

    @abc.abstractmethod
    def list_staff(self, page: int, size: int) -> Page[StaffMember]: ...

    @abc.abstractmethod
    def set_staff_roles(self, user_id: str, body: dict, actor: Actor) -> StaffMember: ...

    @abc.abstractmethod
    def assign_company_admin(self, input: dict) -> AssignCompanyAdminResult: ...

    @abc.abstractmethod
    def disable_company_users(self, input: dict) -> CompanyUsersResult: ...

    @abc.abstractmethod
    def enable_company_users(self, input: dict) -> CompanyUsersResult: ...

    @abc.abstractmethod
    def list_company_user_refs(self, company_id: str | None, portal_role: str | None,
                               status: list[str] | str | None) -> list[CompanyUserRef]: ...
