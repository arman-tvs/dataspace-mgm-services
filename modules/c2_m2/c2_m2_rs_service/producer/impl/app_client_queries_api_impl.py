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
from modules.c2_m2 import interface
from modules.c2_m2.c2_m2_rs_api.apis import AppClientQueriesApi


class AppClientQueriesApiImpl(AppClientQueriesApi):
    """Queries over HTTP give the same answer as the in-process interface, which keeps the contract's
    parameter names (call convention)."""

    def list_app_roles(self, claims: dict, app_ids: list[str] | None = None, lang: str | None = None) -> list[dict]:
        return interface.list_app_roles(appId=app_ids, lang=lang)

    def list_app_instance_clients(self, claims: dict, app_id: str | None = None,
                                  offer_subscription_id: str | None = None,
                                  customer_company_id: str | None = None, instance_kind: str | None = None,
                                  status: list[str] | None = None) -> list[dict]:
        return interface.list_app_instance_clients(appId=app_id, offerSubscriptionId=offer_subscription_id,
                                                   customerCompanyId=customer_company_id,
                                                   instanceKind=instance_kind, status=status)

    def get_app_instance_client(self, claims: dict, instance_client_id: str) -> dict:
        return interface.get_app_instance_client(id=instance_client_id)
