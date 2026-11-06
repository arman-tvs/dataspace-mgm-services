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

import abc
from contextlib import AbstractContextManager

from modules.c2_m2.c2_m2_impl.internal.model import AppClientTemplate


class AppClientTemplateDao(abc.ABC):
    """Table `app_client_template`: one client template per app."""

    @abc.abstractmethod
    def lock(self, app_id: str) -> AbstractContextManager[None]:
        """Lock `app` of 6.14 (the template and all instance clients of the app) until the transaction ends."""

    @abc.abstractmethod
    def get(self, app_id: str) -> AppClientTemplate | None: ...

    @abc.abstractmethod
    def save(self, template: AppClientTemplate) -> None: ...
