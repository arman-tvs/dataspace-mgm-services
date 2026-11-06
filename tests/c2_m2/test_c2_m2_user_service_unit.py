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
"""Unit tests of `UserServiceImpl` (C2-M2 README 6.5 to 6.12, 7.1 to 7.6, 7.11 to 7.16, 8.8 to 8.10, 9.4) and of
the neighbour gateways. No database, no Keycloak, no neighbour module: every DAO, the `Database`, the Portal IAM,
C3-M1, C10-M1, the app client service and the event relay are mocks. `DaoService` and `Context` are real, so the
lock order of 6.14 and the role lookups of 6.12.2 are tested too."""
from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, call, create_autospec

import pytest

from modules.c2_m2.c2_m2_api.exception import (CompanyNotActiveException, ConflictException, IamErrorException,
                                               InvalidStateException, LastCompanyAdminException,
                                               LastOspAdminException, NoActiveSubscriptionException,
                                               NotFoundException, StaffCompanyConflictException,
                                               UnknownAppRoleException, UpstreamErrorException,
                                               UserAlreadyBoundException, UserNotFoundException,
                                               ValidationException)
from modules.c2_m2.c2_m2_api.model.constants import (ActorType, BindingStatus, CompanyStatus, InstanceClientStatus,
                                                     InstanceKind, InvitationEndReason, InvitationStatus, JoinedVia,
                                                     RemovalReason, RoleKind)
from modules.c2_m2.c2_m2_api.model.common import Actor
from modules.c2_m2.c2_m2_impl.config import Config
from modules.c2_m2.c2_m2_impl.context import Context
from modules.c2_m2.c2_m2_impl.dao import (AppClientTemplateDao, AppInstanceClientDao, AuditLogDao, CompanyDao,
                                          CompanyUserDao, DaoService, InvitationDao, RoleAssignmentLogDao)
from modules.c2_m2.c2_m2_impl.impl import (AppClientServiceImpl, CompanyProfileGatewayImpl,
                                           SubscriptionsGatewayImpl, UserServiceImpl)
from modules.c2_m2.c2_m2_impl.internal.model import (AppClientTemplate, AppInstanceClient, Company, CompanyUser,
                                                     SuspendedRoles)
from modules.c2_m2.c2_m2_impl.internal.services import (CompanyProfileGateway, Database, PortalIam,
                                                        SubscriptionsGateway)
from portal_common.problems import Problem

# Test data of FRAMEWORK 7a
OSP = "11111111-1111-4111-8111-111111111111"
MASCHINENBAU, BPN_M = "c0000001-0000-4000-8000-000000000001", "BPNLIUK2REMLK3F4"
LOGISTIK, BPN_L = "c0000002-0000-4000-8000-000000000002", "BPNL00000000U2LG"
ERIKA, MAX, HANS = ("5a1c0001-0000-4000-8000-000000000001", "5a1c0002-0000-4000-8000-000000000002",
                    "5a1c0003-0000-4000-8000-000000000003")
APP = "6f1c2a4e-8b0d-4c55-9a3e-2d7b1f0c9e11"
PROCESS, STEP_RUN = "9a000000-0000-4000-8000-000000000001", "9b000000-0000-4000-8000-000000000001"

CORE_UUID, TEMPLATE_UUID, IC_UUID = "uuid-portal-core", "uuid-template", "uuid-instance-1"
IC_CLIENT_ID = "app-1"
PORTAL_ROLES = ("Company Admin", "IT Admin", "Member", "OSP Reviewer", "OSP Admin", "Applicant")
APP_ROLES = ("Viewer", "Editor")

ACTOR = Actor.person({"sub": ERIKA, "company_id": MASCHINENBAU})


def role(name: str, prefix: str = "core") -> dict:
    return {"id": f"{prefix}-{name}", "name": name}


def mappings(*core: str, app: tuple[str, ...] = ()) -> dict:
    """Keycloak `role-mappings` of an account: portal roles on `portal-core`, app roles on the instance client."""
    client_mappings = {"portal-core": {"id": CORE_UUID, "mappings": [role(n) for n in core]}}
    if app:
        client_mappings[IC_CLIENT_ID] = {"id": IC_UUID, "mappings": [role(n, "app") for n in app]}
    return {"clientMappings": client_mappings}


def keycloak_user(user_id: str = ERIKA, given: str = "Erika", family: str = "Mustermann", **extra) -> dict:
    return {"id": user_id, "firstName": given, "lastName": family, "enabled": True, "attributes": {}, **extra}


def instance_client(status: InstanceClientStatus = InstanceClientStatus.ACTIVE) -> AppInstanceClient:
    return AppInstanceClient(id="ic-1", app_id=APP, instance_kind=InstanceKind.SUBSCRIPTION,
                             offer_subscription_id="sub-1", customer_company_id=MASCHINENBAU,
                             iam_client_id=IC_CLIENT_ID, instance_url="https://app.example.org",
                             status=status, iam_client_uuid=IC_UUID)


def binding(user_id: str = ERIKA, company_id: str = MASCHINENBAU, status: BindingStatus = BindingStatus.ACTIVE,
            **extra) -> CompanyUser:
    return CompanyUser(user_id, company_id, JoinedVia.ONBOARDING, given_name="Erika", family_name="Mustermann",
                       status=status, **extra)


def step(**fields) -> dict:
    return {"processId": PROCESS, "stepRunId": STEP_RUN, **fields}


