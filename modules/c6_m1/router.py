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
#  Assisted-By: Claude Code (claude-opus-5-5)
#################################################################################
"""HTTP layer of C6-M1 Connectors (README 7 to 9): token and permission from openapi.yaml, the scope
`company` from the token, then `service.py` or `interface.py`."""
from __future__ import annotations

from typing import Literal

from fastapi import Body, Query, Response

from portal_common import standin

from . import interface, service
from .interface import MODULE

router = standin.router(MODULE)

Role = Literal["provider", "host"]
Type = Literal["COMPANY_CONNECTOR", "CONNECTOR_AS_A_SERVICE"]
Status = Literal["ACTIVE", "INACTIVE"]


def reset() -> None:
    interface.reset()


# ---------------------------------------------------------------- people (README 7, scope company)
@router.get("/connectors")
def list_connectors(role: Role | None = None, type: Type | None = None, status: Status | None = None,
                    page: int = Query(0, ge=0), size: int = Query(20, ge=1, le=100),
                    claims: dict = standin.perm(MODULE, "GET", "/connectors")):
    return service.list_connectors(claims.get("company_id"), role=role, type=type, status=status, page=page, size=size)


@router.post("/connectors", status_code=201)
def register_connector(body: dict = Body(...), claims: dict = standin.perm(MODULE, "POST", "/connectors")):
    return service.register_connector(claims.get("company_id"), claims.get("sub"), body)


@router.post("/connectors/as-a-service", status_code=201)
def register_connector_as_a_service(body: dict = Body(...),
                                    claims: dict = standin.perm(MODULE, "POST", "/connectors/as-a-service")):
    return service.register_connector_as_a_service(claims.get("company_id"), claims.get("sub"), body)


@router.get("/connectors/{connectorId}")
def get_connector(connectorId: str, claims: dict = standin.perm(MODULE, "GET", "/connectors/{connectorId}")):
    return service.get_connector(claims.get("company_id"), connectorId)


@router.patch("/connectors/{connectorId}")
def change_endpoint(connectorId: str, body: dict = Body(...),
                    claims: dict = standin.perm(MODULE, "PATCH", "/connectors/{connectorId}")):
    return service.change_endpoint(claims.get("company_id"), claims.get("sub"), connectorId, body)


@router.delete("/connectors/{connectorId}", status_code=204)
def delete_connector(connectorId: str, claims: dict = standin.perm(MODULE, "DELETE", "/connectors/{connectorId}")):
    service.delete_connector(claims.get("company_id"), claims.get("sub"), connectorId)
    return Response(status_code=204)


# ---------------------------------------------------------------- Process Orchestration (README 8)
@router.post("/steps/deactivate-subscription-connectors")
def deactivate_subscription_connectors(
        body: dict = Body(...), _: dict = standin.perm(MODULE, "POST", "/steps/deactivate-subscription-connectors")):
    return interface.deactivate_subscription_connectors(body)


@router.post("/steps/unlink-technical-user")
def unlink_technical_user(body: dict = Body(...), _: dict = standin.perm(MODULE, "POST", "/steps/unlink-technical-user")):
    return interface.unlink_technical_user(body)


# ---------------------------------------------------------------- queries (README 9)
@router.get("/internal/connectors")
def list_connectors_internal(technicalUserId: str | None = None,
                             _: dict = standin.perm(MODULE, "GET", "/internal/connectors")):
    return interface.list_connectors_internal(technicalUserId=technicalUserId)
