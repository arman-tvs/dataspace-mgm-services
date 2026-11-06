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
from collections.abc import Iterable
from contextlib import AbstractContextManager

from modules.c2_m2.c2_m2_api.model.constants import BindingStatus
from modules.c2_m2.c2_m2_impl.internal.model import CompanyUser


class CompanyUserDao(abc.ABC):
    """Table `company_user`: bindings of accounts to companies."""

    @abc.abstractmethod
    def lock_account(self, user_id: str) -> AbstractContextManager[None]:
        """Lock `account` of 6.14 until the transaction ends; works for accounts without a binding."""

    @abc.abstractmethod
    def save(self, binding: CompanyUser) -> None: ...

    @abc.abstractmethod
    def current_of(self, user_id: str) -> CompanyUser | None:
        """The binding `ACTIVE` or `DISABLED` of the account; at most one exists."""

    @abc.abstractmethod
    def list_of(self, user_id: str, company_id: str) -> list[CompanyUser]:
        """All bindings of the account to the company, oldest first."""

    @abc.abstractmethod
    def list_of_company(self, company_id: str | None, statuses: Iterable[BindingStatus]) -> list[CompanyUser]:
        """Bindings with one of `statuses`; `company_id` None means all companies."""
