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
"""Endpoint interfaces of C2-M2, one per use case. PUBLIC_APIS form openapi.yaml, PRIVATE_APIS openapi-private.yaml."""
from .app_client_queries_api import AppClientQueriesApi
from .app_client_steps_api import AppClientStepsApi
from .company_app_roles_api import CompanyAppRolesApi
from .company_invitations_api import CompanyInvitationsApi
from .company_user_queries_api import CompanyUserQueriesApi
from .company_user_steps_api import CompanyUserStepsApi
from .company_users_api import CompanyUsersApi
from .invitation_acceptance_api import InvitationAcceptanceApi
from .osp_company_invitations_api import OspCompanyInvitationsApi
from .osp_staff_api import OspStaffApi
from .osp_staff_invitations_api import OspStaffInvitationsApi
from .osp_users_api import OspUsersApi

PUBLIC_APIS = (
    CompanyUsersApi, CompanyAppRolesApi, CompanyInvitationsApi, InvitationAcceptanceApi,
    OspUsersApi, OspCompanyInvitationsApi, OspStaffApi, OspStaffInvitationsApi,
)
PRIVATE_APIS = (AppClientQueriesApi, CompanyUserQueriesApi, AppClientStepsApi, CompanyUserStepsApi)

__all__ = [
    "PRIVATE_APIS", "PUBLIC_APIS", "AppClientQueriesApi", "AppClientStepsApi", "CompanyAppRolesApi",
    "CompanyInvitationsApi", "CompanyUserQueriesApi", "CompanyUserStepsApi", "CompanyUsersApi",
    "InvitationAcceptanceApi", "OspCompanyInvitationsApi", "OspStaffApi", "OspStaffInvitationsApi", "OspUsersApi",
]
