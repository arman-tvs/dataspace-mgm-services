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
"""Public interface of C2-M2 Users and App Access: the steps of README section 8 and the queries of
section 9, called in-process without a token (AGENTS.md, call convention)."""
from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from . import module
from .c2_m2_api.exception import C2M2BaseException
from .c2_m2_api.model.utils import MODULE
from .c2_m2_rs_api import ExceptionTranslator

__all__ = [
    "MODULE", "add_app_roles", "assign_company_admin", "create_client_template", "create_instance_client",
    "disable_company_users", "disable_instance_client", "enable_company_users", "enable_instance_client",
    "get_app_instance_client", "list_app_instance_clients", "list_app_roles", "list_company_user_refs", "reset",
    "update_instance_url", "update_role_descriptions",
]


def reset() -> None:
    module.reset()


def _json(value):
    """The JSON body of the HTTP form (call convention): models as camelCase dicts."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_json(v) for v in value]
    return value


def _step(input: dict, action: Callable[[dict], BaseModel]) -> dict:
    """Step answer of FRAMEWORK 4.4; errors as Problem Details that always carry `retryable` (README 12)."""
    try:
        result = action(input if isinstance(input, dict) else {})
    except C2M2BaseException as exc:
        raise ExceptionTranslator.to_problem(exc, is_step=True) from exc
    return {"stepRunId": input.get("stepRunId"), "state": "DONE", "result": _json(result)}


def _query(action: Callable[[], object]):
    try:
        return _json(action())
    except C2M2BaseException as exc:
        raise ExceptionTranslator.to_problem(exc) from exc


def _as_list(value: list[str] | str | None) -> list[str]:
    return [value] if isinstance(value, str) else list(value or [])


# -- steps (section 8) ------------------------------------------------------------------------------
def create_client_template(input: dict) -> dict:
    return _step(input, module.current().apps.create_client_template)


def create_instance_client(input: dict) -> dict:
    return _step(input, module.current().apps.create_instance_client)


def enable_instance_client(input: dict) -> dict:
    return _step(input, module.current().apps.enable_instance_client)


def disable_instance_client(input: dict) -> dict:
    return _step(input, module.current().apps.disable_instance_client)


def update_instance_url(input: dict) -> dict:
    return _step(input, module.current().apps.update_instance_url)


def add_app_roles(input: dict) -> dict:
    return _step(input, module.current().apps.add_app_roles)


def update_role_descriptions(input: dict) -> dict:
    return _step(input, module.current().apps.update_role_descriptions)


def assign_company_admin(input: dict) -> dict:
    return _step(input, module.current().users.assign_company_admin)


def disable_company_users(input: dict) -> dict:
    return _step(input, module.current().users.disable_company_users)


def enable_company_users(input: dict) -> dict:
    return _step(input, module.current().users.enable_company_users)


# -- queries (section 9) ----------------------------------------------------------------------------
def list_app_roles(*, appId: list[str] | str | None = None, lang: str | None = None, **_other) -> list[dict]:
    return _query(lambda: module.current().apps.list_app_roles(_as_list(appId), lang))


def list_app_instance_clients(*, appId: str | None = None, offerSubscriptionId: str | None = None,
                              customerCompanyId: str | None = None, instanceKind: str | None = None,
                              status: list[str] | str | None = None, **_other) -> list[dict]:
    return _query(lambda: module.current().apps.list_app_instance_clients(
        app_id=appId, offer_subscription_id=offerSubscriptionId, customer_company_id=customerCompanyId,
        instance_kind=instanceKind, statuses=_as_list(status)))


def get_app_instance_client(*, id: str) -> dict:  # noqa: A002 - openapi name
    return _query(lambda: module.current().apps.get_app_instance_client(id))


def list_company_user_refs(*, companyId: str | None = None, portalRole: str | None = None,
                           status: list[str] | str | None = None, **_other) -> list[dict]:
    return _query(lambda: module.current().users.list_company_user_refs(companyId, portalRole, status))
