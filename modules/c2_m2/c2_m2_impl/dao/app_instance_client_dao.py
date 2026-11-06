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

from modules.c2_m2.c2_m2_impl.internal.model import AppInstanceClient


class AppInstanceClientDao(abc.ABC):
    """Table `app_instance_client` and the sequence `client_number` (6.1)."""

    @abc.abstractmethod
    def get(self, instance_client_id: str) -> AppInstanceClient | None: ...

    @abc.abstractmethod
    def save(self, instance_client: AppInstanceClient) -> None: ...

    @abc.abstractmethod
    def find_by_subscription(self, offer_subscription_id: str) -> AppInstanceClient | None: ...

    @abc.abstractmethod
    def find_single(self, app_id: str) -> AppInstanceClient | None:
        """The `SINGLE` instance client of the app with a status other than `DISABLED`."""

    @abc.abstractmethod
    def find_by_iam_client_id(self, iam_client_id: str) -> AppInstanceClient | None: ...

    @abc.abstractmethod
    def list_of_app(self, app_id: str) -> list[AppInstanceClient]:
        """Sorted by `created_at`."""

    @abc.abstractmethod
    def list_all(self) -> list[AppInstanceClient]: ...

    @abc.abstractmethod
    def next_client_number(self) -> int: ...