class Harness:
    """`UserServiceImpl` wired to mocks; `iam`, `dao.*`, `apps`, `profiles`, `subscriptions` and `published` are
    the mocks the tests configure and inspect."""

    def __init__(self) -> None:
        self.db = create_autospec(Database, instance=True)
        self.dao = DaoService(
            self.db,
            templates=create_autospec(AppClientTemplateDao, instance=True),
            instance_clients=create_autospec(AppInstanceClientDao, instance=True),
            companies=create_autospec(CompanyDao, instance=True),
            company_users=create_autospec(CompanyUserDao, instance=True),
            invitations=create_autospec(InvitationDao, instance=True),
            audit_log=create_autospec(AuditLogDao, instance=True),
            role_log=create_autospec(RoleAssignmentLogDao, instance=True))
        self.iam = create_autospec(PortalIam, instance=True)
        self.profiles = create_autospec(CompanyProfileGateway, instance=True)
        self.subscriptions = create_autospec(SubscriptionsGateway, instance=True)
        self.ctx = Context(Config(), self.iam, self.dao, self.subscriptions, self.profiles)
        self.published = MagicMock(name="publish")
        self.ctx.publish = self.published   # instead of the event relay (FRAMEWORK 6)
        self.apps = create_autospec(AppClientServiceImpl, instance=True)
        self.service = UserServiceImpl(self.ctx, self.apps)

        # Lock calls of every DAO in one list, to check the order of 6.14
        self.locks = MagicMock(name="locks")
        self.dao.companies.lock.side_effect = lambda k: self._lock("company", k)
        self.dao.company_users.lock_account.side_effect = lambda k: self._lock("account", k)
        self.dao.templates.lock.side_effect = lambda k: self._lock("app", k)
        self.dao.invitations.lock.side_effect = lambda k: self._lock("invitation", k)
        self.dao.invitations.lock_staff.side_effect = lambda: self._lock("staff", None)

        # Portal IAM defaults: portal-core exists with every portal role, accounts have no roles
        self.iam.find_client.return_value = {"id": CORE_UUID, "clientId": "portal-core"}
        self.iam.client_roles.side_effect = self._client_roles
        self.iam.role_mappings.return_value = mappings()
        self.iam.users_with_client_role.return_value = []
        self.iam.get_user.side_effect = lambda uid: keycloak_user(uid)

        # DAO defaults: empty tables
        self.dao.companies.get.return_value = None
        self.dao.company_users.current_of.return_value = None
        self.dao.company_users.list_of.return_value = []
        self.dao.company_users.list_of_company.return_value = []
        self.dao.instance_clients.find_by_iam_client_id.side_effect = (
            lambda cid: instance_client() if cid == IC_CLIENT_ID else None)
        self.dao.invitations.list_all.return_value = []

    def _lock(self, kind: str, key: str | None) -> MagicMock:
        self.locks(kind, key)
        return MagicMock()   # context manager

    @staticmethod
    def _client_roles(uuid: str) -> list[dict]:
        if uuid == CORE_UUID:
            return [role(n) for n in PORTAL_ROLES]
        return [role(n, "app") for n in APP_ROLES]

    def admins(self, *user_ids: str) -> None:
        """Accounts with `Company Admin` (and `OSP Admin`) in the Portal IAM."""
        self.iam.users_with_client_role.side_effect = lambda _uuid, name: [
            {"id": u, "enabled": True} for u in user_ids] if name in ("Company Admin", "OSP Admin") else []

    def events(self, event_type: str) -> list[dict]:
        return [c.args[1] for c in self.published.call_args_list if c.args[0] == event_type]

    def saved_bindings(self) -> list[CompanyUser]:
        return [c.args[0] for c in self.dao.company_users.save.call_args_list]

    def role_log(self) -> list[tuple[str, str, RoleKind]]:
        return [(e.action, e.role_name, e.role_kind) for e in (c.args[0] for c in self.dao.role_log.add.call_args_list)]


@pytest.fixture
def h() -> Harness:
    return Harness()


# -- reading the Portal IAM (6.12.2) -------------------------------------------------------------------
def test_roles_are_split_into_company_and_staff_roles(h):
    h.iam.role_mappings.return_value = mappings("Company Admin", "OSP Reviewer", "Applicant")

    assert h.service.portal_roles(ERIKA) == {"Company Admin", "OSP Reviewer", "Applicant"}
    assert h.service.company_roles(ERIKA) == ["Company Admin"]
    assert h.service.staff_roles(ERIKA) == ["OSP Reviewer"]
    assert h.service.has_staff_role(ERIKA)


def test_core_client_is_looked_up_once_and_unknown_role_is_iam_error(h):
    assert h.ctx.core_role("Member") == role("Member")
    assert h.ctx.core_role("IT Admin") == role("IT Admin")
    h.iam.find_client.assert_called_once_with("portal-core")

    with pytest.raises(IamErrorException):
        h.ctx.core_role("No Such Role")


def test_missing_core_client_is_iam_error(h):
    h.iam.find_client.return_value = None
    with pytest.raises(IamErrorException):
        _ = h.ctx.core_uuid


# -- company row (6.6) --------------------------------------------------------------------------------
def test_ensure_company_active_uses_the_stored_row(h):
    h.dao.companies.get.return_value = Company(MASCHINENBAU, BPN_M)

    assert h.service.ensure_company_active(MASCHINENBAU).bpn == BPN_M
    h.profiles.company.assert_not_called()


def test_ensure_company_active_rejects_a_disabled_row(h):
    h.dao.companies.get.return_value = Company(MASCHINENBAU, BPN_M, status=CompanyStatus.DISABLED)
    with pytest.raises(CompanyNotActiveException):
        h.service.ensure_company_active(MASCHINENBAU)


