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
"""Accounts of people: bindings, portal roles, app roles, OSP staff (README 6.5 to 6.7, 6.10 to 6.12),
operations 7.1 to 7.6 and 7.11 to 7.16, steps 8.8 to 8.10 and query 9.4."""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

from modules.c2_m2.c2_m2_api.exception import (CompanyNotActiveException, ConflictException, InvalidStateException,
                                               LastCompanyAdminException, LastOspAdminException,
                                               NoActiveSubscriptionException, NotFoundException,
                                               StaffCompanyConflictException, UnknownAppRoleException,
                                               UserAlreadyBoundException, UserNotFoundException)
from modules.c2_m2.c2_m2_api.model import (AppRolesResult, AssignCompanyAdminResult, CompanyAppRoles,
                                           CompanyUser as CompanyUserModel, CompanyUserDetail, CompanyUserRef,
                                           CompanyUsersResult, Page, StaffMember, UserAccount)
from modules.c2_m2.c2_m2_api.model.common import Actor
from modules.c2_m2.c2_m2_api.model.constants import (BindingStatus, CompanyStatus, InstanceClientStatus,
                                                     InvitationEndReason, InvitationStatus, JoinedVia, RemovalReason,
                                                     RoleKind)
from modules.c2_m2.c2_m2_api.service import UserService
from modules.c2_m2.c2_m2_impl.config.properties import as_list
from modules.c2_m2.c2_m2_impl.context import Context, paginate, statuses
from modules.c2_m2.c2_m2_impl.dao import DaoService
from modules.c2_m2.c2_m2_impl.internal.model import AppInstanceClient, Company, CompanyUser, SuspendedRoles, now
from modules.c2_m2.c2_m2_impl.utils.validation_utils import Validator, invalid
from portal_common import settings

from .app_client_service_impl import AppClientServiceImpl

ADDED, REMOVED = "ADDED", "REMOVED"


