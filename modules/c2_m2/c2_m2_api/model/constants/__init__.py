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
"""Enumerations of C2-M2 (README sections 5 and 6, openapi.yaml): one class per file."""
from .actor_type_enum import ActorType
from .binding_status_enum import BindingStatus
from .company_status_enum import CompanyStatus
from .instance_client_status_enum import InstanceClientStatus
from .instance_kind_enum import InstanceKind
from .invitation_end_reason_enum import InvitationEndReason
from .invitation_kind_enum import InvitationKind
from .invitation_status_enum import InvitationStatus
from .joined_via_enum import JoinedVia
from .removal_reason_enum import RemovalReason
from .role_kind_enum import RoleKind

__all__ = [
    "ActorType", "BindingStatus", "CompanyStatus", "InstanceClientStatus", "InstanceKind", "InvitationEndReason",
    "InvitationKind", "InvitationStatus", "JoinedVia", "RemovalReason", "RoleKind",
]