def test_ensure_company_active_asks_c3_m1_and_stores_the_row(h):
    h.profiles.company.return_value = {"id": MASCHINENBAU, "status": "ACTIVE", "bpn": BPN_M}

    company = h.service.ensure_company_active(MASCHINENBAU)

    h.profiles.company.assert_called_once_with(MASCHINENBAU)
    h.dao.companies.save.assert_called_once_with(company)
    assert (company.company_id, company.bpn, company.status) == (MASCHINENBAU, BPN_M, CompanyStatus.ACTIVE)


@pytest.mark.parametrize("profile", [None, {"status": "PENDING", "bpn": BPN_M}, {"status": "ACTIVE", "bpn": None}])
def test_ensure_company_active_rejects_unknown_inactive_or_bpn_less_companies(h, profile):
    h.profiles.company.return_value = profile
    with pytest.raises(CompanyNotActiveException):
        h.service.ensure_company_active(MASCHINENBAU)
    h.dao.companies.save.assert_not_called()


# -- bind (6.12.1) ------------------------------------------------------------------------------------
def test_bind_sets_attributes_roles_binding_logs_and_event(h):
    company = Company(MASCHINENBAU, BPN_M)

    result = h.service.bind(MAX, company, ["Member"], JoinedVia.INVITATION, ACTOR, "acceptInvitation",
                            invitation_id="inv-1", given_name="Max", family_name="Mustermann")

    updated = h.iam.update_user.call_args.args[1]
    assert updated["attributes"] == {"company_id": [MASCHINENBAU], "bpn": [BPN_M]} and updated["enabled"] is True
    h.iam.add_client_role_mappings.assert_called_once_with(MAX, CORE_UUID, [role("Member")])
    h.iam.remove_client_role_mappings.assert_not_called()
    assert h.saved_bindings() == [result]
    assert (result.user_id, result.company_id, result.joined_via, result.invitation_id) == (
        MAX, MASCHINENBAU, JoinedVia.INVITATION, "inv-1")
    assert h.role_log() == [("ADDED", "Member", RoleKind.COMPANY_PORTAL)]
    h.dao.audit_log.add.assert_called_once()
    assert h.events("UserAssignedToCompany") == [
        {"userId": MAX, "companyId": MASCHINENBAU, "via": "INVITATION", "portalRoles": ["Member"]}]


def test_bind_unknown_account(h):
    h.iam.get_user.side_effect = None
    h.iam.get_user.return_value = None
    with pytest.raises(UserNotFoundException):
        h.service.bind(MAX, Company(MASCHINENBAU, BPN_M), ["Member"], JoinedVia.INVITATION, ACTOR, "op")
    h.dao.company_users.save.assert_not_called()
    h.published.assert_not_called()


def test_bind_skips_update_user_when_attributes_already_match(h):
    h.iam.get_user.side_effect = lambda uid: keycloak_user(
        uid, attributes={"company_id": [MASCHINENBAU], "bpn": [BPN_M]})
    h.iam.role_mappings.return_value = mappings("Member")

    h.service.bind(MAX, Company(MASCHINENBAU, BPN_M), ["Member"], JoinedVia.INVITATION, ACTOR, "op")

    h.iam.update_user.assert_not_called()
    h.iam.add_client_role_mappings.assert_not_called()


# -- 7.1 / 7.11 list, 7.2 detail ----------------------------------------------------------------------
def test_list_company_users_sorts_by_name_and_pages(h):
    rows = [CompanyUser(u, MASCHINENBAU, JoinedVia.INVITATION, given_name=g, family_name=f)
            for u, g, f in ((MAX, "Max", "Zeller"), (ERIKA, "Erika", "Abel"), (HANS, "Hans", "Meier"))]
    h.dao.company_users.list_of_company.return_value = rows
    h.iam.role_mappings.return_value = mappings("Member", "Applicant")

    page = h.service.list_company_users(MASCHINENBAU, None, page=0, size=2).model_dump(by_alias=True)

    h.dao.company_users.list_of_company.assert_called_once_with(
        MASCHINENBAU, {BindingStatus.ACTIVE, BindingStatus.DISABLED})
    assert [i["familyName"] for i in page["items"]] == ["Abel", "Meier"]
    assert page["items"][0]["portalRoles"] == ["Member"]
    assert (page["page"], page["size"], page["total"]) == (0, 2, 3)


def test_list_company_users_rejects_an_unknown_status(h):
    with pytest.raises(ValidationException):
        h.service.list_company_users(MASCHINENBAU, ["SLEEPING"], 0, 20)


def test_get_company_user_with_app_roles(h):
    h.dao.company_users.current_of.return_value = binding()
    h.iam.role_mappings.return_value = mappings("Company Admin", "Applicant", app=("Viewer",))

    detail = h.service.get_company_user(MASCHINENBAU, ERIKA).model_dump(by_alias=True)

    assert detail["portalRoles"] == ["Company Admin"]
    assert detail["appRoles"] == [{"appId": APP, "appInstanceClientId": "ic-1", "iamClientId": IC_CLIENT_ID,
                                   "instanceClientStatus": "ACTIVE", "roles": ["Viewer"]}]


@pytest.mark.parametrize("current", [None, binding(company_id=LOGISTIK)])
def test_get_company_user_of_another_or_no_company_is_404(h, current):
    h.dao.company_users.current_of.return_value = current
    with pytest.raises(NotFoundException):
        h.service.get_company_user(MASCHINENBAU, ERIKA)


