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
"""Models of C2-M2 exposed outside the module (shapes of openapi.yaml)."""
from .api_model import ApiModel
from .common import Actor, Page, StepResult
from .app_client import (AppInstanceClient, AppRole, AppRoles, CompanyAppRoles, InstanceClientRef,
                         RoleDescription)
from .people import (AppRolesResult, CompanyUser, CompanyUserDetail, CompanyUserRef, StaffMember, UserAccount,
                     UserClientRoles)
from .invitation import AcceptInvitationResult, Invitation, InvitationWithCode
from .steps import (AddAppRolesResult, AssignCompanyAdminResult, CompanyUsersResult, TemplateResult,
                    UpdateRoleDescriptionsResult)

__all__ = [
    "ApiModel", "Actor", "Page", "StepResult",
    "CompanyUser", "CompanyUserDetail", "CompanyUserRef", "UserAccount", "UserClientRoles", "AppRolesResult",
    "StaffMember",
    "Invitation", "InvitationWithCode", "AcceptInvitationResult",
    "AppInstanceClient", "InstanceClientRef", "RoleDescription", "AppRole", "AppRoles", "CompanyAppRoles",
    "TemplateResult", "AddAppRolesResult", "UpdateRoleDescriptionsResult", "AssignCompanyAdminResult",
    "CompanyUsersResult",
]
