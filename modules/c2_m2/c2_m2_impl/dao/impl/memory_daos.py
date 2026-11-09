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
"""The DAOs of C2-M2 on the in-memory store: the same filters and order as the SQL of the PostgreSQL DAOs."""
from __future__ import annotations

from collections.abc import Iterable
from contextlib import AbstractContextManager

from modules.c2_m2.c2_m2_api.model.constants import BindingStatus, InstanceClientStatus, InstanceKind, InvitationKind
from modules.c2_m2.c2_m2_impl.dao.app_client_template_dao import AppClientTemplateDao
from modules.c2_m2.c2_m2_impl.dao.app_instance_client_dao import AppInstanceClientDao
from modules.c2_m2.c2_m2_impl.dao.audit_log_dao import AuditLogDao
from modules.c2_m2.c2_m2_impl.dao.company_dao import CompanyDao
from modules.c2_m2.c2_m2_impl.dao.company_user_dao import CompanyUserDao
from modules.c2_m2.c2_m2_impl.dao.invitation_dao import InvitationDao
from modules.c2_m2.c2_m2_impl.dao.role_assignment_log_dao import RoleAssignmentLogDao
from modules.c2_m2.c2_m2_impl.internal.model import (
    AppClientTemplate,
    AppInstanceClient,
    AuditLogEntry,
    Company,
    CompanyUser,
    Invitation,
    RoleAssignmentLogEntry,
)

from .memory_store import MemoryStore, Table


class MemoryAppClientTemplateDao(AppClientTemplateDao):
    def __init__(self, store: MemoryStore) -> None:
        self.store, self.table = store, Table[AppClientTemplate](store, lambda t: t.app_id)

    def lock(self, app_id: str) -> AbstractContextManager[None]:
        return self.store.lock(f"c2_m2:app:{app_id}")

    def get(self, app_id: str) -> AppClientTemplate | None:
        return self.table.get(app_id)

    def save(self, template: AppClientTemplate) -> None:
        self.table.save(template)


class MemoryAppInstanceClientDao(AppInstanceClientDao):
    def __init__(self, store: MemoryStore) -> None:
        self.store, self.table = store, Table[AppInstanceClient](store, lambda c: c.id)

    def _first(self, rows: list[AppInstanceClient]) -> AppInstanceClient | None:
        return rows[0] if rows else None

    def _sorted(self, rows: list[AppInstanceClient]) -> list[AppInstanceClient]:
        return sorted(rows, key=lambda c: c.created_at)          # ORDER BY created_at

    def get(self, instance_client_id: str) -> AppInstanceClient | None:
        return self.table.get(instance_client_id)

    def save(self, instance_client: AppInstanceClient) -> None:
        self.table.save(instance_client)

    def find_by_subscription(self, offer_subscription_id: str) -> AppInstanceClient | None:
        return self._first(self.table.where(lambda c: c.offer_subscription_id == offer_subscription_id))

    def find_single(self, app_id: str) -> AppInstanceClient | None:
        return self._first(self.table.where(lambda c: c.app_id == app_id and c.instance_kind == InstanceKind.SINGLE
                                            and c.status != InstanceClientStatus.DISABLED))

    def find_by_iam_client_id(self, iam_client_id: str) -> AppInstanceClient | None:
        return self._first(self.table.where(lambda c: c.iam_client_id == iam_client_id))

    def list_of_app(self, app_id: str) -> list[AppInstanceClient]:
        return self._sorted(self.table.where(lambda c: c.app_id == app_id))

    def list_all(self) -> list[AppInstanceClient]:
        return self._sorted(self.table.where(lambda c: True))

    def next_client_number(self) -> int:
        return self.store.next_number()


class MemoryCompanyDao(CompanyDao):
    def __init__(self, store: MemoryStore) -> None:
        self.store, self.table = store, Table[Company](store, lambda c: c.company_id)

    def lock(self, company_id: str) -> AbstractContextManager[None]:
        return self.store.lock(f"c2_m2:company:{company_id}")

    def get(self, company_id: str) -> Company | None:
        return self.table.get(company_id)

    def save(self, company: Company) -> None:
        self.table.save(company)


class MemoryCompanyUserDao(CompanyUserDao):
    def __init__(self, store: MemoryStore) -> None:
        self.store, self.table = store, Table[CompanyUser](store, lambda b: b.id)

    def lock_account(self, user_id: str) -> AbstractContextManager[None]:
        return self.store.lock(f"c2_m2:account:{user_id}")

    def save(self, binding: CompanyUser) -> None:
        self.table.save(binding)

    def current_of(self, user_id: str) -> CompanyUser | None:
        rows = self.table.where(lambda b: b.user_id == user_id
                                and b.status in (BindingStatus.ACTIVE, BindingStatus.DISABLED))
        return rows[0] if rows else None

    def list_of(self, user_id: str, company_id: str) -> list[CompanyUser]:
        rows = self.table.where(lambda b: b.user_id == user_id and b.company_id == company_id)
        return sorted(rows, key=lambda b: b.created_at)          # ORDER BY created_at

    def list_of_company(self, company_id: str | None, statuses: Iterable[BindingStatus]) -> list[CompanyUser]:
        wanted = {str(s) for s in statuses}
        return self.table.where(lambda b: str(b.status) in wanted
                                and (company_id is None or b.company_id == company_id))


class MemoryInvitationDao(InvitationDao):
    def __init__(self, store: MemoryStore) -> None:
        self.store, self.table = store, Table[Invitation](store, lambda i: i.id)

    def lock(self, invitation_id: str) -> AbstractContextManager[None]:
        return self.store.lock(f"c2_m2:invitation:{invitation_id}")

    def lock_staff(self) -> AbstractContextManager[None]:
        return self.store.lock("c2_m2:staff")

    def get(self, invitation_id: str) -> Invitation | None:
        return self.table.get(invitation_id)

    def save(self, invitation: Invitation) -> None:
        self.table.save(invitation)

    def find_by_code_hash(self, code_hash: str) -> Invitation | None:
        rows = self.table.where(lambda i: i.code_hash == code_hash)
        return rows[0] if rows else None

    def list_of(self, kind: InvitationKind, company_id: str | None) -> list[Invitation]:
        return self.table.where(lambda i: str(i.kind) == str(kind) and i.company_id == company_id)

    def list_all(self) -> list[Invitation]:
        return self.table.where(lambda i: True)


class MemoryAuditLogDao(AuditLogDao):
    def __init__(self, store: MemoryStore) -> None:
        self.table = Table[AuditLogEntry](store, lambda e: e.id)

    def add(self, entry: AuditLogEntry) -> None:
        self.table.save(entry)

    def list_all(self) -> list[AuditLogEntry]:
        return sorted(self.table.where(lambda e: True), key=lambda e: e.occurred_at)   # ORDER BY occurred_at


class MemoryRoleAssignmentLogDao(RoleAssignmentLogDao):
    def __init__(self, store: MemoryStore) -> None:
        self.table = Table[RoleAssignmentLogEntry](store, lambda e: e.id)

    def add(self, entry: RoleAssignmentLogEntry) -> None:
        self.table.save(entry)

    def list_all(self) -> list[RoleAssignmentLogEntry]:
        return sorted(self.table.where(lambda e: True), key=lambda e: e.occurred_at)   # ORDER BY occurred_at