# -- 7.3 / 7.13 portal roles ----------------------------------------------------------------------------
def test_set_portal_roles_adds_and_removes_and_takes_locks_in_order(h):
    h.dao.company_users.list_of.return_value = [binding(MAX)]
    h.iam.role_mappings.return_value = mappings("Member", "Applicant")

    result = h.service.set_company_user_portal_roles(MASCHINENBAU, MAX, {"portalRoles": ["IT Admin"]}, ACTOR)

    assert h.locks.call_args_list == [call("company", MASCHINENBAU), call("account", MAX)]
    h.db.transaction.assert_called_once()
    h.iam.add_client_role_mappings.assert_called_once_with(MAX, CORE_UUID, [role("IT Admin")])
    h.iam.remove_client_role_mappings.assert_called_once_with(MAX, CORE_UUID, [role("Member")])
    assert h.role_log() == [("ADDED", "IT Admin", RoleKind.COMPANY_PORTAL),
                            ("REMOVED", "Member", RoleKind.COMPANY_PORTAL)]
    assert h.events("UserRolesChanged") == [{"userId": MAX, "companyId": MASCHINENBAU,
                                             "addedRoles": ["IT Admin"], "removedRoles": ["Member"]}]
    assert result.user_id == MAX


def test_set_portal_roles_without_change_publishes_nothing(h):
    h.dao.company_users.list_of.return_value = [binding(MAX)]
    h.iam.role_mappings.return_value = mappings("Member")

    h.service.set_company_user_portal_roles(MASCHINENBAU, MAX, {"portalRoles": ["Member"]}, ACTOR)

    h.iam.add_client_role_mappings.assert_not_called()
    h.iam.remove_client_role_mappings.assert_not_called()
    h.published.assert_not_called()


def test_last_company_admin_keeps_the_role(h):
    h.dao.company_users.list_of.return_value = [binding()]
    h.dao.company_users.list_of_company.return_value = [binding()]
    h.iam.role_mappings.return_value = mappings("Company Admin")
    h.admins(ERIKA)

    with pytest.raises(LastCompanyAdminException):
        h.service.set_company_user_portal_roles(MASCHINENBAU, ERIKA, {"portalRoles": ["Member"]}, ACTOR)
    h.iam.remove_client_role_mappings.assert_not_called()


def test_osp_may_remove_the_last_company_admin(h):
    h.dao.company_users.list_of.return_value = [binding()]
    h.iam.role_mappings.return_value = mappings("Company Admin")
    h.admins(ERIKA)

    h.service.set_company_user_portal_roles(MASCHINENBAU, ERIKA, {"portalRoles": ["Member"]}, ACTOR, as_osp=True)

    h.iam.remove_client_role_mappings.assert_called_once_with(ERIKA, CORE_UUID, [role("Company Admin")])
    assert h.dao.audit_log.add.call_args.args[0].operation == "setUserPortalRolesAsOsp"


@pytest.mark.parametrize("bindings, error", [
    ([], NotFoundException),
    ([binding(status=BindingStatus.REMOVED)], NotFoundException),
    ([binding(status=BindingStatus.DISABLED)], InvalidStateException)])
def test_set_portal_roles_needs_an_active_binding(h, bindings, error):
    h.dao.company_users.list_of.return_value = bindings
    with pytest.raises(error):
        h.service.set_company_user_portal_roles(MASCHINENBAU, ERIKA, {"portalRoles": ["Member"]}, ACTOR)


@pytest.mark.parametrize("body", [{}, {"portalRoles": []}, {"portalRoles": ["OSP Admin"]},
                                  {"portalRoles": ["Member", "Member"]}])
def test_set_portal_roles_validates_the_body(h, body):
    h.dao.company_users.list_of.return_value = [binding()]
    with pytest.raises(ValidationException):
        h.service.set_company_user_portal_roles(MASCHINENBAU, ERIKA, body, ACTOR)


# -- 7.4 / 7.14 remove -----------------------------------------------------------------------------------
def test_remove_company_user_unbinds_logs_out_and_reports(h):
    current = binding(MAX)
    h.dao.company_users.list_of.return_value = [current]
    h.iam.role_mappings.return_value = mappings("Member", "Applicant", app=("Viewer",))
    h.iam.get_user.side_effect = lambda uid: keycloak_user(
        uid, attributes={"company_id": [MASCHINENBAU], "bpn": [BPN_M]})
    h.admins(ERIKA)

    h.service.remove_company_user(MASCHINENBAU, MAX, ACTOR)

    assert h.iam.remove_client_role_mappings.call_args_list == [
        call(MAX, IC_UUID, [role("Viewer", "app")]), call(MAX, CORE_UUID, [role("Member")])]
    assert h.iam.update_user.call_args.args[1]["attributes"] == {"company_id": [], "bpn": []}
    h.iam.logout_user.assert_called_once_with(MAX)
    assert (current.status, current.removal_reason) == (BindingStatus.REMOVED, RemovalReason.REMOVED_BY_COMPANY)
    assert current.given_name is None and current.family_name is None
    assert h.events("UserRemovedFromCompany") == [
        {"userId": MAX, "companyId": MASCHINENBAU, "reason": "REMOVED_BY_COMPANY"}]


def test_remove_company_user_twice_is_idempotent(h):
    h.dao.company_users.list_of.return_value = [binding(MAX, status=BindingStatus.REMOVED)]
    h.service.remove_company_user(MASCHINENBAU, MAX, ACTOR)
    h.iam.logout_user.assert_not_called()
    h.published.assert_not_called()


def test_remove_company_user_unknown_is_404(h):
    with pytest.raises(NotFoundException):
        h.service.remove_company_user(MASCHINENBAU, MAX, ACTOR)


def test_remove_the_last_company_admin_is_refused_but_osp_may(h):
    h.dao.company_users.list_of.return_value = [binding()]
    h.dao.company_users.list_of_company.return_value = [binding()]
    h.admins(ERIKA)
    with pytest.raises(LastCompanyAdminException):
        h.service.remove_company_user(MASCHINENBAU, ERIKA, ACTOR)

    h.service.remove_company_user(MASCHINENBAU, ERIKA, ACTOR, as_osp=True)
    assert h.events("UserRemovedFromCompany")[0]["reason"] == "REMOVED_BY_OSP"


