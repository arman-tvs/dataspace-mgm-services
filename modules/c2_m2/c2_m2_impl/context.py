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
"""What the service implementations of C2-M2 share: configuration, DAO service, Portal IAM, neighbours, events."""
from __future__ import annotations

from dataclasses import dataclass, field

from modules.c2_m2.c2_m2_api.model.common import Actor
from modules.c2_m2.c2_m2_api.model.constants import RoleKind
from modules.c2_m2.c2_m2_api.model.utils import MODULE
from modules.c2_m2.c2_m2_impl.config import Config
from modules.c2_m2.c2_m2_impl.config.properties import as_list
from modules.c2_m2.c2_m2_impl.dao import DaoService
from modules.c2_m2.c2_m2_impl.internal.model import AppInstanceClient, AuditLogEntry, RoleAssignmentLogEntry
from modules.c2_m2.c2_m2_impl.internal.services import (CompanyProfileGateway, PortalIam, SubscriptionsGateway,
                                                        iam_error)
from modules.c2_m2.c2_m2_impl.utils.validation_utils import Validator, invalid
from portal_common import events


@dataclass
class Context:
    config: Config
    iam: PortalIam
    dao: DaoService
    subscriptions: SubscriptionsGateway
    company_profiles: CompanyProfileGateway
    _core_uuid: str | None = None
    _core_roles: dict[str, dict] = field(default_factory=dict)

    @property
    def validate(self) -> Validator:
        return Validator(as_list(self.config.from_properties("languages")))

    @staticmethod
    def publish(event_type: str, data: dict) -> dict:
        """CloudEvent of README section 10; never names, codes or secrets."""
        return events.publish(MODULE, event_type, data)

    # -- logs (6.13) ---------------------------------------------------------------------------
    def audit(self, actor: Actor, operation: str, company_id: str | None, object_id: str | None) -> None:
        self.dao.audit_log.add(AuditLogEntry(actor, operation, company_id, object_id))

    def log_role(self, actor: Actor, operation: str, action: str, user_id: str, company_id: str | None,
                 kind: RoleKind, iam_client_id: str, role: str, client: AppInstanceClient | None = None) -> None:
        self.dao.role_log.add(RoleAssignmentLogEntry(
            user_id=user_id, company_id=company_id, role_kind=kind, iam_client_id=iam_client_id, role_name=role,
            action=action, actor=actor, operation=operation, app_id=client.app_id if client else None,
            app_instance_client_id=client.id if client else None))

    # -- the client `portal-core` (6.12.2: role IDs read at start, an unknown name reads again) ---
    @property
    def core_uuid(self) -> str:
        if self._core_uuid is None:
            client = self.iam.find_client(self.config.from_properties("portal.core.client.id"))
            if not client:
                raise iam_error(f"client {self.config.from_properties("portal.core.client.id")} not found")
            self._core_uuid = client["id"]
        return self._core_uuid

    def core_role(self, name: str) -> dict:
        if name not in self._core_roles:
            self._core_roles = {r["name"]: r for r in self.iam.client_roles(self.core_uuid)}
        if name not in self._core_roles:
            raise iam_error(f"portal role {name!r} missing on {self.config.from_properties("portal.core.client.id")}")
        return self._core_roles[name]


def paginate(items: list, page: int, size: int, render) -> dict:
    """Lists as in FRAMEWORK 4.1: `{items, page, size, total}`."""
    chunk = items[page * size:(page + 1) * size]
    return {"items": [render(x) for x in chunk], "page": page, "size": size, "total": len(items)}


def statuses(values: list[str] | str | None, allowed: type, default: list) -> set:
    """Repeatable `status` filter, validated against an enumeration."""
    given = [values] if isinstance(values, str) else list(values or [])
    try:
        return {allowed(v) for v in given} or set(default)
    except ValueError:
        raise invalid(f"status: one of {[str(x) for x in allowed]}") from None
