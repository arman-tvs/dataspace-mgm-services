#################################################################################
#  Copyright (c) 2026 Technovative Solutions
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
#  Assisted-By: Claude Code (claude-opus-5-5)
#################################################################################
"""What C2-M2 offers other modules on accounts of a company: the steps for Process Orchestration (README 8.8 to
8.10) and the query 9.4. `UserServiceImpl` delegates to it and keeps the bindings and roles they change."""
from __future__ import annotations

from typing import TYPE_CHECKING

from modules.c2_m2.c2_m2_api.exception import (
    ConflictException,
    InvalidStateException,
    StaffCompanyConflictException,
    UserAlreadyBoundException,
    UserNotFoundException,
)
from modules.c2_m2.c2_m2_api.model import AssignCompanyAdminResult, CompanyUserRef, CompanyUsersResult
from modules.c2_m2.c2_m2_api.model.common import Actor
from modules.c2_m2.c2_m2_api.model.constants import (
    BindingStatus,
    CompanyStatus,
    InvitationEndReason,
    InvitationStatus,
    JoinedVia,
    RoleKind,
)
from modules.c2_m2.c2_m2_impl.context import Context, statuses
from modules.c2_m2.c2_m2_impl.internal.model import Company, CompanyUser
from modules.c2_m2.c2_m2_impl.utils.validation_utils import Validator, invalid
from portal_common import settings

if TYPE_CHECKING:
    from .user_service_impl import UserServiceImpl


