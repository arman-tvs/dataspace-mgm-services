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
"""Queries about app roles and instance clients for other modules (README 9.1 to 9.3), `query_c2_m2`."""
from abc import abstractmethod
from typing import Annotated

from fastapi import Path, Query

from modules.c2_m2.c2_m2_rs_api.endpoint import Claims, Lang, RestApi, StatusFilter, api

AppIds = Annotated[list[str] | None, Query(alias="appId")]
AppFilter = Annotated[str | None, Query(alias="appId")]
OfferSubscriptionFilter = Annotated[str | None, Query(alias="offerSubscriptionId")]
CustomerCompanyFilter = Annotated[str | None, Query(alias="customerCompanyId")]
InstanceKindFilter = Annotated[str | None, Query(alias="instanceKind")]
InstanceClientId = Annotated[str, Path(alias="id")]


class AppClientQueriesApi(RestApi):
    @api.get("/internal/app-roles")
    @abstractmethod
    def list_app_roles(self, claims: Claims, app_ids: AppIds = None, lang: Lang = None) -> list[dict]: ...

    @api.get("/internal/app-instance-clients")
    @abstractmethod
    def list_app_instance_clients(self, claims: Claims, app_id: AppFilter = None,
                                  offer_subscription_id: OfferSubscriptionFilter = None,
                                  customer_company_id: CustomerCompanyFilter = None,
                                  instance_kind: InstanceKindFilter = None,
                                  status: StatusFilter = None) -> list[dict]: ...

    @api.get("/internal/app-instance-clients/{id}")
    @abstractmethod
    def get_app_instance_client(self, claims: Claims, instance_client_id: InstanceClientId) -> dict: ...
