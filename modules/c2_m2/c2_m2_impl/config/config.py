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
"""Configuration of C2-M2 (README section 4), kept in an `application.properties` file.

`C2_M2_CONFIG_FILE` names the file; without it the bundled `application.properties` next to this module is used.
Values may refer to the environment with `${NAME:default}` (see `properties.py`)."""
from __future__ import annotations

import os
from pathlib import Path

from . import properties

CONFIG_FILE_VARIABLE = "C2_M2_CONFIG_FILE"
DEFAULT_CONFIG_FILE = Path(__file__).with_name("application.properties")


def config_file() -> Path:
    return Path(os.environ.get(CONFIG_FILE_VARIABLE) or DEFAULT_CONFIG_FILE)


class Config:
    """The file of `C2_M2_CONFIG_FILE` (or `path`), read once at creation, never at import (AGENTS.md rule 6)."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.config_file = Path(path) if path else config_file()
        if not self.config_file.is_file():
            raise RuntimeError(f"C2-M2 configuration file not found: {self.config_file} ({CONFIG_FILE_VARIABLE})")
        self._properties = properties.load(self.config_file)

    def from_properties(self, name: str) -> str:
        """The value of `name` in the file; an empty string means not set. A missing key is a configuration error."""
        try:
            return self._properties[name]
        except KeyError:
            raise RuntimeError(f"C2-M2 configuration: {name} missing in {self.config_file}") from None
