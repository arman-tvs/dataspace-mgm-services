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
"""Exceptions the implementation of C2-M2 raises; all derive from `C2M2BaseException`.
The REST layer translates them to HTTP answers."""
from .c2_m2_base_exception import C2M2BaseException
from .validation import UnknownAppRoleException, ValidationException
from .not_found import InvitationNotFoundException, NotFoundException, RoleNotFoundException, UserNotFoundException
from .app_client import InstanceExistsException, NoActiveSubscriptionException, TemplateMissingException
from .company import (CompanyNotActiveException, ConflictException, InvalidStateException, LastCompanyAdminException,
                      LastOspAdminException, StaffCompanyConflictException, UserAlreadyBoundException)
from .invitation import InvitationNotOpenException, NameMismatchException, TooManyInvitationsException
from .external import IamErrorException, UpstreamErrorException

ALL_EXCEPTIONS: tuple[type[C2M2BaseException], ...] = (
    ValidationException, UnknownAppRoleException,
    NotFoundException, UserNotFoundException, RoleNotFoundException, InvitationNotFoundException,
    TemplateMissingException, InstanceExistsException, NoActiveSubscriptionException,
    InvalidStateException, ConflictException, CompanyNotActiveException, UserAlreadyBoundException,
    StaffCompanyConflictException, LastCompanyAdminException, LastOspAdminException,
    InvitationNotOpenException, NameMismatchException, TooManyInvitationsException,
    IamErrorException, UpstreamErrorException,
)

__all__ = ["ALL_EXCEPTIONS", "C2M2BaseException", *(e.__name__ for e in ALL_EXCEPTIONS)]
