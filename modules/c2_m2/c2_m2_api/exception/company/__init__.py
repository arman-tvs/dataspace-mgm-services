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
"""Errors of companies, bindings and the limits of 6.7."""
from .company_not_active_exception import CompanyNotActiveException
from .conflict_exception import ConflictException
from .invalid_state_exception import InvalidStateException
from .last_company_admin_exception import LastCompanyAdminException
from .last_osp_admin_exception import LastOspAdminException
from .staff_company_conflict_exception import StaffCompanyConflictException
from .user_already_bound_exception import UserAlreadyBoundException

__all__ = ["CompanyNotActiveException", "ConflictException", "InvalidStateException", "LastCompanyAdminException",
           "LastOspAdminException", "StaffCompanyConflictException", "UserAlreadyBoundException"]
