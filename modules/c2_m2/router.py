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
#  Assisted-By: GitHub Copilot
#################################################################################
"""Scaffold entry point of C2-M2: `router`, `reset()` and `on_startup()` (AGENTS.md, module folder).
The endpoints are defined in c2_m2_rs_api and implemented in c2_m2_rs_service/producer/impl."""
import logging

from . import interface, module
from .c2_m2_impl.config import Config
from .c2_m2_rs_service.routers import private_router, public_router, router

__all__ = ["on_startup", "private_router", "public_router", "reset", "router"]

log = logging.getLogger(__name__)


def reset() -> None:
    interface.reset()


def on_startup() -> None:
    # Without a database the installation still starts; calls of C2-M2 fail until DATABASE_URL is set.
    if not Config().from_properties("database.url"):
        log.warning("C2-M2 has no database (DATABASE_URL, README 4): bootstrap and invitation cleanup skipped")
        return
    module.current().on_startup()