def test_remove_of_a_deleted_account_only_marks_the_binding(h):
    current = binding(MAX)
    h.dao.company_users.list_of.return_value = [current]
    h.iam.role_mappings.return_value = None   # account gone in Keycloak
    h.admins(ERIKA)

    h.service.remove_company_user(MASCHINENBAU, MAX, ACTOR)

    assert current.removal_reason == RemovalReason.ACCOUNT_DELETED
    h.iam.logout_user.assert_not_called()


# -- 7.5 / 7.6 app roles -------------------------------------------------------------------------------
def app_roles_ready(h, current: tuple[str, ...] = ()) -> None:
    h.dao.company_users.list_of.return_value = [binding(MAX)]
    h.apps.template.return_value = AppClientTemplate(APP, LOGISTIK, "App", "app-template-1", TEMPLATE_UUID)
    h.apps.target_clients.return_value = [instance_client()]
    h.iam.client_role_mappings.return_value = [role(n, "app") for n in current]


def test_set_user_app_roles_adds_and_removes_on_every_instance_client(h):
    app_roles_ready(h, current=("Viewer",))

    result = h.service.set_user_app_roles(MASCHINENBAU, MAX, APP, {"roles": ["Editor"]}, ACTOR)

    assert h.locks.call_args_list == [call("app", APP), call("company", MASCHINENBAU), call("account", MAX)]
    h.iam.add_client_role_mappings.assert_called_once_with(MAX, IC_UUID, [role("Editor", "app")])
    h.iam.remove_client_role_mappings.assert_called_once_with(MAX, IC_UUID, [role("Viewer", "app")])
    assert h.role_log() == [("ADDED", "Editor", RoleKind.APP), ("REMOVED", "Viewer", RoleKind.APP)]
    assert result.model_dump(by_alias=True) | {} == {
        "userId": MAX, "appId": APP, "roles": ["Editor"], "addedRoles": ["Editor"], "removedRoles": ["Viewer"],
        "instanceClients": [{"appInstanceClientId": "ic-1", "iamClientId": IC_CLIENT_ID}]}
    assert h.events("UserRolesChanged")[0]["appId"] == APP


def test_set_user_app_roles_rejects_roles_not_on_the_template(h):
    app_roles_ready(h)
    with pytest.raises(UnknownAppRoleException):
        h.service.set_user_app_roles(MASCHINENBAU, MAX, APP, {"roles": ["Root"]}, ACTOR)
    h.iam.add_client_role_mappings.assert_not_called()


def test_set_user_app_roles_needs_an_active_subscription(h):
    app_roles_ready(h)
    h.apps.target_clients.return_value = []
    with pytest.raises(NoActiveSubscriptionException):
        h.service.set_user_app_roles(MASCHINENBAU, MAX, APP, {"roles": ["Viewer"]}, ACTOR)


def test_set_user_app_roles_reports_changes_made_before_an_iam_error(h):
    app_roles_ready(h, current=("Viewer",))
    h.iam.remove_client_role_mappings.side_effect = IamErrorException("Keycloak down", retryable=True)

    with pytest.raises(IamErrorException):
        h.service.set_user_app_roles(MASCHINENBAU, MAX, APP, {"roles": ["Editor"]}, ACTOR)

    assert h.events("UserRolesChanged") == [{"userId": MAX, "companyId": MASCHINENBAU, "appId": APP,
                                             "addedRoles": ["Editor"], "removedRoles": []}]


def test_get_company_app_roles(h):
    h.apps.template_roles.return_value = [{"name": "Viewer", "descriptions": []}]
    h.apps.target_clients.return_value = [instance_client()]

    result = h.service.get_company_app_roles(MASCHINENBAU, APP, "en").model_dump(by_alias=True)

    h.apps.template_roles.assert_called_once_with(APP, "en")
    assert result["assignable"] is True and result["templateExists"] is True
    assert result["instanceClients"] == [{"appInstanceClientId": "ic-1", "iamClientId": IC_CLIENT_ID}]


def test_get_company_app_roles_without_template_is_404(h):
    h.apps.template_roles.return_value = None
    with pytest.raises(NotFoundException):
        h.service.get_company_app_roles(MASCHINENBAU, APP, None)


# -- 7.12 account -----------------------------------------------------------------------------------------
def test_get_user_account(h):
    h.iam.get_user.side_effect = lambda uid: keycloak_user(uid, createdTimestamp=1_767_225_600_000)
    h.iam.role_mappings.return_value = mappings("Company Admin", "OSP Reviewer", app=("Viewer",))
    h.dao.company_users.current_of.return_value = binding()

    account = h.service.get_user_account(ERIKA).model_dump(by_alias=True)

    assert (account["portalRoles"], account["staffRoles"]) == (["Company Admin"], ["OSP Reviewer"])
    assert account["binding"]["companyId"] == MASCHINENBAU
    assert account["createdAt"].startswith("2026-01-01")
    assert account["appRoles"][0]["roles"] == ["Viewer"]


def test_get_user_account_unknown(h):
    h.iam.get_user.side_effect = None
    h.iam.get_user.return_value = None
    with pytest.raises(UserNotFoundException):
        h.service.get_user_account(ERIKA)


