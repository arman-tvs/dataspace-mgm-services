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
"""Data access objects of C2-M2: one interface per table of README section 5."""
from .app_client_template_dao import AppClientTemplateDao
from .app_instance_client_dao import AppInstanceClientDao
from .audit_log_dao import AuditLogDao
from .company_dao import CompanyDao
from .company_user_dao import CompanyUserDao
from .dao_service import DaoService
from .invitation_dao import InvitationDao
from .role_assignment_log_dao import RoleAssignmentLogDao

__all__ = ["AppClientTemplateDao", "AppInstanceClientDao", "AuditLogDao", "CompanyDao", "CompanyUserDao",
           "DaoService", "InvitationDao", "RoleAssignmentLogDao"]
