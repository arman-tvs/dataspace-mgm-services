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

import unicodedata

from .invitation import Invitation


class NameCheck:
    """Names of the token against the invitation, compared as in C5-M1 6.5: NFC, outer spaces removed, case ignored."""

    @staticmethod
    def normalize(value: str | None) -> str | None:
        return unicodedata.normalize("NFC", value).strip().casefold() if value else None

    @classmethod
    def matches(cls, claims: dict, invitation: Invitation) -> bool:
        given, family = cls.normalize(claims.get("given_name")), cls.normalize(claims.get("family_name"))
        return bool(given and family) and (given, family) == (cls.normalize(invitation.given_name),
                                                              cls.normalize(invitation.family_name))