# -- 7.15 / 7.16 OSP staff --------------------------------------------------------------------------------
def test_list_staff_merges_both_staff_roles(h):
    h.iam.users_with_client_role.side_effect = lambda _u, name: {
        "OSP Reviewer": [keycloak_user(HANS, "Hans", "Zeller"), keycloak_user(ERIKA)],
        "OSP Admin": [keycloak_user(ERIKA)]}.get(name, [])

    page = h.service.list_staff(0, 20).model_dump(by_alias=True)

    assert [m["userId"] for m in page["items"]] == [ERIKA, HANS] and page["total"] == 2


def test_set_staff_roles_for_an_osp_company_account(h):
    h.dao.company_users.current_of.return_value = binding(company_id=OSP)

    h.service.set_staff_roles(ERIKA, {"staffRoles": ["OSP Reviewer"]}, ACTOR)

    assert h.locks.call_args_list == [call("staff", None), call("account", ERIKA)]
    h.iam.add_client_role_mappings.assert_called_once_with(ERIKA, CORE_UUID, [role("OSP Reviewer")])
    assert h.role_log() == [("ADDED", "OSP Reviewer", RoleKind.STAFF_PORTAL)]
    assert h.events("OspStaffRolesChanged") == [{"userId": ERIKA, "addedRoles": ["OSP Reviewer"],
                                                 "removedRoles": []}]


def test_set_staff_roles_for_an_account_of_another_company_is_refused(h):
    h.dao.company_users.current_of.return_value = binding(company_id=MASCHINENBAU)
    with pytest.raises(StaffCompanyConflictException):
        h.service.set_staff_roles(ERIKA, {"staffRoles": ["OSP Reviewer"]}, ACTOR)


def test_last_osp_admin_keeps_the_role(h):
    h.iam.role_mappings.return_value = mappings("OSP Admin")
    h.admins(ERIKA)
    with pytest.raises(LastOspAdminException):
        h.service.set_staff_roles(ERIKA, {"staffRoles": []}, ACTOR)
    h.iam.remove_client_role_mappings.assert_not_called()


def test_set_staff_roles_unknown_account(h):
    h.iam.get_user.side_effect = None
    h.iam.get_user.return_value = None
    with pytest.raises(UserNotFoundException):
        h.service.set_staff_roles(ERIKA, {"staffRoles": []}, ACTOR)


# -- 8.8 assign-company-admin ---------------------------------------------------------------------------
def test_assign_company_admin_creates_company_and_binds_the_applicant(h):
    result = h.service.assign_company_admin(step(companyId=MASCHINENBAU, bpn=BPN_M, applicantSub=ERIKA))

    saved_company = h.dao.companies.save.call_args.args[0]
    assert (saved_company.company_id, saved_company.bpn) == (MASCHINENBAU, BPN_M)
    h.iam.add_client_role_mappings.assert_called_once_with(ERIKA, CORE_UUID, [role("Company Admin")])
    bound = h.saved_bindings()[0]
    assert (bound.joined_via, bound.given_name) == (JoinedVia.ONBOARDING, "Erika")
    actor = h.dao.audit_log.add.call_args.args[0].actor
    assert (actor.type, actor.process_id, actor.step_run_id) == (ActorType.PROCESS, PROCESS, STEP_RUN)
    assert result.company_id == MASCHINENBAU and result.user_id == ERIKA
    assert h.events("UserAssignedToCompany")[0]["via"] == "ONBOARDING"


def test_assign_company_admin_is_idempotent_for_a_bound_admin(h):
    h.dao.companies.get.return_value = Company(MASCHINENBAU, BPN_M)
    h.dao.company_users.current_of.return_value = binding()
    h.iam.get_user.side_effect = lambda uid: keycloak_user(
        uid, attributes={"company_id": [MASCHINENBAU], "bpn": [BPN_M]})
    h.iam.role_mappings.return_value = mappings("Company Admin")

    result = h.service.assign_company_admin(step(companyId=MASCHINENBAU, bpn=BPN_M, applicantSub=ERIKA))

    assert result.portal_roles == ["Company Admin"]
    h.iam.add_client_role_mappings.assert_not_called()
    h.iam.update_user.assert_not_called()
    h.published.assert_not_called()


def test_assign_company_admin_adds_the_role_to_a_bound_member(h):
    h.dao.companies.get.return_value = Company(MASCHINENBAU, BPN_M)
    h.dao.company_users.current_of.return_value = binding()
    h.iam.role_mappings.return_value = mappings("Member")

    h.service.assign_company_admin(step(companyId=MASCHINENBAU, bpn=BPN_M, applicantSub=ERIKA))

    h.iam.add_client_role_mappings.assert_called_once_with(ERIKA, CORE_UUID, [role("Company Admin")])
    assert h.events("UserRolesChanged")[0]["addedRoles"] == ["Company Admin"]


@pytest.mark.parametrize("company, current, staff, error, retryable", [
    (Company(MASCHINENBAU, BPN_L), None, False, ConflictException, False),
    (Company(MASCHINENBAU, BPN_M, status=CompanyStatus.DISABLING), None, False, InvalidStateException, True),
    (None, binding(company_id=LOGISTIK), False, UserAlreadyBoundException, False),
    (None, None, True, StaffCompanyConflictException, False)])
def test_assign_company_admin_refusals(h, company, current, staff, error, retryable):
    h.dao.companies.get.return_value = company
    h.dao.company_users.current_of.return_value = current
    if staff:
        h.iam.role_mappings.return_value = mappings("OSP Reviewer")

    with pytest.raises(error) as raised:
        h.service.assign_company_admin(step(companyId=MASCHINENBAU, bpn=BPN_M, applicantSub=ERIKA))

    assert raised.value.retryable is retryable
    h.dao.company_users.save.assert_not_called()


