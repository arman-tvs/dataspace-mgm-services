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
"""C2-M2 as one object: configuration, DAO service, internal services and service implementations, created at
first use and on `reset()`."""
from __future__ import annotations

import threading

from .c2_m2_impl.config import Config
from .c2_m2_impl.context import Context
from .c2_m2_impl.dao.impl import postgres_dao_service
from .c2_m2_impl.dao.jdbc import MIGRATIONS_DIR
from .c2_m2_impl.impl import (AppClientServiceImpl, CompanyProfileGatewayImpl, InvitationCleanupJobImpl,
                              InvitationServiceImpl, PostgresDatabase, SubscriptionsGatewayImpl, UserServiceImpl,
                              portal_iam)


class C2M2Module:
    def __init__(self, config: Config | None = None) -> None:
        config = config or Config()
        database_url = config.from_properties("database.url")
        if not database_url:
            raise RuntimeError(f"C2-M2 needs its database: set database.url (DATABASE_URL, README 4) in {config.config_file}")
        db = PostgresDatabase(database_url)
        db.migrate(MIGRATIONS_DIR)
        self.ctx = Context(config, portal_iam(config), postgres_dao_service(db), SubscriptionsGatewayImpl(),
                           CompanyProfileGatewayImpl())
        self.apps = AppClientServiceImpl(self.ctx)
        self.users = UserServiceImpl(self.ctx, self.apps)
        self.invitations = InvitationServiceImpl(self.ctx, self.users)
        self.cleanup = InvitationCleanupJobImpl(self.invitations.expire_overdue)

    def on_startup(self) -> None:
        self.invitations.bootstrap()
        self.cleanup.start()

    def close(self) -> None:
        self.cleanup.stop()


_lock = threading.Lock()
_current: C2M2Module | None = None


def current() -> C2M2Module:
    global _current
    with _lock:
        if _current is None:
            _current = C2M2Module()
        return _current


def reset() -> None:
    """Fresh data and configuration read again from the environment (README 4)."""
    global _current
    with _lock:
        if _current is not None:
            _current.close()
        _current = None
