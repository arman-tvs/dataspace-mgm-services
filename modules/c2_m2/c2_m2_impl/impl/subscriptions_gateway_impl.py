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

from modules.c2_m2.c2_m2_api.exception import UpstreamErrorException
from modules.c2_m2.c2_m2_impl.internal.services import SubscriptionsGateway

from .neighbour_gateway import NeighbourGateway


class SubscriptionsGatewayImpl(NeighbourGateway, SubscriptionsGateway):
    """Subscriptions (C10-M1): active subscriptions of a company to an app (6.10)."""

    TARGET = "c10-m1"
    STUB_FILE = "stub-subscriptions.json"

    def active_subscriptions(self, customer_company_id: str, offer_id: str) -> list[dict]:
        if self.is_standin():
            return [s for s in self.stub_items() if s["customerCompanyId"] == customer_company_id
                    and s["offerId"] == offer_id and s["status"] == "ACTIVE"]
        found = self.query("find_subscriptions", customerCompanyId=customer_company_id, offerId=offer_id,
                           status="ACTIVE")
        # Only an actual list is an answer; a 404 (None) or any other shape is an upstream error (README 11.2).
        if not isinstance(found, list):
            raise UpstreamErrorException(f"{self.TARGET} find_subscriptions gave no subscription list",
                                         retryable=True)
        return [s for s in found if isinstance(s, dict) and s.get("status") == "ACTIVE"]