def test_assign_company_admin_unknown_applicant(h):
    h.iam.get_user.side_effect = None
    h.iam.get_user.return_value = None
    with pytest.raises(UserNotFoundException) as raised:
        h.service.assign_company_admin(step(companyId=MASCHINENBAU, bpn=BPN_M, applicantSub=ERIKA))
    assert raised.value.retryable is False


@pytest.mark.parametrize("fields", [
    {"companyId": "not-a-uuid", "bpn": BPN_M, "applicantSub": ERIKA},
    {"companyId": MASCHINENBAU, "bpn": "BPN-WRONG", "applicantSub": ERIKA},
    {"companyId": MASCHINENBAU, "bpn": BPN_M}])
def test_assign_company_admin_validates_its_input(h, fields):
    with pytest.raises(ValidationException):
        h.service.assign_company_admin(step(**fields))
    h.iam.get_user.assert_not_called()


def test_assign_company_admin_reactivates_a_returning_company(h):
    company = Company(MASCHINENBAU, BPN_M, status=CompanyStatus.DISABLED)
    h.dao.companies.get.return_value = company

    h.service.assign_company_admin(step(companyId=MASCHINENBAU, bpn=BPN_M, applicantSub=ERIKA))

    assert company.status == CompanyStatus.ACTIVE


# -- 8.9 / 8.10 disable and enable ----------------------------------------------------------------------
def test_disable_company_users_suspends_every_binding_and_revokes_invitations(h):
    company = Company(MASCHINENBAU, BPN_M)
    h.dao.companies.get.return_value = company
    erika = binding()
    h.dao.company_users.list_of_company.side_effect = lambda _c, s: (
        [erika] if BindingStatus.ACTIVE in s and erika.status == BindingStatus.ACTIVE else
        [erika] if BindingStatus.DISABLED in s and erika.status == BindingStatus.DISABLED else [])
    h.iam.role_mappings.return_value = mappings("Company Admin", app=("Viewer",))
    invitation = MagicMock(company_id=MASCHINENBAU, status=InvitationStatus.OPEN)
    h.dao.invitations.list_all.return_value = [invitation]

    result = h.service.disable_company_users(step(companyId=MASCHINENBAU))

    invitation.end.assert_called_once_with(InvitationStatus.REVOKED, InvitationEndReason.COMPANY_DISABLED)
    h.dao.invitations.save.assert_called_once_with(invitation)
    assert erika.status == BindingStatus.DISABLED
    assert erika.suspended_roles == SuspendedRoles(["Company Admin"], [(IC_CLIENT_ID, "Viewer")])
    h.iam.logout_user.assert_called_once_with(ERIKA)
    assert company.status == CompanyStatus.DISABLED
    assert result.user_ids == [ERIKA]
    assert h.events("CompanyUsersDisabled") == [{"companyId": MASCHINENBAU, "userIds": [ERIKA]}]


def test_disable_of_the_osp_company_is_refused(h):
    with pytest.raises(InvalidStateException):
        h.service.disable_company_users(step(companyId=OSP))


def test_disable_of_an_unknown_company_is_empty(h):
    assert h.service.disable_company_users(step(companyId=MASCHINENBAU)).user_ids == []
    h.published.assert_not_called()


def test_disable_while_enabling_is_retryable(h):
    h.dao.companies.get.return_value = Company(MASCHINENBAU, BPN_M, status=CompanyStatus.ENABLING)
    with pytest.raises(InvalidStateException) as raised:
        h.service.disable_company_users(step(companyId=MASCHINENBAU))
    assert raised.value.retryable is True


def test_enable_company_users_restores_the_saved_roles(h):
    company = Company(MASCHINENBAU, BPN_M, status=CompanyStatus.DISABLED)
    h.dao.companies.get.return_value = company
    erika = binding(status=BindingStatus.DISABLED,
                    suspended_roles=SuspendedRoles(["Company Admin"], [(IC_CLIENT_ID, "Viewer")]))
    h.dao.company_users.list_of_company.side_effect = lambda _c, s: (
        [erika] if erika.status in s else [])
    h.iam.client_role.return_value = role("Viewer", "app")

    result = h.service.enable_company_users(step(companyId=MASCHINENBAU))

    assert h.iam.add_client_role_mappings.call_args_list == [
        call(ERIKA, CORE_UUID, [role("Company Admin")]), call(ERIKA, IC_UUID, [role("Viewer", "app")])]
    assert h.iam.update_user.call_args.args[1]["attributes"] == {"company_id": [MASCHINENBAU], "bpn": [BPN_M]}
    assert (erika.status, erika.suspended_roles) == (BindingStatus.ACTIVE, None)
    assert company.status == CompanyStatus.ACTIVE
    assert result.user_ids == [ERIKA]
    assert h.events("CompanyUsersEnabled") == [{"companyId": MASCHINENBAU, "userIds": [ERIKA]}]


def test_enable_skips_disabled_instance_clients_and_removes_deleted_accounts(h):
    h.dao.companies.get.return_value = Company(MASCHINENBAU, BPN_M, status=CompanyStatus.DISABLED)
    erika = binding(status=BindingStatus.DISABLED, suspended_roles=SuspendedRoles([], [(IC_CLIENT_ID, "Viewer")]))
    max_ = binding(MAX, status=BindingStatus.DISABLED)
    h.dao.company_users.list_of_company.side_effect = lambda _c, s: [b for b in (erika, max_) if b.status in s]
    h.dao.instance_clients.find_by_iam_client_id.side_effect = lambda _c: instance_client(
        InstanceClientStatus.DISABLED)
    h.iam.get_user.side_effect = lambda uid: None if uid == MAX else keycloak_user(uid)

    h.service.enable_company_users(step(companyId=MASCHINENBAU))

    h.iam.client_role.assert_not_called()
    assert (max_.status, max_.removal_reason) == (BindingStatus.REMOVED, RemovalReason.ACCOUNT_DELETED)
    assert erika.status == BindingStatus.ACTIVE


