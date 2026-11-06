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

Routes of this file: `POST /steps/create-wallet`, `GET /companies/{companyId}/wallet`,
`GET /internal/wallets/{companyId}` and `GET /internal/wallets/{companyId}/holder-access`. The wallet
account routes (`accounts.router`) and the SAP DIV callback routes (`providers.callback_routers()`) belong
to other files of the module and are mounted here when those files exist. Operations that are not
implemented yet are answered by the scaffold from the spec.
"""
from __future__ import annotations

from fastapi import Body, Response

from portal_common import standin

from . import interface, service
from .interface import MODULE

router = standin.router(MODULE)


def reset() -> None:
    interface.reset()


def on_startup() -> None:
    """Start the scheduled tasks of README 6.10."""
    service.start_timer()


@router.post("/steps/create-wallet")
def create_wallet(body: dict = Body(...), _: dict = standin.perm(MODULE, "POST", "/steps/create-wallet")):
    return interface.create_wallet(body)


@router.get("/companies/{companyId}/wallet")
def own_wallet(companyId: str, claims: dict = standin.perm(MODULE, "GET", "/companies/{companyId}/wallet")):
    standin.company_scope(MODULE, claims, companyId)
    return interface.wallet_view(companyId=companyId)


@router.get("/internal/wallets/{companyId}")
def get_wallet(companyId: str, _: dict = standin.perm(MODULE, "GET", "/internal/wallets/{companyId}")):
    return interface.get_wallet_info(companyId=companyId)


@router.get("/internal/wallets/{companyId}/holder-access")
def holder_access(companyId: str, response: Response,
                  claims: dict = standin.perm(MODULE, "GET", "/internal/wallets/{companyId}/holder-access")):
    response.headers["Cache-Control"] = "no-store"
    return interface.get_holder_access(companyId=companyId, claims=claims)


def _mount_other_files() -> None:
    """Wallet accounts and SAP DIV callbacks are written in `accounts.py` and `providers.py`."""
    accounts = service.optional_module("accounts")
    if accounts is not None and hasattr(accounts, "router"):
        router.include_router(accounts.router)
    providers = service.providers_module()
    if providers is not None and hasattr(providers, "callback_routers"):
        for callback_router in providers.callback_routers():
            router.include_router(callback_router)


_mount_other_files()
