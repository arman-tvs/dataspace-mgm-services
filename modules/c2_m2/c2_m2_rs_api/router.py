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
"""Builds the FastAPI routers of C2-M2 from the endpoint interfaces (`apis/`) and the contract YAML.

The interfaces say at which method and path each `def` is exposed. The contract adds operationId,
summary, permission, scope and the request and response schemas. Implementations are injected:
this package never imports them.
"""
from __future__ import annotations

import inspect
import typing
from collections.abc import Callable, Iterable
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer

from modules.c2_m2.c2_m2_api.model.utils import MODULE
from portal_common import tokens

from .apis import PRIVATE_APIS, PUBLIC_APIS
from .c2_m2_route import C2M2Route
from .contract import Json, load_contract, operations, resolve_object
from .endpoint import AUTHENTICATED, Endpoint, RestApi

# Declares the bearer scheme for Swagger; the token itself is checked per operation (AUTHENTICATED).
_bearer = HTTPBearer(scheme_name="portalIam", bearerFormat="JWT", auto_error=False)


def apis(*, public: bool) -> tuple[type[RestApi], ...]:
    return PUBLIC_APIS if public else PRIVATE_APIS


def _assign(implementations: Iterable[RestApi], interfaces: tuple[type[RestApi], ...]) -> dict:
    assigned: dict[type[RestApi], RestApi] = {}
    for implementation in implementations:
        matches = [api for api in interfaces if isinstance(implementation, api)]
        if not matches:
            raise TypeError(f"{type(implementation).__name__} implements none of "
                            f"{', '.join(api.__name__ for api in interfaces)}")
        for api in matches:
            if api in assigned:
                raise ValueError(f"{api.__name__} is implemented by {type(assigned[api]).__name__} "
                                 f"and {type(implementation).__name__}")
            assigned[api] = implementation
    missing = [api.__name__ for api in interfaces if api not in assigned]
    if missing:
        raise ValueError(f"no implementation for {', '.join(missing)}")
    return assigned


def _authenticated(annotation: object) -> bool:
    """True for the `Claims` annotation (`Annotated[..., AUTHENTICATED]`) of an endpoint parameter."""
    return (typing.get_origin(annotation) is typing.Annotated
            and AUTHENTICATED in getattr(annotation, "__metadata__", ()))


def _endpoint_function(declaration: Callable, implementation: RestApi, endpoint: Endpoint) -> Callable:
    """A function with the signature of the interface method that calls the implementation."""
    hints = typing.get_type_hints(declaration, include_extras=True)
    parameters = []
    for parameter in list(inspect.signature(declaration).parameters.values())[1:]:   # without self
        annotation = hints.get(parameter.name, parameter.annotation)
        if _authenticated(annotation):
            annotation = Annotated[dict, Depends(tokens.require_spec(MODULE, endpoint.method, endpoint.path))]
        parameters.append(parameter.replace(annotation=annotation))
    if not any(_authenticated(hints.get(p.name)) for p in parameters):
        raise TypeError(f"{declaration.__qualname__} has no `Claims` parameter: every endpoint needs a token")
    target = getattr(implementation, declaration.__name__)
    try:
        inspect.signature(target).bind(**{p.name: None for p in parameters})
    except TypeError as e:
        raise TypeError(f"{type(implementation).__name__}.{declaration.__name__} does not accept the "
                        f"parameters of the interface: {e}") from e

    def call(**kwargs: object) -> object:
        return target(**kwargs)

    call.__dict__["__signature__"] = inspect.Signature(parameters)   # what FastAPI reads for the parameters
    call.__name__ = declaration.__name__
    call.__qualname__ = f"{type(implementation).__name__}.{declaration.__name__}"
    call.__doc__ = declaration.__doc__
    call.__dict__["implementation"] = target   # lets tests and tools find the bound implementation
    return call


def _text(operation: dict[str, Json], key: str, *, required: bool = False) -> str | None:
    """A text field of a contract operation; a required one that is missing is a contract error."""
    value = operation.get(key)
    if isinstance(value, str):
        return value
    if required:
        raise LookupError(f"contract operation without {key}")
    return None


def _tags(operation: dict[str, Json]) -> list[str | Enum] | None:
    tags = operation.get("tags")
    return [str(tag) for tag in tags] if isinstance(tags, list) else None


def _success_status(operation: dict[str, Json]) -> int:
    """The 2xx status of a contract operation (`responses`)."""
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        raise LookupError("contract operation without responses")
    return next(int(code) for code in responses if code.startswith("2"))


def create_router(implementations: Iterable[RestApi], *, public: bool) -> APIRouter:
    """Router of the public (`openapi.yaml`) or private (`openapi-private.yaml`) API. Every interface of
    that API needs exactly one implementation; every contract operation needs exactly one endpoint."""
    interfaces = apis(public=public)
    assigned = _assign(implementations, interfaces)
    document = load_contract(public=public)
    contract = operations(document)
    problem = resolve_object(document["components"]["responses"]["Problem"], document)
    router = APIRouter(prefix=document["servers"][0]["url"], route_class=C2M2Route, dependencies=[Depends(_bearer)])
    routed: set[tuple[str, str]] = set()
    for api in interfaces:
        for name, endpoint in api.endpoints().items():
            key = (endpoint.method, endpoint.path)
            if key not in contract:
                raise LookupError(f"{api.__name__}.{name}: {endpoint.method} {endpoint.path} is not in the contract")
            if key in routed:
                raise LookupError(f"{api.__name__}.{name}: {endpoint.method} {endpoint.path} is declared twice")
            routed.add(key)
            operation = resolve_object(contract[key], document)
            # FastAPI derives the parameters from the interface signature; copying them would duplicate them.
            operation.pop("parameters", None)
            router.add_api_route(
                endpoint.path,
                _endpoint_function(getattr(api, name), assigned[api], endpoint),
                methods=[endpoint.method],
                status_code=_success_status(operation),
                response_model=None,
                operation_id=_text(operation, "operationId", required=True),
                summary=_text(operation, "summary"),
                description=_text(operation, "description"),
                tags=_tags(operation),
                # A default Problem keeps FastAPI from advertising its unused 422 response.
                responses={"default": problem},
                openapi_extra=operation,
            )
    unrouted = sorted(contract.keys() - routed)
    if unrouted:
        raise LookupError(f"contract operations without an endpoint interface: {unrouted}")
    return router
