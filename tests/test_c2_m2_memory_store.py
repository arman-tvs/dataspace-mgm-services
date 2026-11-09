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
"""The in-memory store of C2-M2 (README 4 `DATABASE_URL` empty): chosen without a database, rows as values,
transactions that roll back, and the filters and order of the SQL of the PostgreSQL DAOs."""
import datetime as dt

import pytest

from modules.c2_m2 import module
from modules.c2_m2.c2_m2_api.exception import LastCompanyAdminException
from modules.c2_m2.c2_m2_api.model.constants import (
    BindingStatus,
    InstanceClientStatus,
    InstanceKind,
    InvitationKind,
    JoinedVia,
)
from modules.c2_m2.c2_m2_impl.dao.impl import memory_dao_service
from modules.c2_m2.c2_m2_impl.dao.impl.memory_store import MemoryStore
from modules.c2_m2.c2_m2_impl.internal.model import AppInstanceClient, Company, CompanyUser, Invitation
from portal_common.problems import Problem

COMPANY = "c0000001-0000-4000-8000-000000000001"
OTHER = "c0000002-0000-4000-8000-000000000002"
T0 = dt.datetime(2026, 11, 9, 10, tzinfo=dt.UTC)


def client(id_: str, kind: InstanceKind, status: InstanceClientStatus, minutes: int) -> AppInstanceClient:
    return AppInstanceClient(id=id_, app_id="app", instance_kind=kind, offer_subscription_id=f"sub-{id_}",
                             customer_company_id=None, iam_client_id=f"iam-{id_}", instance_url="https://x.example",
                             status=status, created_at=T0 + dt.timedelta(minutes=minutes))


def test_without_a_database_the_module_uses_the_memory_store(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    module.reset()
    assert type(module.current().ctx.dao.db).__name__ == "MemoryStore"


def test_rows_are_values_a_change_counts_only_when_saved():
    dao = memory_dao_service()
    dao.companies.save(Company(COMPANY, "BPNL0000000001AB"))
    read = dao.companies.get(COMPANY)
    assert read is not None
    read.bpn = "changed"
    assert dao.companies.get(COMPANY).bpn == "BPNL0000000001AB"
    dao.companies.save(read)
    assert dao.companies.get(COMPANY).bpn == "changed"


def test_a_failing_transaction_is_rolled_back_but_the_client_number_is_not():
    dao = memory_dao_service()
    first = dao.instance_clients.next_client_number()
    with pytest.raises(RuntimeError), dao.lock(("company", COMPANY)):
        dao.companies.save(Company(COMPANY, None))
        dao.instance_clients.next_client_number()
        raise RuntimeError("the IAM call failed")
    assert dao.companies.get(COMPANY) is None
    assert dao.instance_clients.next_client_number() == first + 2      # a sequence, as in PostgreSQL


def test_a_business_error_keeps_the_writes_as_postgres_commits_then():
    """PostgresDatabase.transaction commits on C2M2BaseException and Problem and re-raises; the memory store too."""
    dao = memory_dao_service()
    with pytest.raises(LastCompanyAdminException), dao.lock(("company", COMPANY)):
        dao.companies.save(Company(COMPANY, None))
        raise LastCompanyAdminException("the company keeps at least one Company Admin")
    assert dao.companies.get(COMPANY) is not None
    with pytest.raises(Problem), dao.lock(("company", OTHER)):
        dao.companies.save(Company(OTHER, None))
        raise Problem("c2-m2", 409, "conflict")
    assert dao.companies.get(OTHER) is not None


def test_nested_transactions_join_the_outer_one():
    store = MemoryStore()
    dao = memory_dao_service()
    with store.transaction(), store.transaction():
        pass
    with pytest.raises(ValueError), dao.lock(("company", COMPANY), ("account", "u1")):
        dao.companies.save(Company(COMPANY, None))
        with dao.lock(("invitation", "i1")):
            dao.companies.save(Company(OTHER, None))
        raise ValueError
    assert dao.companies.get(COMPANY) is None and dao.companies.get(OTHER) is None


def test_instance_clients_filters_and_order_as_the_sql():
    dao = memory_dao_service()
    dao.instance_clients.save(client("b", InstanceKind.SUBSCRIPTION, InstanceClientStatus.ACTIVE, 2))
    dao.instance_clients.save(client("a", InstanceKind.SINGLE, InstanceClientStatus.DISABLED, 1))
    dao.instance_clients.save(client("c", InstanceKind.SINGLE, InstanceClientStatus.ACTIVE, 3))
    assert [c.id for c in dao.instance_clients.list_of_app("app")] == ["a", "b", "c"]     # ORDER BY created_at
    assert dao.instance_clients.find_single("app").id == "c"                               # not DISABLED
    assert dao.instance_clients.find_by_subscription("sub-b").id == "b"
    assert dao.instance_clients.find_by_iam_client_id("iam-a").id == "a"


def test_company_users_current_binding_and_statuses():
    dao = memory_dao_service()
    old = CompanyUser("u1", COMPANY, JoinedVia.INVITATION, status=BindingStatus.REMOVED, created_at=T0)
    now = CompanyUser("u1", COMPANY, JoinedVia.INVITATION, created_at=T0 + dt.timedelta(days=1))
    other = CompanyUser("u2", OTHER, JoinedVia.ONBOARDING)
    for binding in (now, old, other):
        dao.company_users.save(binding)
    assert dao.company_users.current_of("u1").id == now.id                 # ACTIVE or DISABLED only
    assert [b.id for b in dao.company_users.list_of("u1", COMPANY)] == [old.id, now.id]   # oldest first
    assert {b.user_id for b in dao.company_users.list_of_company(None, [BindingStatus.ACTIVE])} == {"u1", "u2"}
    assert [b.user_id for b in dao.company_users.list_of_company(OTHER, [BindingStatus.ACTIVE])] == ["u2"]


def test_invitations_by_kind_and_company_including_staff_without_company():
    dao = memory_dao_service()
    expires = T0 + dt.timedelta(days=7)
    staff = Invitation(InvitationKind.STAFF, None, None, None, ["OSP Reviewer"], "h-staff", expires, None)
    company = Invitation(InvitationKind.COMPANY, COMPANY, None, None, ["Member"], "h-company", expires, None)
    dao.invitations.save(staff)
    dao.invitations.save(company)
    assert [i.id for i in dao.invitations.list_of(InvitationKind.STAFF, None)] == [staff.id]   # IS NOT DISTINCT FROM
    assert [i.id for i in dao.invitations.list_of(InvitationKind.COMPANY, COMPANY)] == [company.id]
    assert dao.invitations.find_by_code_hash("h-company").id == company.id
