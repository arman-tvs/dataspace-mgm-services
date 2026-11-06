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
"""The routers of C2-M2: endpoint interfaces of c2_m2_rs_api bound to the implementations of producer/impl."""
from fastapi import APIRouter

from modules.c2_m2.c2_m2_rs_api import create_router
from modules.c2_m2.c2_m2_rs_service.producer import private_implementations, public_implementations

public_router = create_router(public_implementations(), public=True)
private_router = create_router(private_implementations(), public=False)

router = APIRouter()
# Concrete APIRoute objects, so the scaffold sees which spec operations are implemented.
router.routes.extend(public_router.routes)
router.routes.extend(private_router.routes)