class InternalCompanyUserApi:
    """Steps assign-company-admin (8.8), disable-company-users (8.9), enable-company-users (8.10); query 9.4."""

    def __init__(self, ctx: Context, users: UserServiceImpl) -> None:
        self.ctx, self.users = ctx, users

    # -- 8.8 --------------------------------------------------------------------------------------
    def assign_company_admin(self, input: dict) -> AssignCompanyAdminResult:
        """8.8"""
        v, dao, operation = self.ctx.validate, self.ctx.dao, "assign-company-admin"
        company_id = v.uuid(input, "companyId")
        bpn = v.bpn(input)
        user_id = v.text(input, "applicantSub")
        actor = Actor.process(input)
        admin = self.users.cfg.from_properties("company.admin.role")
        with dao.lock(("company", company_id), ("account", user_id)):
            company = dao.companies.get(company_id)
            user, binding = self._preconditions(company, company_id, bpn, user_id)
            if company is None:
                company = Company(company_id, bpn)
                dao.companies.save(company)
            elif company.status == CompanyStatus.DISABLED:   # return after a transfer (FRAMEWORK 5.6)
                self.users._set_company_status(company, CompanyStatus.ACTIVE)
            if binding is None:
                self.users.bind(user_id, company, [admin], JoinedVia.ONBOARDING, actor, operation,
                                given_name=user.get("firstName"), family_name=user.get("lastName"))
            else:
                self._admin_of_existing_binding(binding, company, user, admin, actor, operation)
            return AssignCompanyAdminResult(company_id=company_id, user_id=user_id,
                                            portal_roles=self.users.company_roles(user_id))

    def _preconditions(self, company: Company | None, company_id: str, bpn: str,
                       user_id: str) -> tuple[dict, CompanyUser | None]:
        """The checks of 8.8 in their order; the account of the Portal IAM and its current binding."""
        if company is not None and company.bpn != bpn:
            raise ConflictException("the BPN differs from the stored one", retryable=False)
        if company is not None and company.status in (CompanyStatus.DISABLING, CompanyStatus.ENABLING):
            raise InvalidStateException(f"company status {company.status}", retryable=True)
        user = self.ctx.iam.get_user(user_id)
        if user is None:
            raise UserNotFoundException("account unknown in the Portal IAM", retryable=False)
        binding = self.ctx.dao.company_users.current_of(user_id)
        if binding is not None and binding.company_id != company_id:
            raise UserAlreadyBoundException("the account is bound to another company", retryable=False)
        if binding is None and company_id != settings.get("ospCompanyId") and self.users.has_staff_role(user_id):
            raise StaffCompanyConflictException("staff accounts bind only to the OSP company", retryable=False)
        return user, binding

    def _admin_of_existing_binding(self, binding: CompanyUser, company: Company, user: dict, admin: str,
                                   actor: Actor, operation: str) -> None:
        """An account already bound to the company: restore a disabled binding, add the admin role if missing."""
        user_id, company_id = binding.user_id, company.company_id
        restored = binding.status == BindingStatus.DISABLED
        if restored:
            self.users._restore(binding, company, actor, operation)
        else:
            self.users._set_company_attributes(self.ctx.iam.get_user(user_id) or user, company)
        added = [] if admin in self.users.portal_roles(user_id) else [admin]
        if added:
            self.ctx.iam.add_client_role_mappings(user_id, self.ctx.core_uuid, [self.ctx.core_role(admin)])
            self.users.log_roles(actor, operation, user_id, company_id, RoleKind.COMPANY_PORTAL, added, [])
            self.ctx.audit(actor, operation, company_id, user_id)
        if restored:
            self.ctx.publish("UserAssignedToCompany", {"userId": user_id, "companyId": company_id,
                                                       "via": str(JoinedVia.ONBOARDING),
                                                       "portalRoles": self.users.company_roles(user_id)})
        elif added:
            self.ctx.publish("UserRolesChanged", {"userId": user_id, "companyId": company_id,
                                                  "addedRoles": added, "removedRoles": []})

    # -- 8.9 and 8.10 -----------------------------------------------------------------------------
    def _user_ids(self, company_id: str, status: BindingStatus) -> list[str]:
        return sorted(b.user_id for b in self.ctx.dao.company_users.list_of_company(company_id, [status]))

    def disable_company_users(self, input: dict) -> CompanyUsersResult:
        """8.9"""
        company_id = self.ctx.validate.uuid(input, "companyId")
        actor, dao, operation = Actor.process(input), self.ctx.dao, "disable-company-users"
        if company_id == settings.get("ospCompanyId"):
            raise InvalidStateException("the OSP company is not deactivated by this step", retryable=False)
        with dao.lock(("company", company_id)):
            company = dao.companies.get(company_id)
            if company is None:
                return CompanyUsersResult(company_id=company_id, user_ids=[])
            if company.status == CompanyStatus.ENABLING:
                raise InvalidStateException("the company is being enabled", retryable=True)
            if company.status == CompanyStatus.ACTIVE:
                self.users._set_company_status(company, CompanyStatus.DISABLING)
                for inv in dao.invitations.list_all():
                    if inv.company_id == company_id and inv.status == InvitationStatus.OPEN:
                        inv.end(InvitationStatus.REVOKED, InvitationEndReason.COMPANY_DISABLED)
                        dao.invitations.save(inv)
                self.ctx.audit(actor, operation, company_id, company_id)
            if company.status == CompanyStatus.DISABLING:
                for binding in dao.company_users.list_of_company(company_id, [BindingStatus.ACTIVE]):
                    with dao.lock(("account", binding.user_id)):
                        self.users._suspend(binding, actor, operation)
                self.users._set_company_status(company, CompanyStatus.DISABLED)
                self.ctx.publish("CompanyUsersDisabled", {
                    "companyId": company_id, "userIds": self._user_ids(company_id, BindingStatus.DISABLED)})
            return CompanyUsersResult(company_id=company_id,
                                      user_ids=self._user_ids(company_id, BindingStatus.DISABLED))

    def enable_company_users(self, input: dict) -> CompanyUsersResult:
        """8.10"""
        company_id = self.ctx.validate.uuid(input, "companyId")
        actor, dao, operation = Actor.process(input), self.ctx.dao, "enable-company-users"
        with dao.lock(("company", company_id)):
            company = dao.companies.get(company_id)
            if company is None:
                return CompanyUsersResult(company_id=company_id, user_ids=[])
            if company.status == CompanyStatus.DISABLING:
                raise InvalidStateException("the company is being disabled", retryable=True)
            announce = company.status != CompanyStatus.ACTIVE
            if company.status == CompanyStatus.DISABLED:
                self.users._set_company_status(company, CompanyStatus.ENABLING)
            for binding in dao.company_users.list_of_company(company_id, [BindingStatus.DISABLED]):
                with dao.lock(("account", binding.user_id)):
                    self.users._restore(binding, company, actor, operation)
            user_ids = self._user_ids(company_id, BindingStatus.ACTIVE)
            if announce:
                self.users._set_company_status(company, CompanyStatus.ACTIVE)
                self.ctx.publish("CompanyUsersEnabled", {"companyId": company_id, "userIds": user_ids})
            return CompanyUsersResult(company_id=company_id, user_ids=user_ids)

    # -- 9.4 --------------------------------------------------------------------------------------
    def list_company_user_refs(self, company_id: str | None, portal_role: str | None,
                               status: list[str] | str | None) -> list[CompanyUserRef]:
        """9.4"""
        if not company_id:
            raise invalid("companyId is required")
        company_id = Validator.uuid({"companyId": company_id}, "companyId")
        wanted = statuses(status, BindingStatus, [BindingStatus.ACTIVE])
        found = self.ctx.dao.company_users.list_of_company(company_id, wanted)
        if portal_role:
            if portal_role not in self.users._company_roles():
                raise invalid(f"portalRole: one of {list(self.users._company_roles())}")
            with_role = {u["id"] for u in self.users.users_with_role(portal_role)}
            found = [b for b in found if b.user_id in with_role]
        return [CompanyUserRef(user_id=b.user_id, status=b.status) for b in sorted(found, key=lambda b: b.created_at)]
