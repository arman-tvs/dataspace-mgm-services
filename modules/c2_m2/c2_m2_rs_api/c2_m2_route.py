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

from fastapi import Request
from fastapi.routing import APIRoute

from .exception_translator import ExceptionTranslator


class C2M2Route(APIRoute):
    """Route class of the C2-M2 router: every error leaves as Problem Details via `ExceptionTranslator`."""

    def get_route_handler(self):
        original = super().get_route_handler()
        is_step = "/steps/" in self.path

        async def handler(request: Request):
            try:
                return await original(request)
            except Exception as exc:  # noqa: BLE001 - every error leaves as Problem Details
                return ExceptionTranslator.to_problem(exc, is_step).response()

        return handler
