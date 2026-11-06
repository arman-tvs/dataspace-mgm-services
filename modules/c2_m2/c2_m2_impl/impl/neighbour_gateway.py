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

import json
from pathlib import Path

from modules.c2_m2.c2_m2_api.exception import UpstreamErrorException
from modules.c2_m2.c2_m2_api.model.utils import MODULE
from portal_common import neighbours
from portal_common.problems import Problem

HERE = Path(__file__).resolve().parent


class NeighbourGateway:
    """A neighbouring module with its built-in stand-in (FRAMEWORK 4.7): empty address = stub file."""

    TARGET: str = ""
    STUB_FILE: str = ""

    def is_standin(self) -> bool:
        return neighbours.is_standin(self.TARGET)

    def stub_items(self) -> list[dict]:
        return json.loads((HERE / self.STUB_FILE).read_text(encoding="utf-8"))["items"]

    def query(self, function: str, **params):
        """None means 404; any other failure is an upstream error (README 11.2)."""
        try:
            return neighbours.query(MODULE, self.TARGET, function, **params)
        except Problem as p:
            raise UpstreamErrorException(p.detail or f"{self.TARGET} did not answer as expected",
                                         retryable=bool(p.ext.get("retryable", True))) from p
