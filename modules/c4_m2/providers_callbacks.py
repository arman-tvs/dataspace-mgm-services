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
#  Assisted-By: Claude Code (claude-sonnet-5-5)
#################################################################################
"""HTTP routes of the SAP DIV callbacks (README 7.6): the middleware reports wallets and wallet accounts.

Checks in this order: token (401), permission `submit_wallet_callback` (403), the calling client `azp` equals
`SAP_DIV_CALLBACK_CLIENT_ID` (403, nothing is audited), then the logic of the core (`service`) or of the wallet
accounts (`accounts`), which writes the audit entry itself. The router has no prefix; `router.py` includes it
under `/api/c4-m2`.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Body, Response

from portal_common import problems, standin
from portal_common.problems import Problem

MODULE = "c4-m2"
DEFAULT_CALLBACK_CLIENT = "sa-div-callback"


def _authorize(claims: dict) -> None:
    client = os.environ.get("SAP_DIV_CALLBACK_CLIENT_ID", "").strip() or DEFAULT_CALLBACK_CLIENT
    if claims.get("azp") != client:
        raise Problem(MODULE, 403, "forbidden", detail="the calling client is not the callback client of SAP DIV")


def sap_div_router() -> APIRouter:
    router = APIRouter(route_class=problems.route_class(MODULE))

    @router.post("/callbacks/sap-div/wallets/{bpn}")
    def wallet_created(bpn: str, body: dict = Body(...),
                       claims: dict = standin.perm(MODULE, "POST", "/callbacks/sap-div/wallets/{bpn}")):
        from . import service
        _authorize(claims)
        service.accept_wallet_callback(bpn, body, claims)
        return Response(status_code=204)

    @router.post("/callbacks/sap-div/technical-users/{externalId}")
    def account_created(externalId: str, body: dict = Body(...),
                        claims: dict = standin.perm(MODULE, "POST", "/callbacks/sap-div/technical-users/{externalId}")):
        from . import accounts
        _authorize(claims)
        accounts.accept_account_created(externalId, body, claims)
        return Response(status_code=204)

    @router.post("/callbacks/sap-div/technical-users/{externalId}/delete")
    def account_deleted(externalId: str,
                        claims: dict = standin.perm(MODULE, "POST",
                                                    "/callbacks/sap-div/technical-users/{externalId}/delete")):
        from . import accounts
        _authorize(claims)
        accounts.accept_account_deleted(externalId, claims)
        return Response(status_code=204)

    return router
