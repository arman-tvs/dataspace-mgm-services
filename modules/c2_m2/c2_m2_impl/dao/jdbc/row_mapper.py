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

from typing import Any

from modules.c2_m2.c2_m2_api.model.common import Actor
from modules.c2_m2.c2_m2_api.model.constants import ActorType


class RowMapper:
    """Base of the row mappers: a table's columns, a model as parameters, and a database row as a model.
    The driver returns uuid columns as `uuid.UUID`; the internal models keep IDs as strings."""

    TABLE: str = ""
    KEY: str = ""
    COLUMNS: tuple[str, ...] = ()
    CASTS: dict[str, str] = {}

    @staticmethod
    def text(value: Any) -> str | None:
        return None if value is None else str(value)

    @staticmethod
    def actor_params(actor: Actor) -> tuple:
        return str(actor.type), actor.sub, actor.process_id, actor.step_run_id

    @classmethod
    def actor_from(cls, row: dict) -> Actor:
        return Actor(ActorType(row["actor_type"]), sub=cls.text(row["actor_sub"]),
                     process_id=cls.text(row["process_id"]), step_run_id=cls.text(row["step_run_id"]))
