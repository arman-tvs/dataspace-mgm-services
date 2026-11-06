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
"""Interfaces of the internal services: Portal IAM, database, neighbouring modules, background job.
The implementations live in c2_m2_impl/impl."""
from .company_profile_gateway import CompanyProfileGateway
from .database import Database
from .invitation_cleanup_job import InvitationCleanupJob
from .portal_iam import PortalIam, iam_error
from .subscriptions_gateway import SubscriptionsGateway

__all__ = ["CompanyProfileGateway", "Database", "InvitationCleanupJob", "PortalIam",
           "SubscriptionsGateway", "iam_error"]
