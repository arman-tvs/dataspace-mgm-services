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
#  Assisted-By: GitHub Copilot (Claude Sonnet 5.5)
#################################################################################
"""Input checks of the operations and steps (README 7 and 8) beyond the schemas: every failure is 400 `validation`.
Checking a body against its `openapi.yaml` schema is `schemas.parse` (the HTTP models stay at the edge, ADR-0003)."""
from __future__ import annotations

from modules.c2_m3 import errors


def validate_page(page: int, size: int) -> None:
    if page < 0 or not 1 <= size <= 100:
        raise errors.validation("page must be >= 0 and size must be 1..100")