def test_enable_while_disabling_is_retryable(h):
    h.dao.companies.get.return_value = Company(MASCHINENBAU, BPN_M, status=CompanyStatus.DISABLING)
    with pytest.raises(InvalidStateException) as raised:
        h.service.enable_company_users(step(companyId=MASCHINENBAU))
    assert raised.value.retryable is True


# -- query 9.4 ------------------------------------------------------------------------------------------
def test_list_company_user_refs_filters_by_portal_role(h):
    older = binding(MAX, created_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    newer = binding(ERIKA, created_at=dt.datetime(2026, 2, 1, tzinfo=dt.UTC))
    h.dao.company_users.list_of_company.return_value = [newer, older]
    h.admins(ERIKA, MAX)

    refs = h.service.list_company_user_refs(MASCHINENBAU, "Company Admin", None)

    assert [r.user_id for r in refs] == [MAX, ERIKA]
    h.dao.company_users.list_of_company.assert_called_once_with(MASCHINENBAU, {BindingStatus.ACTIVE})


@pytest.mark.parametrize("company_id, portal_role", [(None, None), ("not-a-uuid", None),
                                                     (MASCHINENBAU, "OSP Admin")])
def test_list_company_user_refs_validation(h, company_id, portal_role):
    with pytest.raises(ValidationException):
        h.service.list_company_user_refs(company_id, portal_role, None)
    if company_id != MASCHINENBAU:
        h.dao.company_users.list_of_company.assert_not_called()


# -- secrets (FRAMEWORK 4.6): no names in events ------------------------------------------------------------
def test_events_carry_no_names(h):
    h.service.bind(MAX, Company(MASCHINENBAU, BPN_M), ["Member"], JoinedVia.INVITATION, ACTOR, "op",
                   given_name="Max", family_name="Mustermann")
    h.dao.company_users.list_of.return_value = [binding(MAX)]
    h.service.remove_company_user(MASCHINENBAU, MAX, ACTOR, as_osp=True)
    assert h.published.call_count == 2
    for c in h.published.call_args_list:
        assert "Max" not in str(c.args[1]) and "Mustermann" not in str(c.args[1])


# -- neighbour gateways (README 11.2): C3-M1 and C10-M1 mocked ------------------------------------------------
def test_company_profile_gateway_queries_c3_m1(monkeypatch):
    query = MagicMock(return_value={"id": MASCHINENBAU, "status": "ACTIVE", "bpn": BPN_M})
    monkeypatch.setattr("portal_common.neighbours.is_standin", lambda target: False)
    monkeypatch.setattr("portal_common.neighbours.query", query)

    assert CompanyProfileGatewayImpl().company(MASCHINENBAU)["bpn"] == BPN_M
    query.assert_called_once_with("c2-m2", "c3-m1", "query_company", companyId=MASCHINENBAU)


def test_company_profile_gateway_maps_a_neighbour_failure_to_upstream_error(monkeypatch):
    def fail(*_a, **_k):
        raise Problem("c3-m1", 503, "unavailable", detail="C3-M1 down", retryable=True)
    monkeypatch.setattr("portal_common.neighbours.is_standin", lambda target: False)
    monkeypatch.setattr("portal_common.neighbours.query", fail)

    with pytest.raises(UpstreamErrorException) as raised:
        CompanyProfileGatewayImpl().company(MASCHINENBAU)
    assert raised.value.retryable is True


def test_company_profile_gateway_stand_in_reads_the_stub_file(monkeypatch):
    query = MagicMock()
    monkeypatch.setattr("portal_common.neighbours.is_standin", lambda target: True)
    monkeypatch.setattr("portal_common.neighbours.query", query)

    assert CompanyProfileGatewayImpl().company(MASCHINENBAU)["bpn"] == BPN_M
    query.assert_not_called()


def test_subscriptions_gateway_queries_c10_m1_and_keeps_only_active(monkeypatch):
    query = MagicMock(return_value=[{"offerSubscriptionId": "sub-1", "status": "ACTIVE"},
                                    {"offerSubscriptionId": "sub-2", "status": "INACTIVE"}])
    monkeypatch.setattr("portal_common.neighbours.is_standin", lambda target: False)
    monkeypatch.setattr("portal_common.neighbours.query", query)

    found = SubscriptionsGatewayImpl().active_subscriptions(MASCHINENBAU, APP)

    assert [s["offerSubscriptionId"] for s in found] == ["sub-1"]
    query.assert_called_once_with("c2-m2", "c10-m1", "find_subscriptions", customerCompanyId=MASCHINENBAU,
                                  offerId=APP, status="ACTIVE")


@pytest.mark.parametrize("answer", [None, {"items": []}])
def test_subscriptions_gateway_treats_a_missing_list_as_upstream_error(monkeypatch, answer):
    monkeypatch.setattr("portal_common.neighbours.is_standin", lambda target: False)
    monkeypatch.setattr("portal_common.neighbours.query", MagicMock(return_value=answer))

    with pytest.raises(UpstreamErrorException):
        SubscriptionsGatewayImpl().active_subscriptions(MASCHINENBAU, APP)


def test_subscriptions_gateway_empty_list_means_no_subscriptions(monkeypatch):
    monkeypatch.setattr("portal_common.neighbours.is_standin", lambda target: False)
    monkeypatch.setattr("portal_common.neighbours.query", MagicMock(return_value=[]))

    assert SubscriptionsGatewayImpl().active_subscriptions(MASCHINENBAU, APP) == []
