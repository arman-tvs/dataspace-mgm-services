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
"""Public interface of the C4-M2 stand-in: `create-wallet` and the wallet queries.

Provider: the dataspace wallet of the CSP when `CSP_WALLET_URL` is set (C4-M2 11.3, e.g. the
shared CSP stand-in `/wallet/v1`), otherwise `STUB` (DID `did:web:wallet.example.org:<BPN>`).
The holder access (API key) stays in memory and is only returned by the query for C4-M1.
"""
from __future__ import annotations

import os

from portal_common import csp, events, neighbours, standin
from portal_common.problems import Problem

from . import crypto, service
from .store import WalletStore

MODULE = "c4-m2"
wallets: dict[str, dict] = {}


def store() -> WalletStore:
    """The active store."""
    return service.get_store()


def reset() -> None:
    """Clear the store, the key cache and the helpers of the providers and accounts files, if they exist."""
    wallets.clear()
    service.reset()
    crypto.reset()
    for name in ("providers", "accounts"):
        module = service.optional_module(name)
        if module is not None and hasattr(module, "reset"):
            module.reset()


def _implemented() -> bool:
    """The real implementation needs the provider adapters (providers.py). Until that file exists in the
    module, the stand-in below answers, so that the flows of demo.py keep working."""
    return service.providers_module() is not None


def create_wallet(input: dict) -> dict:
    """Step `create-wallet` (README 8.1)."""
    if _implemented():
        return service.create_wallet(input)
    return _standin_create_wallet(input)


def _standin_create_wallet(input: dict) -> dict:
    cid = input.get("companyId")
    if cid not in wallets:
        company = neighbours.query(MODULE, "c3-m1", "query_company", companyId=cid)
        if not company or not company.get("bpn"):
            raise Problem(MODULE, 409, "invalid-state", detail="company without BPN", retryable=False)
        bpn, url = company["bpn"], os.environ.get("CSP_WALLET_URL", "")
        if url:
            try:
                status, answer = csp.request(url, "POST", "/wallets", {"bpn": bpn})
            except csp.CspUnavailable as e:
                raise Problem(MODULE, 502, "upstream-error", detail=str(e), retryable=True) from e
            if status != 201:
                raise Problem(MODULE, 409 if status in (403, 409) else 502,
                              "provider-rejected" if status in (403, 409) else "upstream-error",
                              detail=f"CSP wallet answered {status}", retryable=status >= 500)
            wallets[cid] = {"walletId": standin.stable_id("wallet", cid), "companyId": cid, "bpn": bpn,
                            "status": "ACTIVE", "provider": "CSP", "issuanceMode": "HOLDER_REQUESTS",
                            "supportsWalletAccounts": True,
                            "did": answer["did"], "providerRef": answer["participantContextId"],
                            "_holder": {k: answer[k] for k in ("identityApiUrl", "participantContextId", "apiKey")}}
        else:
            wallets[cid] = {"walletId": standin.stable_id("wallet", cid), "companyId": cid, "bpn": bpn,
                            "status": "ACTIVE", "provider": "STUB", "issuanceMode": "STUB", "supportsWalletAccounts": False,
                            "did": f"did:web:wallet.example.org:{bpn}", "providerRef": None, "_holder": None}
        w = wallets[cid]
        events.publish(MODULE, "DataspaceWalletCreated", {
            "companyId": cid, "did": w["did"], "walletId": w["walletId"], "provider": w["provider"],
            "didDocumentLocation": service.did_web_location(w["did"]), "bpn": bpn})
    return standin.step_reply(input, state="RUNNING")   # long-running; completed by DataspaceWalletCreated


def _wallet(cid: str) -> dict:
    if cid not in wallets:
        raise Problem(MODULE, 404, "not-found")
    return wallets[cid]


def get_wallet_info(*, companyId: str) -> dict:
    """Query `getWalletInfo` (README 9.1): the wallet without secrets."""
    if _implemented():
        return service.wallet_info(companyId)
    return {k: v for k, v in _wallet(companyId).items() if not k.startswith("_")}


def wallet_view(*, companyId: str) -> dict:
    """Body of `GET /companies/{companyId}/wallet` (README 7.1, openapi `Wallet`)."""
    if _implemented():
        return service.wallet_view(companyId)
    return get_wallet_info(companyId=companyId)


def get_holder_access(*, companyId: str, claims: dict | None = None) -> dict:
    """Query `getHolderAccess` (README 9.3), only for C4-M1. `claims` is set by the HTTP route; in the same
    process the audit entry holds the name of the calling module."""
    if _implemented():
        return service.holder_access(companyId, claims)
    w = _wallet(companyId)
    if not w["_holder"]:
        raise Problem(MODULE, 409, "invalid-state", detail="no holder access for provider STUB")
    return w["_holder"]


# ------------------------------------------------------------------------------- wallet accounts
# The wallet accounts (README 8.2, 8.3, 9.2) are implemented in accounts.py. It is imported when the
# function is called, so that this file and accounts.py never import each other at load time. Without
# accounts.py the stand-in answers.
def _account_function(name: str):
    accounts = service.optional_module("accounts")
    if accounts is not None and hasattr(accounts, name):
        return getattr(accounts, name)
    return __getattr__(name)


def create_wallet_account(input: dict) -> dict:
    """Step `create-wallet-account` (README 8.2)."""
    return _account_function("create_wallet_account")(input)


def delete_wallet_account(input: dict) -> dict:
    """Step `delete-wallet-account` (README 8.3)."""
    return _account_function("delete_wallet_account")(input)


def get_wallet_account_internal(*, technicalUserId: str) -> dict:
    """Query `getWalletAccountInternal` (README 9.2)."""
    return _account_function("get_wallet_account_internal")(technicalUserId=technicalUserId)


__getattr__ = standin.missing_interface(MODULE)   # steps and queries not implemented yet: stand-in
