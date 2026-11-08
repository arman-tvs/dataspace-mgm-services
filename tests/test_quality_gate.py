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
"""The quality gate (tools/quality, ADR-0003): layer rules, areas, the baseline ratchet and the hook mode."""
import io
import json
from pathlib import PurePosixPath

import pytest

from tools.quality import checks, gate, http_layer, layers
from tools.quality.checks import Finding


def violations(path: str, source: str) -> list[tuple[str, str]]:
    return [(v.check, v.message) for v in layers.check_file(PurePosixPath(path), source)]


# ---------------------------------------------------------------- layers (ADR-0003)
@pytest.mark.parametrize("path, layer", [
    ("router.py", "router"), ("interface.py", "interface"), ("services/steps.py", "service"),
    ("store_postgres.py", "store"), ("repository.py", "store"), ("gateways.py", "gateways"),
    ("adapters/keycloak.py", "adapter"), ("errors.py", "errors"), ("calls.py", None),
])
def test_layer_comes_from_the_file_name(path, layer):
    assert layers.layer_of(PurePosixPath(path).parts) == layer


def test_imports_point_down_only():
    assert violations("modules/c9_m9/service.py", "from . import store, gateways, errors\n") == []
    assert violations("modules/c9_m9/router.py", "from . import interface, schemas\n") == []
    assert violations("modules/c9_m9/router.py", "from .store import get\n") == [
        ("layers", "router imports store (store)")]
    assert violations("modules/c9_m9/interface.py", "from modules.c9_m9 import store\n") == [
        ("layers", "interface imports store (store)")]
    assert violations("modules/c9_m9/store.py", "from . import service\n") == [
        ("layers", "store imports service (service)")]


def test_relative_imports_inside_a_subpackage_resolve_to_its_layer():
    assert violations("modules/c9_m9/services/steps.py", "from . import accounts\nfrom .. import gateways\n") == []
    assert violations("modules/c9_m9/services/steps.py", "from .. import router\n") == [
        ("layers", "service imports router (router)")]


def test_http_models_stay_at_the_edge():
    assert violations("modules/c9_m9/service.py", "from pydantic import BaseModel\n") == [
        ("layers", "service imports pydantic: HTTP models stay in router/schemas")]
    assert violations("modules/c9_m9/schemas.py", "from pydantic import BaseModel\n") == []


def test_neighbours_only_in_gateways():
    source = "from portal_common import neighbours\n"
    assert violations("modules/c9_m9/gateways.py", source) == []
    assert violations("modules/c9_m9/service.py", source) == [
        ("neighbours", "portal_common.neighbours outside gateways.py")]
    assert violations("modules/c9_m9/calls.py", "from portal_common.neighbours import query\n") == [
        ("neighbours", "portal_common.neighbours outside gateways.py")]


def test_problems_are_built_only_in_errors():
    source = "raise Problem('c9-m9', 409, 'invalid-state', retryable=False)\n"
    assert violations("modules/c9_m9/errors.py", source) == []
    assert violations("modules/c9_m9/service.py", source) == [("problems", "Problem(...) outside errors.py")]
    assert violations("portal_common/problems.py", source) == []       # only modules are checked


def test_another_modules_interface_is_not_a_layer_of_this_module():
    assert violations("modules/c9_m9/gateways.py", "from modules.c1_m2.interface import get_application\n") == []


# ---------------------------------------------------------------- areas and the ratchet
@pytest.mark.parametrize("path, area", [
    ("modules/c3_m1/interface.py", "modules/c3_m1"), ("portal_common/tokens.py", "portal_common"),
    ("tests/test_x.py", "tests"), ("demo.py", "root"), ("ebw/connector/app.py", None),
    ("spec/x.py", None), ("modules/c3_m1/OPEN-QUESTIONS.md", None),
])
def test_area_of_a_file(path, area):
    assert checks.area_of(PurePosixPath(path)) == area


