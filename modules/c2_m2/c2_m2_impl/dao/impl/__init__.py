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
"""PostgreSQL implementations of the DAO interfaces."""
from modules.c2_m2.c2_m2_impl.dao.dao_service import DaoService
from modules.c2_m2.c2_m2_impl.internal.services import Database

from .postgres_app_client_template_dao import PostgresAppClientTemplateDao
from .postgres_app_instance_client_dao import PostgresAppInstanceClientDao
from .postgres_audit_log_dao import PostgresAuditLogDao
from .postgres_company_dao import PostgresCompanyDao
from .postgres_company_user_dao import PostgresCompanyUserDao
from .postgres_invitation_dao import PostgresInvitationDao
from .postgres_role_assignment_log_dao import PostgresRoleAssignmentLogDao


def postgres_dao_service(db: Database) -> DaoService:
    return DaoService(db, PostgresAppClientTemplateDao(db), PostgresAppInstanceClientDao(db), PostgresCompanyDao(db),
                      PostgresCompanyUserDao(db), PostgresInvitationDao(db), PostgresAuditLogDao(db),
                      PostgresRoleAssignmentLogDao(db))


__all__ = ["PostgresAppClientTemplateDao", "PostgresAppInstanceClientDao", "PostgresAuditLogDao", "PostgresCompanyDao",
           "PostgresCompanyUserDao", "PostgresInvitationDao", "PostgresRoleAssignmentLogDao", "postgres_dao_service"]
