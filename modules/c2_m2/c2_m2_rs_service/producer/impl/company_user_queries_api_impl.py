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
from modules.c2_m2.c2_m2_rs_api.apis import CompanyUserQueriesApi


class CompanyUserQueriesApiImpl(CompanyUserQueriesApi):
    def list_company_user_refs(self, claims: dict, company_id: str | None = None, portal_role: str | None = None,
                               status: list[str] | None = None) -> list[dict]:
        return interface.list_company_user_refs(companyId=company_id, portalRole=portal_role, status=status)
