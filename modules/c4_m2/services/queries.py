#################################################################################
#  Copyright (c) 2026 Technovative Solutions
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
"""Queries of C4-M2: `getWalletInfo` (README 9.1), the wallet view (README 7.1), `getHolderAccess` (README 9.3).
No secrets, except the holder access for C4-M1, which is audited."""
from __future__ import annotations

import os

from modules.c4_m2 import errors, service


def _issuance_mode(provider: str) -> str:
    return "ISSUER_WRITES" if provider == "SAP_DIV" else "HOLDER_REQUESTS"


def _wallet_or_404(company_id: str) -> dict:
    wallet = service.get_store().get_wallet(company_id)
    if wallet is None:
        raise errors.not_found("no wallet for this company")
    return wallet


def wallet_info(company_id: str) -> dict:
    """README 9.1 `WalletInfo`: 13 fields, no secrets."""
    wallet = _wallet_or_404(company_id)
    return {"walletId": wallet["id"], "companyId": wallet["company_id"], "bpn": wallet["bpn"],
            "provider": wallet["provider"], "providerRef": wallet.get("provider_ref"), "status": wallet["status"],
            "did": wallet.get("did"), "didDocumentLocation": wallet.get("did_document_location"),
            "credentialServiceUrl": wallet.get("credential_service_url"),
            "issuanceMode": _issuance_mode(wallet["provider"]), "supportsWalletAccounts": True,
            "failureReason": wallet.get("failure_reason"), "activatedAt": service.iso(wallet.get("activated_at"))}


def wallet_view(company_id: str) -> dict:
    """README 7.1 openapi `Wallet`: the view of the people of the company, no secrets."""
    wallet = _wallet_or_404(company_id)
    return {"companyId": wallet["company_id"], "provider": wallet["provider"], "status": wallet["status"],
            "did": wallet.get("did"), "didDocumentLocation": wallet.get("did_document_location"),
            "credentialServiceUrl": wallet.get("credential_service_url"),
            "bdrsUrl": os.environ.get("BDRS_PUBLIC_URL", "").strip() or None,
            "stsTokenUrl": (os.environ.get("IDENTITYHUB_STS_TOKEN_URL", "").strip() or None)
            if wallet["provider"] == "IDENTITY_HUB" else None,
            "supportsWalletAccounts": True, "failureReason": wallet.get("failure_reason"),
            "createdAt": service.iso(wallet.get("created_at")), "activatedAt": service.iso(wallet.get("activated_at"))}


def holder_access(company_id: str, claims: dict | str | None = None) -> dict:
    """README 9.3 for C4-M1: how credentials get into the wallet, with the access needed for that.
    `claims` are the token claims over HTTP; in the same process the entry holds the name of C4-M1."""
    wallet = _wallet_or_404(company_id)
    if wallet["status"] != "ACTIVE":
        raise errors.wallet_not_active("the wallet is not ACTIVE")
    access = service.wallet_secret(wallet["id"], service.HOLDER_ACCESS)
    if access is None:
        raise errors.wallet_not_active("the wallet has no holder access")
    base = {"issuanceMode": _issuance_mode(wallet["provider"]), "companyId": wallet["company_id"],
            "bpn": wallet["bpn"], "did": wallet["did"], "provider": wallet["provider"]}
    if wallet["provider"] == "SAP_DIV":
        base.update(holder=wallet["did_document_location"], walletUrl=access["url"],
                    clientId=access["client_id"], clientSecret=access["secret"])
    else:
        base.update(identityApiUrl=access["url"], participantContextId=access["client_id"],
                    apiKey=access["secret"], credentialServiceUrl=wallet.get("credential_service_url"))
    service.audit(claims if claims is not None else "c4-m1", "READ_HOLDER_ACCESS", wallet["company_id"], wallet["id"])
    return base
