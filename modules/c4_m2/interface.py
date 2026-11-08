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
"""Public interface of C4-M2 Dataspace Wallet Interface (call convention of AGENTS.md; ADR-0003 "facade").

Steps for Process Orchestration (README 8), the queries for other modules (README 9) and the operations the
router serves (README 7), each a one-line delegation. The rules are in `service.py` and `services/`, the
providers behind `providers.py` (adapters), the neighbours in `gateways.py`, the data in `store.py`.
"""
from __future__ import annotations

from portal_common import standin

from . import service
from .errors import MODULE
from .services import accounts, queries, sap_div_callback

__all__ = ["MODULE"]


def store() -> service.WalletStore:
    """The active store (also the seam of the tests)."""
    return service.get_store()


def reset() -> None:
    """Stop the timer; clear the store, the key cache and the state of the providers."""
    service.reset_all()


def start_timer() -> None:
    """Start the scheduled tasks of README 6.10."""
    service.start_timer()


# ---------------------------------------------------------------------------- wallet (README 8.1, 9)
def create_wallet(input: dict) -> dict:
    """Step `create-wallet` (README 8.1)."""
    return service.create_wallet(input)


def get_wallet_info(*, companyId: str) -> dict:
    """Query `getWalletInfo` (README 9.1): the wallet without secrets."""
    return queries.wallet_info(companyId)


def wallet_view(*, companyId: str) -> dict:
    """Body of `GET /companies/{companyId}/wallet` (README 7.1, openapi `Wallet`)."""
    return queries.wallet_view(companyId)


def get_holder_access(*, companyId: str, claims: dict | None = None) -> dict:
    """Query `getHolderAccess` (README 9.3), only for C4-M1. `claims` is set by the HTTP route; in the same
    process the audit entry holds the name of the calling module."""
    return queries.holder_access(companyId, claims)


# ------------------------------------------------------------------- wallet accounts (README 8.2, 8.3, 9.2)
def create_wallet_account(input: dict) -> dict:
    """Step `create-wallet-account` (README 8.2)."""
    return accounts.create_wallet_account(input)


def delete_wallet_account(input: dict) -> dict:
    """Step `delete-wallet-account` (README 8.3)."""
    return accounts.delete_wallet_account(input)


def get_wallet_account_internal(*, technicalUserId: str) -> dict:
    """Query `getWalletAccountInternal` (README 9.2)."""
    return accounts.get_wallet_account_internal(technicalUserId=technicalUserId)


def view_wallet_account(technical_user_id: str, claims: dict) -> dict:
    """`GET /technical-users/{technicalUserId}/wallet-account`."""
    return accounts.view_wallet_account(technical_user_id, claims)


def retrieve_credentials(technical_user_id: str, claims: dict) -> dict:
    """`POST /technical-users/{technicalUserId}/wallet-account/credentials`."""
    return accounts.retrieve_credentials(technical_user_id, claims)


# ------------------------------------------------------------------------ SAP DIV callbacks (README 7.6)
def accept_sap_div_wallet_callback(bpn: str, body: dict, claims: dict) -> None:
    """The wallet callback of SAP DIV: only its callback client, then README 7.6 steps 1 to 6."""
    sap_div_callback.authorize(claims)
    sap_div_callback.accept_wallet_callback(bpn, body, claims)


def accept_sap_div_account_created(external_id: str, body: dict, claims: dict) -> None:
    """The technical-user callback of SAP DIV (README 7.6)."""
    sap_div_callback.authorize(claims)
    accounts.accept_account_created(external_id, body, claims)


def accept_sap_div_account_deleted(external_id: str, claims: dict) -> None:
    """The deletion callback of SAP DIV for a technical user (README 7.6)."""
    sap_div_callback.authorize(claims)
    accounts.accept_account_deleted(external_id, claims)


__getattr__ = standin.missing_interface(MODULE)   # steps and queries of the spec not implemented here: stand-in
