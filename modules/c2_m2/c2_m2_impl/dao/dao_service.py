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

import contextlib
from collections.abc import Iterator

from modules.c2_m2.c2_m2_impl.internal.services import Database

from .app_client_template_dao import AppClientTemplateDao
from .app_instance_client_dao import AppInstanceClientDao
from .audit_log_dao import AuditLogDao
from .company_dao import CompanyDao
from .company_user_dao import CompanyUserDao
from .invitation_dao import InvitationDao
from .role_assignment_log_dao import RoleAssignmentLogDao


class DaoService:
    """The one way of the service implementations to the database `c2_m2`: every DAO, and the locks of 6.14
    taken through the DAOs in the fixed order app, company, staff, invitation, account."""

    ORDER = ("app", "company", "staff", "invitation", "account")
    STAFF = ("staff", "all")

    def __init__(self, db: Database, templates: AppClientTemplateDao, instance_clients: AppInstanceClientDao,
                 companies: CompanyDao, company_users: CompanyUserDao, invitations: InvitationDao,
                 audit_log: AuditLogDao, role_log: RoleAssignmentLogDao) -> None:
        self.db = db
        self.templates = templates
        self.instance_clients = instance_clients
        self.companies = companies
        self.company_users = company_users
        self.invitations = invitations
        self.audit_log = audit_log
        self.role_log = role_log
        self._lockers = {"app": templates.lock, "company": companies.lock,
                         "staff": lambda _: invitations.lock_staff(), "invitation": invitations.lock,
                         "account": company_users.lock_account}

    def ordered(self, keys: tuple[tuple[str, str | None], ...]) -> list[tuple[str, str]]:
        return sorted({(k, v) for k, v in keys if v is not None}, key=lambda k: (self.ORDER.index(k[0]), k[1]))

    @contextlib.contextmanager
    def lock(self, *keys: tuple[str, str | None]) -> Iterator[None]:
        """Holds the given locks (keys with value None are skipped) until the transaction ends."""
        with self.db.transaction(), contextlib.ExitStack() as held:
            for kind, key in self.ordered(keys):
                held.enter_context(self._lockers[kind](key))
            yield
