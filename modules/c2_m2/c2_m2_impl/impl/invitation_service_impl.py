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
"""Invitations of kind `COMPANY` and `STAFF` (README 6.8, 6.9): operations 7.7 to 7.10 and
7.17 to 7.22, the bootstrap of the first OSP Admin and the cleanup of expired invitations."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from modules.c2_m2.c2_m2_api.exception import (CompanyNotActiveException, InvitationNotFoundException,
                                               InvitationNotOpenException, NameMismatchException, NotFoundException,
                                               StaffCompanyConflictException, TooManyInvitationsException,
                                               UserAlreadyBoundException)
from modules.c2_m2.c2_m2_api.model import (AcceptInvitationResult, Invitation as InvitationModel,
                                           InvitationWithCode, Page)
from modules.c2_m2.c2_m2_api.model.common import Actor
from modules.c2_m2.c2_m2_api.model.constants import (CompanyStatus, InvitationEndReason, InvitationKind,
                                                     InvitationStatus, JoinedVia)
from modules.c2_m2.c2_m2_api.service import InvitationService
from modules.c2_m2.c2_m2_impl.config.properties import as_bool, as_int, as_list
from modules.c2_m2.c2_m2_impl.context import Context, paginate, statuses
from modules.c2_m2.c2_m2_impl.dao import DaoService
from modules.c2_m2.c2_m2_impl.internal.model import Invitation, InvitationCode, NameCheck, now
from modules.c2_m2.c2_m2_impl.utils.validation_utils import invalid
from portal_common import settings

from .user_service_impl import UserServiceImpl


class InvitationServiceImpl(InvitationService):
    def __init__(self, ctx: Context, users: UserServiceImpl) -> None:
        self.ctx = ctx
        self.users = users

    @property
    def cfg(self):
        return self.ctx.config

    @property
    def dao(self) -> DaoService:
        return self.ctx.dao

    @staticmethod
    def _lock(kind: InvitationKind, company_id: str | None) -> tuple[str, str | None]:
        return ("company", company_id) if kind == InvitationKind.COMPANY else DaoService.STAFF

    def _roles_key(self, kind: InvitationKind) -> tuple[str, tuple[str, ...]]:
        if kind == InvitationKind.COMPANY:
            return "portalRoles", as_list(self.cfg.from_properties("company.portal.roles"))
        return "staffRoles", as_list(self.cfg.from_properties("staff.portal.roles"))

    def _find(self, kind: InvitationKind, company_id: str | None, invitation_id: str) -> Invitation:
        inv = self.dao.invitations.get(invitation_id)
        if inv is None or inv.kind != kind or inv.company_id != company_id:
            raise NotFoundException("invitation unknown")
        return inv

    def _end(self, inv: Invitation, status: InvitationStatus, reason: InvitationEndReason | None = None) -> None:
        inv.end(status, reason)
        self.dao.invitations.save(inv)

    # -- operations --------------------------------------------------------------------------------
    def create(self, kind: InvitationKind, company_id: str | None, body: dict, actor: Actor,
               operation: str) -> InvitationWithCode:
        """7.7, 7.17, 7.20: the code appears only in this response."""
        v = self.ctx.validate
        given, family = v.person_name(body, "givenName"), v.person_name(body, "familyName")
        key, allowed = self._roles_key(kind)
        roles = v.role_list(body, key, allowed)
        with self.dao.lock(self._lock(kind, company_id)):
            if kind == InvitationKind.COMPANY:
                self.users.ensure_company_active(company_id)
            open_now = [i for i in self.dao.invitations.list_of(kind, company_id)
                        if i.effective_status() == InvitationStatus.OPEN]
            max_open = as_int(self.cfg.from_properties("invitation.max.open"))
            if len(open_now) >= max_open:
                raise TooManyInvitationsException(f"at most {max_open} open invitations")
            code = InvitationCode.generate()
            inv = Invitation(kind, company_id, given, family, roles, InvitationCode.hash(code),
                             now() + self._ttl(), actor.sub)
            self.dao.invitations.save(inv)
            self.ctx.audit(actor, operation, company_id, inv.id)
            return InvitationWithCode.model_validate(inv.to_api() | {"code": code})

    def list(self, kind: InvitationKind, company_id: str | None, status: list[str] | None, page: int,
             size: int) -> Page[InvitationModel]:
        """7.8, 7.18, 7.21: newest first, never a code."""
        wanted = statuses(status, InvitationStatus, [InvitationStatus.OPEN])
        found = [i for i in self.dao.invitations.list_of(kind, company_id) if i.effective_status() in wanted]
        found.sort(key=lambda i: i.created_at, reverse=True)
        return Page[InvitationModel].model_validate(paginate(found, page, size, Invitation.to_api))

    def revoke(self, kind: InvitationKind, company_id: str | None, invitation_id: str, actor: Actor,
               operation: str) -> None:
        """7.9, 7.19, 7.22"""
        with self.dao.lock(self._lock(kind, company_id), ("invitation", invitation_id)):
            inv = self._find(kind, company_id, invitation_id)
            if inv.is_expired():
                self._end(inv, InvitationStatus.EXPIRED)
            if inv.status == InvitationStatus.REVOKED:
                return
            if inv.status != InvitationStatus.OPEN:
                raise InvitationNotOpenException(f"invitation is {inv.status}")
            self._end(inv, InvitationStatus.REVOKED, InvitationEndReason.REVOKED)
            self.ctx.audit(actor, operation, company_id, inv.id)

    def accept(self, body: dict, claims: dict) -> AcceptInvitationResult:
        """7.10 (scope `own`): the account of `sub` redeems the code."""
        code = body.get("code")
        if not isinstance(code, str) or not InvitationCode.PATTERN.match(code):
            raise invalid("code: 43 characters base64url")
        inv = self.dao.invitations.find_by_code_hash(InvitationCode.hash(code))
        if inv is None:
            raise InvitationNotFoundException("no invitation for this code")
        user_id, actor, operation = claims["sub"], Actor.person(claims), "acceptInvitation"
        with self.dao.lock(self._lock(inv.kind, inv.company_id), ("invitation", inv.id), ("account", user_id)):
            if inv.status == InvitationStatus.ACCEPTED and inv.accepted_by == user_id:
                return AcceptInvitationResult.model_validate(inv.accept_result())
            if inv.status != InvitationStatus.OPEN:
                raise InvitationNotOpenException(f"invitation is {inv.status}")
            if inv.is_expired():
                self._end(inv, InvitationStatus.EXPIRED)
                raise InvitationNotOpenException("invitation is EXPIRED")
            self._check_account(inv, user_id)
            if as_bool(self.cfg.from_properties("invitation.name.check")) and not NameCheck.matches(claims, inv):
                inv.failed_attempts += 1
                if inv.failed_attempts >= as_int(self.cfg.from_properties("invitation.max.failed.attempts")):
                    inv.end(InvitationStatus.REVOKED, InvitationEndReason.TOO_MANY_ATTEMPTS)
                self.dao.invitations.save(inv)
                raise NameMismatchException("the names in the token do not match the invitation")
            if inv.kind == InvitationKind.COMPANY:
                self.users.bind(user_id, self.dao.companies.get(inv.company_id), list(inv.roles),
                                JoinedVia.INVITATION, actor, operation, invitation_id=inv.id,
                                given_name=claims.get("given_name"), family_name=claims.get("family_name"))
            else:
                self.users.add_staff_roles(user_id, list(inv.roles), actor, operation)
            inv.end(InvitationStatus.ACCEPTED)
            inv.accepted_by, inv.accepted_at = user_id, now()
            self.dao.invitations.save(inv)
            self.ctx.audit(actor, operation, inv.company_id, inv.id)
            return AcceptInvitationResult.model_validate(inv.accept_result())

    def _check_account(self, inv: Invitation, user_id: str) -> None:
        """7.10 step 4"""
        binding = self.dao.company_users.current_of(user_id)
        osp_company = settings.get("ospCompanyId")
        if inv.kind == InvitationKind.COMPANY:
            if binding is not None:
                raise UserAlreadyBoundException("the account is already bound to a company")
            company = self.dao.companies.get(inv.company_id)
            if company is None or company.status != CompanyStatus.ACTIVE:
                raise CompanyNotActiveException("the company is not ACTIVE")
            if inv.company_id != osp_company and self.users.has_staff_role(user_id):
                raise StaffCompanyConflictException("staff accounts bind only to the OSP company")
        elif binding is not None and binding.company_id != osp_company:
            raise StaffCompanyConflictException("the account is bound to a company other than the OSP company")

    # -- cleanup and bootstrap ------------------------------------------------------------------------
    def expire_overdue(self) -> int:
        """Open invitations past `expires_at` become `EXPIRED` without names (6.8)."""
        overdue = [i for i in self.dao.invitations.list_all() if i.is_expired()]
        for inv in overdue:
            with self.dao.lock(self._lock(inv.kind, inv.company_id), ("invitation", inv.id)):
                if inv.is_expired():
                    self._end(inv, InvitationStatus.EXPIRED)
        return len(overdue)

    def _ttl(self) -> dt.timedelta:
        return dt.timedelta(hours=as_int(self.cfg.from_properties("invitation.ttl.hours")))

    def _bootstrap_file(self) -> Path | None:
        value = self.cfg.from_properties("bootstrap.admin.file")
        if not value:
            return None
        path = Path(value)
        return path if path.is_absolute() or path.exists() else settings.resolve_path(value)

    def bootstrap(self) -> Invitation | None:
        """6.9: the `STAFF` invitation of `BOOTSTRAP_ADMIN_FILE` while no enabled account is OSP Admin."""
        path = self._bootstrap_file()
        if path is None:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        with self.dao.lock(DaoService.STAFF):
            if self.dao.invitations.get(data["invitationId"]) is not None or self.users.enabled_osp_admins():
                return None
            expires = dt.datetime.fromisoformat(data["expiresAt"]) if data.get("expiresAt") \
                else now() + self._ttl()
            inv = Invitation(InvitationKind.STAFF, None, data["givenName"], data["familyName"],
                             list(data.get("roles") or [self.cfg.from_properties("staff.admin.role")]),
                             data["codeSha256"].lower(), expires, None, id=data["invitationId"])
            self.dao.invitations.save(inv)
            self.ctx.audit(Actor.system(), "bootstrap", None, inv.id)
            return inv
