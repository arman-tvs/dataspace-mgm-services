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
"""Query of the people of a company for other modules (README 9.4), `query_c2_m2`."""
from abc import abstractmethod
from typing import Annotated

from fastapi import Query

from modules.c2_m2.c2_m2_rs_api.endpoint import UUID_PATTERN, Claims, RestApi, StatusFilter, api

# A string on purpose: the interface takes `companyId` as str; the pattern rejects non-UUIDs with 400.
CompanyFilter = Annotated[str | None, Query(alias="companyId", pattern=UUID_PATTERN)]
PortalRoleFilter = Annotated[str | None, Query(alias="portalRole")]


class CompanyUserQueriesApi(RestApi):
    @api.get("/internal/company-users")
    @abstractmethod
    def list_company_user_refs(self, claims: Claims, company_id: CompanyFilter = None,
                               portal_role: PortalRoleFilter = None,
                               status: StatusFilter = None) -> list[dict]: ...
