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
#  Assisted-By: GitHub Copilot
#################################################################################
"""Building blocks of the endpoint interfaces: where a method is exposed, never what it does."""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Annotated

from fastapi import Body, Path, Query

ENDPOINT_ATTRIBUTE = "__c2_m2_endpoint__"


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str   # relative to the module base path /api/c2-m2


class EndpointRouter:
    """Looks like a FastAPI router, but only records the HTTP method and path of an interface method.
    `create_router` registers the routes later, bound to an implementation. Everything else about the
    operation (operationId, permission, scope, schemas) comes from the contract YAML."""

    def _record(self, method: str, path: str):
        def decorate(function):
            setattr(function, ENDPOINT_ATTRIBUTE, Endpoint(method, path))
            return function
        return decorate

    def get(self, path: str):
        return self._record("GET", path)

    def post(self, path: str):
        return self._record("POST", path)

    def put(self, path: str):
        return self._record("PUT", path)

    def delete(self, path: str):
        return self._record("DELETE", path)


api = EndpointRouter()


class _Authenticated:
    def __repr__(self) -> str:
        return "AUTHENTICATED"


# Marker in the type of the `claims` parameter. The router replaces it with the token and permission
# check of the operation (`x-permission` of the contract); the implementation receives the token claims.
AUTHENTICATED = _Authenticated()

# FastAPI metadata lives in the type hints, never in the defaults, so an implementation can override an
# interface method with plain types and the same plain defaults (`page: int = 0`) without FastAPI imports.
# Python names are snake_case; `alias` keeps the names of the contract on the wire.
Claims = Annotated[dict, AUTHENTICATED]
JsonBody = Annotated[dict, Body()]
PageNumber = Annotated[int, Query(alias="page", ge=0)]
PageSize = Annotated[int, Query(alias="size", ge=1, le=100)]
StatusFilter = Annotated[list[str] | None, Query(description="May be given several times.")]
Lang = Annotated[str | None, Query()]
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
CompanyId = Annotated[str, Path(alias="companyId")]
UserId = Annotated[str, Path(alias="userId")]
AppId = Annotated[str, Path(alias="appId")]
InvitationId = Annotated[str, Path(alias="invitationId")]


class RestApi(ABC):
    """Base of every endpoint interface of C2-M2."""

    @classmethod
    def endpoints(cls) -> dict[str, Endpoint]:
        """Endpoints declared by this interface itself, by method name."""
        return {name: getattr(member, ENDPOINT_ATTRIBUTE)
                for name, member in vars(cls).items() if hasattr(member, ENDPOINT_ATTRIBUTE)}
