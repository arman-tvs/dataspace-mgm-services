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
from modules.c2_m2.c2_m2_api.model.api_model import ApiModel

from .company_user import CompanyUser
from .user_client_roles import UserClientRoles


class UserAccount(ApiModel):
    """Returned when OSP staff read any account of the installation, also without a company (7.12)."""
    user_id: str
    given_name: str | None = None
    family_name: str | None = None
    enabled: bool
    created_at: str | None = None
    binding: CompanyUser | None = None
    portal_roles: list[str]
    staff_roles: list[str]
    app_roles: list[UserClientRoles]
