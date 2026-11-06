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

from modules.c2_m2.c2_m2_api.model import (AddAppRolesResult, AppInstanceClient, AppRoles, TemplateResult,
                                           UpdateRoleDescriptionsResult)


class AppClientService(abc.ABC):
    """App clients and app roles: steps 8.1 to 8.7 and queries 9.1 to 9.3.
    Steps take the JSON body of `POST /steps/<step>` (with `processId`, `stepRunId`)."""

    @abc.abstractmethod
    def create_client_template(self, input: dict) -> TemplateResult: ...

    @abc.abstractmethod
    def create_instance_client(self, input: dict) -> AppInstanceClient: ...

    @abc.abstractmethod
    def enable_instance_client(self, input: dict) -> AppInstanceClient: ...

    @abc.abstractmethod
    def disable_instance_client(self, input: dict) -> AppInstanceClient: ...

    @abc.abstractmethod
    def update_instance_url(self, input: dict) -> AppInstanceClient: ...

    @abc.abstractmethod
    def add_app_roles(self, input: dict) -> AddAppRolesResult: ...

    @abc.abstractmethod
    def update_role_descriptions(self, input: dict) -> UpdateRoleDescriptionsResult: ...

    @abc.abstractmethod
    def list_app_roles(self, app_ids: list[str], lang: str | None) -> list[AppRoles]: ...

    @abc.abstractmethod
    def list_app_instance_clients(self, *, app_id: str | None, offer_subscription_id: str | None,
                                  customer_company_id: str | None, instance_kind: str | None,
                                  statuses: list[str] | None) -> list[AppInstanceClient]: ...

    @abc.abstractmethod
    def get_app_instance_client(self, id: str) -> AppInstanceClient: ...  # noqa: A002 - openapi name
