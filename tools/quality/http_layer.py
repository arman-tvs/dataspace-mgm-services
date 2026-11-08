#################################################################################
#  Copyright (c) 2026 Technovative Solutions
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
#  Assisted-By: Claude Code (claude-opus-5-5)
#################################################################################
"""The HTTP layer of a module (ADR-0003 "HTTP layer (FastAPI)").

- `http-body`: a route takes its JSON body as `dict` (`body: dict = Body(...)`) instead of a Pydantic model of
  `schemas.py`; FastAPI then checks nothing and Swagger shows an empty object.
- `http-route`: a route without `operation_id=` (FastAPI invents one) or without a response model
  (`response_model=`, or a precise return annotation: not a bare `dict`/`Response`, no `Any`/`object` inside);
  `status_code=204` needs none.
- `contract`: the OpenAPI that FastAPI generates for the module's router, compared with the module's `openapi.yaml`
  in `spec/`: the same `operationId`, a typed request body with at least the spec's required fields, a typed
  response. Routes missing altogether are `module-map` findings and are not counted again here.
"""
from __future__ import annotations

import ast
import importlib
from dataclasses import dataclass
from pathlib import PurePosixPath

from portal_common import spec
from portal_common.spec import ModuleSpec, Operation

METHODS = {"get", "post", "put", "patch", "delete"}
UNTYPED_RETURNS = {"dict", "Response", "JSONResponse", "None"}


@dataclass(frozen=True, slots=True)
class HttpFinding:
    check: str      # http-body | http-route | contract
    line: int       # 0 for contract findings (generated, no line)
    message: str


# ---------------------------------------------------------------- static checks of router.py
def _route(decorator: ast.expr) -> ast.Call | None:
    """`@router.post(...)` -> the call; anything else -> None."""
    is_route = (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr in METHODS)
    return decorator if is_route and isinstance(decorator, ast.Call) else None


def _keywords(call: ast.Call) -> dict[str, ast.expr]:
    return {k.arg: k.value for k in call.keywords if k.arg}


def _untyped_body(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Parameters declared as `dict` with a `Body(...)` default or `Annotated[dict, Body(...)]`."""
    names = []
    params = fn.args.args + fn.args.kwonlyargs
    positional = [None] * (len(fn.args.args) - len(fn.args.defaults)) + list(fn.args.defaults)
    defaults = positional + list(fn.args.kw_defaults)
    for param, default in zip(params, defaults, strict=False):
        annotation = ast.unparse(param.annotation) if param.annotation else ""
        is_body = isinstance(default, ast.Call) and ast.unparse(default.func).endswith("Body")
        annotated_body = annotation.startswith("Annotated[dict") and "Body" in annotation
        if (annotation.startswith("dict") and is_body) or annotated_body:
            names.append(param.arg)
    return names


def _response_typed(fn: ast.FunctionDef | ast.AsyncFunctionDef, options: dict[str, ast.expr]) -> bool:
    if "response_model" in options or "response_class" in options:
        return True
    status = options.get("status_code")
    if isinstance(status, ast.Constant) and status.value == 204:
        return True
    returns = ast.unparse(fn.returns) if fn.returns else ""
    vague = returns in UNTYPED_RETURNS or "Any" in returns or "object" in returns   # `dict`, `dict[str, Any]`
    return bool(returns) and not vague


def check_router(path: PurePosixPath, source: str) -> list[HttpFinding]:
    """Findings of `modules/<id>/router.py` (and of routers in its subpackages)."""
    out: list[HttpFinding] = []
    for fn in ast.walk(ast.parse(source)):
        if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in fn.decorator_list:
            call = _route(decorator)
            if call is None:
                continue
            options = _keywords(call)
            out += [HttpFinding("http-body", fn.lineno, f"{fn.name}: body `{name}` is a dict, not a schemas.py model")
                    for name in _untyped_body(fn)]
            if "operation_id" not in options:
                out.append(HttpFinding("http-route", fn.lineno, f"{fn.name}: no operation_id (the spec's operationId)"))
            if not _response_typed(fn, options):
                out.append(HttpFinding("http-route", fn.lineno, f"{fn.name}: no response model"))
    return out


# ---------------------------------------------------------------- contract against spec/<Module>/openapi.yaml
def _resolve(document: dict, schema: dict | None) -> dict:
    """A generated schema with `$ref`, `allOf` and `anyOf: [X, null]` resolved to one object schema."""
    if not schema:
        return {}
    if "$ref" in schema:
        return _resolve(document, document["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]])
    for key in ("allOf", "anyOf"):
        if key in schema:
            parts = [_resolve(document, part) for part in schema[key] if part.get("type") != "null"]
            merged: dict = {"properties": {}, "required": []}
            for part in parts:
                merged["properties"].update(part.get("properties", {}))
                merged["required"] += part.get("required", [])
            return merged if merged["properties"] else (parts[0] if parts else {})
    return schema


def _json(content_holder: dict | None) -> dict | None:
    content = (content_holder or {}).get("content") or {}
    return (content.get("application/json") or {}).get("schema")


def _ok_schema(operation: dict) -> dict | None:
    for status, answer in (operation.get("responses") or {}).items():
        if str(status).startswith("2") and (schema := _json(answer)) is not None:
            return schema
    return None


def _generated(module_id: str) -> dict:
    from fastapi import FastAPI
    router = importlib.import_module(f"modules.{module_id.replace('-', '_')}.router")
    app = FastAPI()
    app.include_router(router.router)
    openapi: dict = app.openapi()
    return openapi


def _compare(spec_module: ModuleSpec, operation: Operation, generated_op: dict, generated: dict) -> list[str]:
    label = f"{operation.method} {operation.path}"
    out = []
    if operation.operation_id and generated_op.get("operationId") != operation.operation_id:
        out.append(f"{label}: operationId {generated_op.get('operationId')!r}, spec {operation.operation_id!r}")
    wanted = spec_module.resolve(operation.request_schema)
    if wanted.get("properties"):
        body = _resolve(generated, _json(generated_op.get("requestBody")))
        missing = sorted(set(wanted.get("required", [])) - set(body.get("required", [])))
        if not body.get("properties"):
            out.append(f"{label}: request body untyped, spec has {len(wanted['properties'])} fields")
        elif missing:
            out.append(f"{label}: request body does not require {', '.join(missing)}")
    spec_op = spec_module.document["paths"][operation.path][operation.method.lower()]
    answer = spec_module.resolve(_ok_schema(spec_op))
    if (answer.get("properties") or answer.get("items")) and not _resolve(generated, _ok_schema(generated_op)):
        out.append(f"{label}: response untyped")
    return out


def check_contract(module_id: str) -> list[HttpFinding]:
    """Differences between the generated OpenAPI of a team module and its spec (needs `spec/`)."""
    try:
        spec_module = spec.module(module_id)
    except (KeyError, FileNotFoundError, ValueError):
        return []
    generated = _generated(module_id)
    routes = {(method, path.removeprefix(spec_module.base_path)): op
              for path, item in generated.get("paths", {}).items() for method, op in item.items()}
    out = []
    for operation in spec_module.operations:
        found = [op for (method, path), op in routes.items() if operation.matches(method, path)]
        if found:
            out += [HttpFinding("contract", 0, text) for text in _compare(spec_module, operation, found[0], generated)]
    return out
