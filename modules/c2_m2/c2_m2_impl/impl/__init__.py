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
"""Implementations of the service interfaces of c2_m2_api/service and of c2_m2_impl/internal/services."""
from modules.c2_m2.c2_m2_impl.config import Config
from modules.c2_m2.c2_m2_impl.internal.services import PortalIam

from .app_client_service_impl import AppClientServiceImpl
from .company_profile_gateway_impl import CompanyProfileGatewayImpl
from .invitation_cleanup_job_impl import InvitationCleanupJobImpl
from .invitation_service_impl import InvitationServiceImpl
from .keycloak_portal_iam import KeycloakPortalIam
from .neighbour_gateway import NeighbourGateway
from .postgres_database import PostgresDatabase
from .subscriptions_gateway_impl import SubscriptionsGatewayImpl
from .user_service_impl import UserServiceImpl


def portal_iam(config: Config) -> PortalIam:
    """The Keycloak Admin API at `IAM_URL`."""
    return KeycloakPortalIam(config)


__all__ = ["AppClientServiceImpl", "CompanyProfileGatewayImpl", "InvitationCleanupJobImpl", "InvitationServiceImpl", "KeycloakPortalIam", "NeighbourGateway",
           "PostgresDatabase", "SubscriptionsGatewayImpl", "UserServiceImpl", "portal_iam"]
