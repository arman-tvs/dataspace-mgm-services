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
"""C2-M2 as a service of its own (FRAMEWORK 4.7: a split-out module, reached over HTTP).

    SETTINGS_FILE=config/osp-a/installation.json BASE_URL=http://localhost:8202 \
    DATABASE_URL=postgresql://... IAM_URL=http://localhost:8080/auth IAM_REALM=CX-Central \
        uv run uvicorn --factory modules.c2_m2.c2_m2_rs_service.main:create_app --port 8202

    uv run python -m modules.c2_m2.c2_m2_rs_service.main --port 8202

Serves the public and the private API under /api/c2-m2, plus /health and Swagger at /docs.
Neighbours (C3-M1, Subscriptions) are reached through `C3_M1_URL`, `C10_M1_URL` or `MODULE_URLS`;
without an address C2-M2 uses its built-in stand-ins (README 11.2). Without `IAM_URL` and with
`TEST_TOOLS` not `false`, the scaffold's in-memory test IAM is mounted at /auth, as in the installation.
"""
from __future__ import annotations

import argparse
import contextlib
import os

from fastapi import FastAPI

from portal_common import events, http, problems, settings, tokens

from modules.c2_m2 import module
from modules.c2_m2.c2_m2_api.model.utils import MODULE
from modules.c2_m2.c2_m2_rs_service.routers import router


def _uses_test_iam() -> bool:
    return not os.environ.get("IAM_URL") and os.environ.get("TEST_TOOLS", "true") == "true"


def create_app() -> FastAPI:
    settings.load()
    tokens.reset()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        events.RELAY.start()
        module.current().on_startup()   # fails at once without DATABASE_URL (README 4)
        try:
            yield
        finally:
            module.reset()
            events.RELAY.stop()

    app = FastAPI(title=f"C2-M2 Users and App Access ({settings.get('ospName')})", lifespan=lifespan)
    problems.install(app, MODULE)
    if _uses_test_iam():
        from tools import test_iam
        test_iam.reset()
        app.include_router(test_iam.router)
    app.include_router(router)

    @app.get("/health", tags=["Service"])
    def health():
        return {"status": "UP", "module": MODULE}

    http.register_local(settings.base_url(), app)   # token keys of the test IAM without a network hop
    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="Run C2-M2 Users and App Access as its own service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(create_app, factory=True, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