def test_a_count_above_the_baseline_fails_and_one_below_is_reported():
    now = {"modules/c9_m9": {"ruff": 3, "mypy": 1}, "modules/c8_m8": {"ruff": 1}}
    base = {"modules/c9_m9": {"ruff": 2, "mypy": 4}}
    worse, better = gate.compare(["modules/c9_m9", "modules/c8_m8"], now, base)
    assert worse == [("modules/c9_m9", "ruff", 2, 3), ("modules/c8_m8", "ruff", 0, 1)]   # a new area starts at 0
    assert better == ["modules/c9_m9 mypy: 4 -> 1"]


def test_update_baseline_only_lowers(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "BASELINE", tmp_path / "baseline.json")
    gate.save_baseline({"modules/c9_m9": {"ruff": 5, "mypy": 2}})
    found = [Finding("modules/c9_m9", "ruff", "x.py:1", "E1")] * 3
    found += [Finding("modules/c9_m9", "mypy", "x.py:1", "e")] * 4
    monkeypatch.setattr(checks, "collect", lambda areas: found)
    assert gate.run(["modules/c9_m9"], set(), update=True, hook=False) == 0
    assert gate.load_baseline() == {"modules/c9_m9": {"mypy": 2, "ruff": 3}}    # ruff lowered, mypy not raised


def test_hook_mode_exits_2_with_the_findings_on_stderr(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate, "BASELINE", tmp_path / "baseline.json")
    gate.save_baseline({})
    found = [Finding("modules/c3_m2", "problems", "modules/c3_m2/service.py:7", "Problem(...) outside errors.py")]
    monkeypatch.setattr(checks, "collect", lambda areas: found)
    edited = checks.ROOT / "modules" / "c3_m2" / "service.py"
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"tool_input": {"file_path": str(edited)}})))
    assert gate.main(["--hook"]) == 2
    err = capsys.readouterr().err
    assert "modules/c3_m2 - problems: 1 findings, baseline allows 0" in err
    assert "modules/c3_m2/service.py:7: Problem(...) outside errors.py" in err


def test_hook_ignores_files_outside_the_checked_areas(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"tool_input": {"file_path": "/tmp/notes.md"}})))
    assert gate.main(["--hook"]) == 0


def test_the_repository_passes_its_own_gate():
    """The committed baseline matches the code: every pull request starts green and can only stay so."""
    assert gate.main([]) == 0


# ---------------------------------------------------------------- HTTP layer (FastAPI, ADR-0003)
def http_findings(source: str) -> list[tuple[str, str]]:
    return [(f.check, f.message) for f in http_layer.check_router(PurePosixPath("modules/c9_m9/router.py"), source)]


def test_a_route_without_operation_id_response_model_and_typed_body_is_flagged():
    source = ("@router.post('/steps/x')\n"
              "def x(body: dict = Body(...)) -> dict:\n"
              "    return {}\n")
    assert http_findings(source) == [
        ("http-body", "x: body `body` is a dict, not a schemas.py model"),
        ("http-route", "x: no operation_id (the spec's operationId)"),
        ("http-route", "x: no response model")]


def test_a_route_with_model_body_operation_id_and_precise_return_is_fine():
    assert http_findings("@router.post('/steps/x', operation_id='stepX')\n"
                         "def x(body: StepX) -> StepReply:\n    return {}\n") == []
    assert http_findings("@router.get('/x', operation_id='getX', response_model=X)\n"
                         "def x() -> dict:\n    return {}\n") == []
    assert http_findings("@router.delete('/x', operation_id='deleteX', status_code=204)\n"
                         "def x() -> None:\n    return None\n") == []
    assert http_findings("@router.get('/x', operation_id='getX')\n"
                         "def x() -> dict[str, Any]:\n    return {}\n") == [("http-route", "x: no response model")]


def test_the_contract_of_c3_m2_matches_its_spec_and_c3_m1_shows_the_gaps():
    """C3-M2 is built with schemas.py and operation ids; C3-M1 (develop) takes dict bodies without operation ids."""
    assert http_layer.check_contract("c3-m2") == []
    gaps = [f.message for f in http_layer.check_contract("c3-m1")]
    assert any("PATCH /companies/{companyId}: operationId" in m and "'updateCompany'" in m for m in gaps)
    assert any(m.startswith("PATCH /companies/{companyId}: request body untyped") for m in gaps)
