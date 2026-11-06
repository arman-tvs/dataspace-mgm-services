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

from modules.c2_m2.c2_m2_api.exception import IamErrorException


def iam_error(detail: str) -> IamErrorException:
    return IamErrorException(detail, retryable=True)


class PortalIam(abc.ABC):
    """The calls of the Keycloak Admin REST API that C2-M2 uses (README 11.1); Keycloak representations as dicts.
    `uuid` is the internal ID of a client, `client_id` its client ID. Unexpected answers raise `IamErrorException`."""

    # -- clients -------------------------------------------------------------------------------
    @abc.abstractmethod
    def find_client(self, client_id: str) -> dict | None: ...

    @abc.abstractmethod
    def create_client(self, representation: dict) -> str: ...

    @abc.abstractmethod
    def get_client(self, uuid: str) -> dict: ...

    @abc.abstractmethod
    def update_client(self, uuid: str, representation: dict) -> None: ...

    @abc.abstractmethod
    def protocol_mappers(self, uuid: str) -> list[dict]: ...

    @abc.abstractmethod
    def create_protocol_mapper(self, uuid: str, mapper: dict) -> None: ...

    # -- client roles --------------------------------------------------------------------------
    @abc.abstractmethod
    def client_roles(self, uuid: str) -> list[dict]: ...

    @abc.abstractmethod
    def client_role(self, uuid: str, name: str) -> dict | None: ...

    @abc.abstractmethod
    def create_client_role(self, uuid: str, name: str, description: str | None) -> None: ...

    @abc.abstractmethod
    def update_client_role(self, uuid: str, name: str, representation: dict) -> None: ...

    @abc.abstractmethod
    def users_with_client_role(self, uuid: str, name: str) -> list[dict]: ...

    # -- accounts ------------------------------------------------------------------------------
    @abc.abstractmethod
    def get_user(self, user_id: str) -> dict | None: ...

    @abc.abstractmethod
    def update_user(self, user_id: str, representation: dict) -> None: ...

    @abc.abstractmethod
    def logout_user(self, user_id: str) -> None: ...

    @abc.abstractmethod
    def role_mappings(self, user_id: str) -> dict | None: ...

    @abc.abstractmethod
    def client_role_mappings(self, user_id: str, uuid: str) -> list[dict]: ...

    @abc.abstractmethod
    def add_client_role_mappings(self, user_id: str, uuid: str, roles: list[dict]) -> None: ...

    @abc.abstractmethod
    def remove_client_role_mappings(self, user_id: str, uuid: str, roles: list[dict]) -> None: ...
