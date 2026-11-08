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
"""HTTP layer of C4-M2 Dataspace Wallet Interface: token, permission and scope, then the interface function.

Every route of the module is here (ADR-0003: HTTP only in the router): the wallet (README 7.1, 8.1, 9.1,
9.3), the wallet accounts (README 8.2, 8.3, 9.2) and the callbacks of SAP DIV (README 7.6), in this order.
Operations that are not implemented are answered by the scaffold from the spec.
"""
from __future__ import annotations

from fastapi import Body, Response

from portal_common import standin

from . import interface
from .interface import MODULE

router = standin.router(MODULE)


def reset() -> None:
    interface.reset()


def on_startup() -> None:
    """Start the scheduled tasks of README 6.10."""
    interface.start_timer()


# ------------------------------------------------------------------------------------------- wallet
@router.post("/steps/create-wallet")
def create_wallet(body: dict = Body(...), _: dict = standin.perm(MODULE, "POST", "/steps/create-wallet")) -> dict:
    return interface.create_wallet(body)


@router.get("/companies/{companyId}/wallet")
def own_wallet(companyId: str, claims: dict = standin.perm(MODULE, "GET", "/companies/{companyId}/wallet")) -> dict:
    standin.company_scope(MODULE, claims, companyId)
    return interface.wallet_view(companyId=companyId)


@router.get("/internal/wallets/{companyId}")
def get_wallet(companyId: str, _: dict = standin.perm(MODULE, "GET", "/internal/wallets/{companyId}")) -> dict:
    return interface.get_wallet_info(companyId=companyId)


@router.get("/internal/wallets/{companyId}/holder-access")
def holder_access(companyId: str, response: Response,
                  claims: dict = standin.perm(MODULE, "GET", "/internal/wallets/{companyId}/holder-access")) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return interface.get_holder_access(companyId=companyId, claims=claims)


# ---------------------------------------------------------------------------------- wallet accounts
@router.post("/steps/create-wallet-account")
def step_create_wallet_account(body: dict = Body(...),
                               _: dict = standin.perm(MODULE, "POST", "/steps/create-wallet-account")) -> dict:
    return interface.create_wallet_account(body)


@router.post("/steps/delete-wallet-account")
def step_delete_wallet_account(body: dict = Body(...),
                               _: dict = standin.perm(MODULE, "POST", "/steps/delete-wallet-account")) -> dict:
    return interface.delete_wallet_account(body)


@router.get("/technical-users/{technicalUserId}/wallet-account")
def get_wallet_account(technicalUserId: str,
                       claims: dict = standin.perm(MODULE, "GET",
                                                   "/technical-users/{technicalUserId}/wallet-account")) -> dict:
    return interface.view_wallet_account(technicalUserId, claims)


@router.post("/technical-users/{technicalUserId}/wallet-account/credentials")
def post_wallet_account_credentials(
        technicalUserId: str, response: Response,
        claims: dict = standin.perm(MODULE, "POST",
                                    "/technical-users/{technicalUserId}/wallet-account/credentials")) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return interface.retrieve_credentials(technicalUserId, claims)


@router.get("/internal/technical-users/{technicalUserId}/wallet-account")
def get_wallet_account_internal_route(
        technicalUserId: str,
        _: dict = standin.perm(MODULE, "GET", "/internal/technical-users/{technicalUserId}/wallet-account")) -> dict:
    return interface.get_wallet_account_internal(technicalUserId=technicalUserId)


# -------------------------------------------------------------------------- SAP DIV callbacks (README 7.6)
@router.post("/callbacks/sap-div/wallets/{bpn}")
def sap_div_wallet_created(bpn: str, body: dict = Body(...),
                           claims: dict = standin.perm(MODULE, "POST", "/callbacks/sap-div/wallets/{bpn}")) -> Response:
    interface.accept_sap_div_wallet_callback(bpn, body, claims)
    return Response(status_code=204)


@router.post("/callbacks/sap-div/technical-users/{externalId}")
def sap_div_account_created(externalId: str, body: dict = Body(...),
                            claims: dict = standin.perm(MODULE, "POST",
                                                        "/callbacks/sap-div/technical-users/{externalId}")) -> Response:
    interface.accept_sap_div_account_created(externalId, body, claims)
    return Response(status_code=204)


@router.post("/callbacks/sap-div/technical-users/{externalId}/delete")
def sap_div_account_deleted(externalId: str,
                            claims: dict = standin.perm(MODULE, "POST",
                                                        "/callbacks/sap-div/technical-users/{externalId}/delete")
                            ) -> Response:
    interface.accept_sap_div_account_deleted(externalId, claims)
    return Response(status_code=204)
