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
"""Implementations of the endpoint interfaces of c2_m2_rs_api, one class per use case."""
from .app_client_queries_api_impl import AppClientQueriesApiImpl
from .app_client_steps_api_impl import AppClientStepsApiImpl
from .company_app_roles_api_impl import CompanyAppRolesApiImpl
from .company_invitations_api_impl import CompanyInvitationsApiImpl
from .company_user_queries_api_impl import CompanyUserQueriesApiImpl
from .company_user_steps_api_impl import CompanyUserStepsApiImpl
from .company_users_api_impl import CompanyUsersApiImpl
from .invitation_acceptance_api_impl import InvitationAcceptanceApiImpl
from .osp_company_invitations_api_impl import OspCompanyInvitationsApiImpl
from .osp_staff_api_impl import OspStaffApiImpl
from .osp_staff_invitations_api_impl import OspStaffInvitationsApiImpl
from .osp_users_api_impl import OspUsersApiImpl

__all__ = [
    "AppClientQueriesApiImpl", "AppClientStepsApiImpl", "CompanyAppRolesApiImpl", "CompanyInvitationsApiImpl",
    "CompanyUserQueriesApiImpl", "CompanyUserStepsApiImpl", "CompanyUsersApiImpl", "InvitationAcceptanceApiImpl",
    "OspCompanyInvitationsApiImpl", "OspStaffApiImpl", "OspStaffInvitationsApiImpl", "OspUsersApiImpl",
]
