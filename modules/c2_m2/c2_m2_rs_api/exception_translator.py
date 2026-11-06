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
from __future__ import annotations

from portal_common import problems
from portal_common.problems import Problem

from modules.c2_m2.c2_m2_api.exception import (
    C2M2BaseException, CompanyNotActiveException, ConflictException, IamErrorException, InstanceExistsException,
    InvalidStateException, InvitationNotFoundException, InvitationNotOpenException, LastCompanyAdminException,
    LastOspAdminException, NameMismatchException, NoActiveSubscriptionException, NotFoundException,
    RoleNotFoundException, StaffCompanyConflictException, TemplateMissingException, TooManyInvitationsException,
    UnknownAppRoleException, UpstreamErrorException, UserAlreadyBoundException, UserNotFoundException,
    ValidationException)
from modules.c2_m2.c2_m2_api.model.utils import MODULE


class ExceptionTranslator:
    """Exceptions of the implementation as Problem Details: HTTP status and `type` of README section 12."""

    RULES: dict[type[C2M2BaseException], tuple[int, str]] = {
        ValidationException: (400, "validation"),
        UnknownAppRoleException: (400, "unknown-app-role"),
        NameMismatchException: (403, "name-mismatch"),
        NotFoundException: (404, "not-found"),
        RoleNotFoundException: (404, "role-not-found"),
        InvitationNotFoundException: (404, "invitation-not-found"),
        UserNotFoundException: (404, "user-not-found"),
        TemplateMissingException: (409, "template-missing"),
        InstanceExistsException: (409, "instance-exists"),
        InvalidStateException: (409, "invalid-state"),
        ConflictException: (409, "conflict"),
        InvitationNotOpenException: (409, "invitation-not-open"),
        UserAlreadyBoundException: (409, "user-already-bound"),
        StaffCompanyConflictException: (409, "staff-company-conflict"),
        LastCompanyAdminException: (409, "last-company-admin"),
        LastOspAdminException: (409, "last-osp-admin"),
        TooManyInvitationsException: (409, "too-many-invitations"),
        CompanyNotActiveException: (409, "company-not-active"),
        NoActiveSubscriptionException: (409, "no-active-subscription"),
        IamErrorException: (502, "iam-error"),
        UpstreamErrorException: (502, "upstream-error"),
    }

    @classmethod
    def rule(cls, exc: C2M2BaseException) -> tuple[int, str]:
        for kind in type(exc).__mro__:
            if kind in cls.RULES:
                return cls.RULES[kind]
        return 500, "internal-error"

    @classmethod
    def to_problem(cls, exc: Exception, is_step: bool = False) -> Problem:
        """Steps always carry `retryable` (FRAMEWORK 4.4); other errors go through the shared rule."""
        if not isinstance(exc, C2M2BaseException):
            return problems.to_problem(MODULE, exc, is_step)
        status, name = cls.rule(exc)
        ext = dict(exc.details)
        if is_step or exc.retryable is not None:
            ext["retryable"] = exc.retryable if exc.retryable is not None else status >= 500
        return Problem(MODULE, status, name, detail=exc.detail, **ext)
