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
"""What the core of C4-M2 needs from a wallet provider (README 6.11): the port its adapters implement."""
from __future__ import annotations

from typing import Protocol


class WalletProvider(Protocol):
    """A dataspace wallet provider: SAP DIV, IdentityHub or the wallet of the CSP.

    `order_wallet` answers `{"result": "CREATED", "did", "did_document_location", "credential_service_url",
    "provider_ref", "secrets"}` when the wallet exists at once, otherwise `{"result": "ORDERED"}` and the provider
    calls back (README 7.6). `order_account` and `order_account_deletion` work the same way for wallet accounts.
    Provider errors are `errors.upstream_error` (retryable) or `errors.provider_rejected`."""

    provider: str
    supports_wallet_accounts: bool
    issuance_mode: str
    deletion_is_async: bool

    def did_for(self, bpn: str) -> str | None:
        """The DID the provider must use for `bpn`; None if only the form `did:web:` is checked."""
        ...

    def order_wallet(self, order: dict) -> dict:
        ...

    def order_account(self, order: dict) -> dict:
        ...

    def order_account_deletion(self, account: dict) -> dict:
        ...