class UserServiceImpl(UserService):
    def __init__(self, ctx: Context, apps: AppClientServiceImpl) -> None:
        self.ctx = ctx
        self.apps = apps

    @property
    def cfg(self):
        return self.ctx.config

    @property
    def dao(self) -> DaoService:
        return self.ctx.dao

    # -- reading the Portal IAM ----------------------------------------------------------------
    def _mappings(self, user_id: str) -> dict | None:
        return self.ctx.iam.role_mappings(user_id)

    def _core_names(self, mappings: dict | None) -> set[str]:
        client_mappings = (mappings or {}).get("clientMappings") or {}
        core = client_mappings.get(self.cfg.from_properties("portal.core.client.id")) or {}
        return {r["name"] for r in core.get("mappings") or []}

    def portal_roles(self, user_id: str) -> set[str]:
        return self._core_names(self._mappings(user_id))

    def company_roles(self, user_id: str) -> list[str]:
        return sorted(self.portal_roles(user_id) & set(self._company_roles()))

    def staff_roles(self, user_id: str) -> list[str]:
        return sorted(self.portal_roles(user_id) & set(self._staff_roles()))

    def has_staff_role(self, user_id: str) -> bool:
        return bool(self.staff_roles(user_id))

    def _instance_mappings(self, mappings: dict | None) -> Iterator[tuple[AppInstanceClient, str, list[dict]]]:
        """Assignments on instance clients of this module; other clients are left out (7.2)."""
        for client_id, cm in ((mappings or {}).get("clientMappings") or {}).items():
            ic = self.dao.instance_clients.find_by_iam_client_id(client_id)
            if ic is not None and cm.get("mappings"):
                yield ic, cm["id"], cm["mappings"]

    def _app_roles_view(self, mappings: dict | None) -> list[dict]:
        return [{"appId": ic.app_id, "appInstanceClientId": ic.id, "iamClientId": ic.iam_client_id,
                 "instanceClientStatus": str(ic.status), "roles": sorted(r["name"] for r in roles)}
                for ic, _, roles in self._instance_mappings(mappings)]

    def users_with_role(self, role: str) -> list[dict]:
        return self.ctx.iam.users_with_client_role(self.ctx.core_uuid, role)

    # -- portal roles (6.12.2) -----------------------------------------------------------------
    def set_roles(self, user_id: str, role_set: tuple[str, ...], wanted: list[str]) -> tuple[list[str], list[str]]:
        """Sets the roles of one role set to exactly `wanted`; `Applicant` and the other set stay."""
        current = self.portal_roles(user_id)
        added = [r for r in wanted if r not in current]
        removed = sorted(r for r in current if r in role_set and r not in wanted)
        if added:
            self.ctx.iam.add_client_role_mappings(user_id, self.ctx.core_uuid, [self.ctx.core_role(r) for r in added])
        if removed:
            self.ctx.iam.remove_client_role_mappings(user_id, self.ctx.core_uuid,
                                                     [self.ctx.core_role(r) for r in removed])
        return added, removed

    def log_roles(self, actor: Actor, operation: str, user_id: str, company_id: str | None, kind: RoleKind,
                  added: list[str], removed: list[str], client: AppInstanceClient | None = None) -> None:
        client_id = client.iam_client_id if client else self.cfg.from_properties("portal.core.client.id")
        for action, names in ((ADDED, added), (REMOVED, removed)):
            for name in names:
                self.ctx.log_role(actor, operation, action, user_id, company_id, kind, client_id, name, client)

    # -- company row (6.6) and limits (6.7) ------------------------------------------------------
    def ensure_company_active(self, company_id: str) -> Company:
        company = self.dao.companies.get(company_id)
        if company is not None:
            if company.status != CompanyStatus.ACTIVE:
                raise CompanyNotActiveException(f"company status {company.status}")
            return company
        found = self.ctx.company_profiles.company(company_id)
        if not found or found.get("status") != "ACTIVE" or not found.get("bpn"):
            raise CompanyNotActiveException("the company is not ACTIVE in C3-M1 or has no BPN")
        company = Company(company_id, found["bpn"])
        self.dao.companies.save(company)
        return company

    def company_admins(self, company_id: str) -> set[str]:
        bound = {b.user_id for b in self.dao.company_users.list_of_company(company_id, [BindingStatus.ACTIVE])}
        return {u["id"] for u in self.users_with_role(self.cfg.from_properties("company.admin.role"))} & bound

    def _is_last_company_admin(self, company_id: str, user_id: str) -> bool:
        return self.company_admins(company_id) == {user_id}

    def enabled_osp_admins(self) -> set[str]:
        admin = self.cfg.from_properties("staff.admin.role")
        return {u["id"] for u in self.users_with_role(admin) if u.get("enabled", True)}

    def _binding_for_change(self, company_id: str, user_id: str) -> CompanyUser:
        """Binding `ACTIVE` of the account to the company: none or `REMOVED` 404, `DISABLED` 409."""
        current = next((b for b in self.dao.company_users.list_of(user_id, company_id)
                        if b.status != BindingStatus.REMOVED), None)
        if current is None:
            raise NotFoundException("no binding of the account to this company")
        if current.status == BindingStatus.DISABLED:
            raise InvalidStateException("the company is deactivated")
        return current

    def _set_company_status(self, company: Company, status: CompanyStatus) -> None:
        company.status, company.changed_at = status, now()
        self.dao.companies.save(company)

    def _company_roles(self) -> tuple[str, ...]:
        return as_list(self.cfg.from_properties("company.portal.roles"))

    def _staff_roles(self) -> tuple[str, ...]:
        return as_list(self.cfg.from_properties("staff.portal.roles"))

    # -- account attributes ----------------------------------------------------------------------
    def _set_company_attributes(self, user: dict, company: Company | None) -> None:
        """`company_id` and `bpn` on the account (empty list removes them) and `enabled` = true (6.5)."""
        cfg = self.cfg
        want = {cfg.from_properties("company.id.attribute"): [company.company_id] if company else [],
                cfg.from_properties("bpn.attribute"): [company.bpn] if company and company.bpn else []}
        attrs = dict(user.get("attributes") or {})
        if all(attrs.get(k, []) == v for k, v in want.items()) and user.get("enabled", True):
            return
        self.ctx.iam.update_user(user["id"], user | {"attributes": attrs | want, "enabled": True})

    # -- bind, unbind, suspend, restore (6.12, 8.9, 8.10) ----------------------------------------
    def bind(self, user_id: str, company: Company, roles: list[str], via: JoinedVia, actor: Actor, operation: str,
             invitation_id: str | None = None, given_name: str | None = None,
             family_name: str | None = None) -> CompanyUser:
        """6.12.1"""
        user = self.ctx.iam.get_user(user_id)
        if user is None:
            raise UserNotFoundException("account unknown in the Portal IAM")
        self._set_company_attributes(user, company)
        added, removed = self.set_roles(user_id, self._company_roles(), roles)
        binding = CompanyUser(user_id, company.company_id, via, given_name=given_name, family_name=family_name,
                              invitation_id=invitation_id)
        self.dao.company_users.save(binding)
        self.log_roles(actor, operation, user_id, company.company_id, RoleKind.COMPANY_PORTAL, added, removed)
        self.ctx.audit(actor, operation, company.company_id, user_id)
        self.ctx.publish("UserAssignedToCompany", {"userId": user_id, "companyId": company.company_id,
                                                   "via": str(via), "portalRoles": sorted(roles)})
        return binding

    def _remove_portal_and_app_roles(self, binding: CompanyUser, mappings: dict, actor: Actor,
                                     operation: str) -> None:
        """Removes app roles on instance clients and company portal roles."""
        iam, uid, cid = self.ctx.iam, binding.user_id, binding.company_id
        for ic, client_uuid, roles in self._instance_mappings(mappings):
            iam.remove_client_role_mappings(uid, client_uuid, roles)
            self.log_roles(actor, operation, uid, cid, RoleKind.APP, [], sorted(r["name"] for r in roles), ic)
        portal = sorted(self._core_names(mappings) & set(self._company_roles()))
        if portal:
            iam.remove_client_role_mappings(uid, self.ctx.core_uuid, [self.ctx.core_role(r) for r in portal])
            self.log_roles(actor, operation, uid, cid, RoleKind.COMPANY_PORTAL, [], portal)

    def _mark_removed(self, binding: CompanyUser, reason: RemovalReason, actor: Actor, operation: str) -> None:
        binding.status, binding.removal_reason = BindingStatus.REMOVED, reason
        binding.removed_at = binding.changed_at = now()
        binding.given_name = binding.family_name = None
        binding.suspended_roles = None
        self.dao.company_users.save(binding)
        self.ctx.audit(actor, operation, binding.company_id, binding.user_id)
        self.ctx.publish("UserRemovedFromCompany", {"userId": binding.user_id, "companyId": binding.company_id,
                                                    "reason": str(reason)})

    def unbind(self, binding: CompanyUser, reason: RemovalReason, actor: Actor, operation: str) -> None:
        """6.12.3: the account remains, without a company and with `Applicant`."""
        mappings = self._mappings(binding.user_id)
        if mappings is None:
            self._mark_removed(binding, RemovalReason.ACCOUNT_DELETED, actor, operation)
            return
        self._remove_portal_and_app_roles(binding, mappings, actor, operation)
        user = self.ctx.iam.get_user(binding.user_id)
        if user is not None:
            self._set_company_attributes(user, None)
        self.ctx.iam.logout_user(binding.user_id)
        self._mark_removed(binding, reason, actor, operation)

    def _suspend(self, binding: CompanyUser, actor: Actor, operation: str) -> None:
        """8.9 step 4 for one binding; the saved roles are stored before anything is removed."""
        mappings = self._mappings(binding.user_id)
        if mappings is None:
            self._mark_removed(binding, RemovalReason.ACCOUNT_DELETED, actor, operation)
            return
        if binding.suspended_roles is None or binding.suspended_roles.is_empty():
            binding.suspended_roles = SuspendedRoles(
                portal_roles=sorted(self._core_names(mappings) & set(self._company_roles())),
                app_roles=[(ic.iam_client_id, r["name"]) for ic, _, roles in self._instance_mappings(mappings)
                           for r in roles])
            self.dao.company_users.save(binding)
        self._remove_portal_and_app_roles(binding, mappings, actor, operation)
        user = self.ctx.iam.get_user(binding.user_id)
        if user is not None:
            self._set_company_attributes(user, None)
        self.ctx.iam.logout_user(binding.user_id)
        binding.status, binding.changed_at = BindingStatus.DISABLED, now()
        self.dao.company_users.save(binding)
        self.ctx.audit(actor, operation, binding.company_id, binding.user_id)

    def _restore(self, binding: CompanyUser, company: Company, actor: Actor, operation: str) -> bool:
        """8.10 step 3 for one binding; False if the account no longer exists."""
        iam, uid = self.ctx.iam, binding.user_id
        user = iam.get_user(uid)
        if user is None:
            self._mark_removed(binding, RemovalReason.ACCOUNT_DELETED, actor, operation)
            return False
        self._set_company_attributes(user, company)
        saved = binding.suspended_roles or SuspendedRoles()
        current = self.portal_roles(uid)
        portal = [r for r in saved.portal_roles if r not in current]
        if portal:
            iam.add_client_role_mappings(uid, self.ctx.core_uuid, [self.ctx.core_role(r) for r in portal])
            self.log_roles(actor, operation, uid, company.company_id, RoleKind.COMPANY_PORTAL, portal, [])
        for client_id, role_name in saved.app_roles:
            ic = self.dao.instance_clients.find_by_iam_client_id(client_id)
            if ic is None or ic.iam_client_uuid is None or ic.status == InstanceClientStatus.DISABLED:
                continue
            role = iam.client_role(ic.iam_client_uuid, role_name)
            if role is not None:
                iam.add_client_role_mappings(uid, ic.iam_client_uuid, [role])
                self.log_roles(actor, operation, uid, company.company_id, RoleKind.APP, [role_name], [], ic)
        binding.status, binding.suspended_roles, binding.changed_at = BindingStatus.ACTIVE, None, now()
        self.dao.company_users.save(binding)
        self.ctx.audit(actor, operation, company.company_id, uid)
        return True

    # -- operations: people of the company (7.1 to 7.6) and of all companies (7.11 to 7.14) ------
    def _view(self, binding: CompanyUser) -> dict:
        roles = [] if binding.status == BindingStatus.REMOVED else self.company_roles(binding.user_id)
        return binding.to_api(roles)

    @staticmethod
    def _sort_key(b: CompanyUser) -> tuple:
        return b.family_name or "", b.given_name or "", b.created_at

    def list_company_users(self, company_id: str | None, status: list[str] | None, page: int,
                           size: int) -> Page[CompanyUserModel]:
        """7.1 (one company) and 7.11 (`company_id` None: all companies, sorted by company first)."""
        wanted = statuses(status, BindingStatus, [BindingStatus.ACTIVE, BindingStatus.DISABLED])
        found = self.dao.company_users.list_of_company(company_id, wanted)
        found.sort(key=lambda b: (b.company_id, *self._sort_key(b)) if company_id is None else self._sort_key(b))
        return Page[CompanyUserModel].model_validate(paginate(found, page, size, self._view))

    def get_company_user(self, company_id: str, user_id: str) -> CompanyUserDetail:
        """7.2"""
        binding = self.dao.company_users.current_of(user_id)
        if binding is None or binding.company_id != company_id:
            raise NotFoundException("no binding of the account to this company")
        mappings = self._mappings(user_id)
        roles = sorted(self._core_names(mappings) & set(self._company_roles()))
        return CompanyUserDetail.model_validate(binding.to_api(roles) | {"appRoles": self._app_roles_view(mappings)})

    def set_company_user_portal_roles(self, company_id: str, user_id: str, body: dict, actor: Actor,
                                      as_osp: bool = False) -> CompanyUserModel:
        """7.3 and, with `as_osp`, 7.13 (without the limit "last Company Admin")."""
        operation = "setUserPortalRolesAsOsp" if as_osp else "setCompanyUserPortalRoles"
        with self.dao.lock(("company", company_id), ("account", user_id)):
            binding = self._binding_for_change(company_id, user_id)
            roles = self.ctx.validate.role_list(body, "portalRoles", self._company_roles())
            admin = self.cfg.from_properties("company.admin.role")
            if not as_osp and admin not in roles and admin in self.portal_roles(user_id) \
                    and self._is_last_company_admin(company_id, user_id):
                raise LastCompanyAdminException("the company keeps at least one Company Admin")
            added, removed = self.set_roles(user_id, self._company_roles(), roles)
            self.log_roles(actor, operation, user_id, company_id, RoleKind.COMPANY_PORTAL, added, removed)
            self.ctx.audit(actor, operation, company_id, user_id)
            if added or removed:
                binding.changed_at = now()
                self.dao.company_users.save(binding)
                self.ctx.publish("UserRolesChanged", {"userId": user_id, "companyId": company_id,
                                                      "addedRoles": added, "removedRoles": removed})
            return CompanyUserModel.model_validate(self._view(binding))

    def remove_company_user(self, company_id: str, user_id: str, actor: Actor, as_osp: bool = False) -> None:
        """7.4 and, with `as_osp`, 7.14 (also `DISABLED`, without the limit "last Company Admin")."""
        operation = "removeUserAsOsp" if as_osp else "removeCompanyUser"
        with self.dao.lock(("company", company_id), ("account", user_id)):
            bindings = self.dao.company_users.list_of(user_id, company_id)
            current = next((b for b in bindings if b.status != BindingStatus.REMOVED), None)
            if current is None:
                if bindings:
                    return
                raise NotFoundException("no binding of the account to this company")
            if current.status == BindingStatus.DISABLED and not as_osp:
                raise InvalidStateException("the company is deactivated")
            if not as_osp and self._is_last_company_admin(company_id, user_id):
                raise LastCompanyAdminException("the company keeps at least one Company Admin")
            reason = RemovalReason.REMOVED_BY_OSP if as_osp else RemovalReason.REMOVED_BY_COMPANY
            self.unbind(current, reason, actor, operation)

    def set_user_app_roles(self, company_id: str, user_id: str, app_id: str, body: dict,
                           actor: Actor) -> AppRolesResult:
        """7.5"""
        iam, operation = self.ctx.iam, "setUserAppRoles"
        roles = self.ctx.validate.role_list(body, "roles", (), allow_empty=True)
        with self.dao.lock(("app", app_id), ("company", company_id), ("account", user_id)):
            self._binding_for_change(company_id, user_id)
            template = self.apps.template(app_id)
            unknown = sorted(set(roles) - {r["name"] for r in iam.client_roles(template.iam_client_uuid)})
            if unknown:
                raise UnknownAppRoleException(f"roles not on the template: {unknown}")
            targets = self.apps.target_clients(company_id, app_id)
            if not targets:
                raise NoActiveSubscriptionException("no active subscription with an active instance client")
            client_roles = {ic.id: {r["name"]: r for r in iam.client_roles(ic.iam_client_uuid)} for ic in targets}
            if any(set(roles) - set(names) for names in client_roles.values()):
                raise InvalidStateException("add-app-roles has not finished on every instance client")
            added: set[str] = set()
            removed: set[str] = set()
            try:
                for ic in targets:
                    current = {r["name"]: r for r in iam.client_role_mappings(user_id, ic.iam_client_uuid)}
                    to_add = [client_roles[ic.id][n] for n in roles if n not in current]
                    to_remove = [r for n, r in current.items() if n not in roles]
                    if to_add:
                        iam.add_client_role_mappings(user_id, ic.iam_client_uuid, to_add)
                        self.log_roles(actor, operation, user_id, company_id, RoleKind.APP,
                                       [r["name"] for r in to_add], [], ic)
                        added |= {r["name"] for r in to_add}
                    if to_remove:
                        iam.remove_client_role_mappings(user_id, ic.iam_client_uuid, to_remove)
                        self.log_roles(actor, operation, user_id, company_id, RoleKind.APP, [],
                                       [r["name"] for r in to_remove], ic)
                        removed |= {r["name"] for r in to_remove}
            finally:   # changes made before an iam-error are reported too (7.5)
                if added or removed:
                    self.ctx.audit(actor, operation, company_id, user_id)
                    self.ctx.publish("UserRolesChanged", {"userId": user_id, "companyId": company_id, "appId": app_id,
                                                          "addedRoles": sorted(added), "removedRoles": sorted(removed)})
        return AppRolesResult.model_validate({
            "userId": user_id, "appId": app_id, "roles": sorted(roles), "addedRoles": sorted(added),
            "removedRoles": sorted(removed), "instanceClients": [ic.ref() for ic in targets]})

    def get_company_app_roles(self, company_id: str, app_id: str, lang: str | None) -> CompanyAppRoles:
        """7.6"""
        roles = self.apps.template_roles(app_id, self.ctx.validate.lang(lang))
        if roles is None:
            raise NotFoundException(f"no client template for app {app_id}")
        targets = self.apps.target_clients(company_id, app_id)
        return CompanyAppRoles.model_validate({
            "appId": app_id, "templateExists": True, "roles": roles, "companyId": company_id,
            "assignable": bool(targets), "instanceClients": [ic.ref() for ic in targets]})

    def get_user_account(self, user_id: str) -> UserAccount:
        """7.12"""
        user = self.ctx.iam.get_user(user_id)
        if user is None:
            raise UserNotFoundException("account unknown in the Portal IAM")
        mappings = self._mappings(user_id)
        core = self._core_names(mappings)
        binding = self.dao.company_users.current_of(user_id)
        created = user.get("createdTimestamp")
        return UserAccount.model_validate({
            "userId": user_id, "givenName": user.get("firstName"), "familyName": user.get("lastName"),
            "enabled": user.get("enabled", True),
            "createdAt": dt.datetime.fromtimestamp(created / 1000, dt.UTC).isoformat() if created else None,
            "binding": self._view(binding) if binding else None,
            "portalRoles": sorted(core & set(self._company_roles())),
            "staffRoles": sorted(core & set(self._staff_roles())),
            "appRoles": self._app_roles_view(mappings)})

    # -- OSP staff (7.15, 7.16) -------------------------------------------------------------------
    def _staff_member(self, user: dict) -> dict:
        binding = self.dao.company_users.current_of(user["id"])
        return {"userId": user["id"], "givenName": user.get("firstName"), "familyName": user.get("lastName"),
                "enabled": user.get("enabled", True), "staffRoles": self.staff_roles(user["id"]),
                "companyId": binding.company_id if binding else None}

    def list_staff(self, page: int, size: int) -> Page[StaffMember]:
        """7.15"""
        found: dict[str, dict] = {}
        for role in self._staff_roles():
            found |= {u["id"]: u for u in self.users_with_role(role)}
        members = sorted(found.values(), key=lambda u: (u.get("lastName") or "", u.get("firstName") or "", u["id"]))
        return Page[StaffMember].model_validate(paginate(members, page, size, self._staff_member))

    def set_staff_roles(self, user_id: str, body: dict, actor: Actor) -> StaffMember:
        """7.16"""
        roles = self.ctx.validate.role_list(body, "staffRoles", self._staff_roles(), allow_empty=True)
        with self.dao.lock(DaoService.STAFF, ("account", user_id)):
            user = self.ctx.iam.get_user(user_id)
            if user is None:
                raise UserNotFoundException("account unknown in the Portal IAM")
            current = self.staff_roles(user_id)
            if not current and roles:
                binding = self.dao.company_users.current_of(user_id)
                if binding is None or binding.company_id != settings.get("ospCompanyId"):
                    raise StaffCompanyConflictException(
                        "only accounts bound to the OSP company get staff roles directly; invite others")
            admin = self.cfg.from_properties("staff.admin.role")
            if admin in current and admin not in roles and self.enabled_osp_admins() == {user_id}:
                raise LastOspAdminException("the installation keeps at least one OSP Admin")
            self.add_staff_roles(user_id, roles, actor, "setStaffRoles", replace=True)
            return StaffMember.model_validate(self._staff_member(self.ctx.iam.get_user(user_id) or user))

    def add_staff_roles(self, user_id: str, roles: list[str], actor: Actor, operation: str,
                        replace: bool = False) -> tuple[list[str], list[str]]:
        """Sets (`replace`) or extends the staff roles; logs and reports `OspStaffRolesChanged`."""
        current = self.staff_roles(user_id)
        wanted = roles if replace else current + [r for r in roles if r not in current]
        added, removed = self.set_roles(user_id, self._staff_roles(), wanted)
        self.log_roles(actor, operation, user_id, None, RoleKind.STAFF_PORTAL, added, removed)
        self.ctx.audit(actor, operation, None, user_id)
        if added or removed:
            self.ctx.publish("OspStaffRolesChanged", {"userId": user_id, "addedRoles": added, "removedRoles": removed})
        return added, removed

    # -- steps (8.8 to 8.10) ---------------------------------------------------------------------
    def assign_company_admin(self, input: dict) -> AssignCompanyAdminResult:
        """8.8"""
        v, dao, operation = self.ctx.validate, self.dao, "assign-company-admin"
        company_id = v.uuid(input, "companyId")
        bpn = v.bpn(input)
        user_id = v.text(input, "applicantSub")
        actor = Actor.process(input)
        admin = self.cfg.from_properties("company.admin.role")
        with dao.lock(("company", company_id), ("account", user_id)):
            company = dao.companies.get(company_id)
            if company is not None and company.bpn != bpn:
                raise ConflictException("the BPN differs from the stored one", retryable=False)
            if company is not None and company.status in (CompanyStatus.DISABLING, CompanyStatus.ENABLING):
                raise InvalidStateException(f"company status {company.status}", retryable=True)
            user = self.ctx.iam.get_user(user_id)
            if user is None:
                raise UserNotFoundException("account unknown in the Portal IAM", retryable=False)
            binding = dao.company_users.current_of(user_id)
            if binding is not None and binding.company_id != company_id:
                raise UserAlreadyBoundException("the account is bound to another company", retryable=False)
            if binding is None and company_id != settings.get("ospCompanyId") and self.has_staff_role(user_id):
                raise StaffCompanyConflictException("staff accounts bind only to the OSP company", retryable=False)
            if company is None:
                company = Company(company_id, bpn)
                dao.companies.save(company)
            elif company.status == CompanyStatus.DISABLED:   # return after a transfer (FRAMEWORK 5.6)
                self._set_company_status(company, CompanyStatus.ACTIVE)
            if binding is None:
                self.bind(user_id, company, [admin], JoinedVia.ONBOARDING, actor, operation,
                          given_name=user.get("firstName"), family_name=user.get("lastName"))
            else:
                restored = binding.status == BindingStatus.DISABLED
                if restored:
                    self._restore(binding, company, actor, operation)
                else:
                    self._set_company_attributes(self.ctx.iam.get_user(user_id) or user, company)
                added = [] if admin in self.portal_roles(user_id) else [admin]
                if added:
                    self.ctx.iam.add_client_role_mappings(user_id, self.ctx.core_uuid, [self.ctx.core_role(admin)])
                    self.log_roles(actor, operation, user_id, company_id, RoleKind.COMPANY_PORTAL, added, [])
                    self.ctx.audit(actor, operation, company_id, user_id)
                if restored:
                    self.ctx.publish("UserAssignedToCompany", {"userId": user_id, "companyId": company_id,
                                                               "via": str(JoinedVia.ONBOARDING),
                                                               "portalRoles": self.company_roles(user_id)})
                elif added:
                    self.ctx.publish("UserRolesChanged", {"userId": user_id, "companyId": company_id,
                                                          "addedRoles": added, "removedRoles": []})
            return AssignCompanyAdminResult(company_id=company_id, user_id=user_id,
                                            portal_roles=self.company_roles(user_id))

    def _user_ids(self, company_id: str, status: BindingStatus) -> list[str]:
        return sorted(b.user_id for b in self.dao.company_users.list_of_company(company_id, [status]))

    def disable_company_users(self, input: dict) -> CompanyUsersResult:
        """8.9"""
        company_id = self.ctx.validate.uuid(input, "companyId")
        actor, dao, operation = Actor.process(input), self.dao, "disable-company-users"
        if company_id == settings.get("ospCompanyId"):
            raise InvalidStateException("the OSP company is not deactivated by this step", retryable=False)
        with dao.lock(("company", company_id)):
            company = dao.companies.get(company_id)
            if company is None:
                return CompanyUsersResult(company_id=company_id, user_ids=[])
            if company.status == CompanyStatus.ENABLING:
                raise InvalidStateException("the company is being enabled", retryable=True)
            if company.status == CompanyStatus.ACTIVE:
                self._set_company_status(company, CompanyStatus.DISABLING)
                for inv in dao.invitations.list_all():
                    if inv.company_id == company_id and inv.status == InvitationStatus.OPEN:
                        inv.end(InvitationStatus.REVOKED, InvitationEndReason.COMPANY_DISABLED)
                        dao.invitations.save(inv)
                self.ctx.audit(actor, operation, company_id, company_id)
            if company.status == CompanyStatus.DISABLING:
                for binding in dao.company_users.list_of_company(company_id, [BindingStatus.ACTIVE]):
                    with dao.lock(("account", binding.user_id)):
                        self._suspend(binding, actor, operation)
                self._set_company_status(company, CompanyStatus.DISABLED)
                self.ctx.publish("CompanyUsersDisabled", {
                    "companyId": company_id, "userIds": self._user_ids(company_id, BindingStatus.DISABLED)})
            return CompanyUsersResult(company_id=company_id,
                                      user_ids=self._user_ids(company_id, BindingStatus.DISABLED))

    def enable_company_users(self, input: dict) -> CompanyUsersResult:
        """8.10"""
        company_id = self.ctx.validate.uuid(input, "companyId")
        actor, dao, operation = Actor.process(input), self.dao, "enable-company-users"
        with dao.lock(("company", company_id)):
            company = dao.companies.get(company_id)
            if company is None:
                return CompanyUsersResult(company_id=company_id, user_ids=[])
            if company.status == CompanyStatus.DISABLING:
                raise InvalidStateException("the company is being disabled", retryable=True)
            announce = company.status != CompanyStatus.ACTIVE
            if company.status == CompanyStatus.DISABLED:
                self._set_company_status(company, CompanyStatus.ENABLING)
            for binding in dao.company_users.list_of_company(company_id, [BindingStatus.DISABLED]):
                with dao.lock(("account", binding.user_id)):
                    self._restore(binding, company, actor, operation)
            user_ids = self._user_ids(company_id, BindingStatus.ACTIVE)
            if announce:
                self._set_company_status(company, CompanyStatus.ACTIVE)
                self.ctx.publish("CompanyUsersEnabled", {"companyId": company_id, "userIds": user_ids})
            return CompanyUsersResult(company_id=company_id, user_ids=user_ids)

    # -- query 9.4 --------------------------------------------------------------------------------
    def list_company_user_refs(self, company_id: str | None, portal_role: str | None,
                               status: list[str] | str | None) -> list[CompanyUserRef]:
        if not company_id:
            raise invalid("companyId is required")
        company_id = Validator.uuid({"companyId": company_id}, "companyId")
        wanted = statuses(status, BindingStatus, [BindingStatus.ACTIVE])
        found = self.dao.company_users.list_of_company(company_id, wanted)
        if portal_role:
            if portal_role not in self._company_roles():
                raise invalid(f"portalRole: one of {list(self._company_roles())}")
            with_role = {u["id"] for u in self.users_with_role(portal_role)}
            found = [b for b in found if b.user_id in with_role]
        return [CompanyUserRef(user_id=b.user_id, status=b.status) for b in sorted(found, key=lambda b: b.created_at)]
