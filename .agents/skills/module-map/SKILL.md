---
name: module-map
description: Show the state of every module folder of the Dataspace Management Service against its spec, statically - which modules are still stand-ins, which a team replaced, which steps and queries a folder answers itself or leaves to the stand-in fallback, routes that are not in openapi.yaml, imports that break the call convention, configuration variables the README does not name, missing tests or OPEN-QUESTIONS.md. Use for "which modules are done", "what is left in C3-M1", "does my module follow the call convention", "why does Process Orchestration get DONE from a stand-in", or as the first step of a module review.
---

<!--
 Copyright (c) 2026 Catena-X Automotive Network e.V.
 Copyright (c) 2026 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This program and the accompanying materials are made available under the
 terms of the Apache License, Version 2.0 which is available at
 https://www.apache.org/licenses/LICENSE-2.0.

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 License for the specific language governing permissions and limitations
 under the License.

 AI Disclosure: This file was entirely AI-generated.
 The AI-generated portions are made available under CC0-1.0 and not subject
 to the project's license. The human contributor has reviewed and verified
 that the code is correct.

 SPDX-License-Identifier: Apache-2.0 AND CC0-1.0
 Assisted-By: Claude Code (claude-opus-5-5)
-->

# Module map

The installation is a modular monolith (FRAMEWORK 1): one folder per module under `modules/<id>/`, every module of the
spec mounted from the start as a stand-in, and a team replaces exactly one folder (README "How a team replaces its
module"). This skill shows, without importing or running anything, how far each folder is.

```bash
M=.agents/skills/module-map/scripts/module-map.py
$M                 # one row per module: kind, steps/queries answered by own code, routes in spec, tests, findings
$M c3-m1           # details: each step and query and who answers it, each route against openapi.yaml, findings
$M c3_m1 --strict  # exit 1 on a blocker or high finding of a team module (pre-push hook, CI)
```

## Kinds

| Kind | Meaning | How the script knows |
|---|---|---|
| `stand-in` | the scaffold's stand-in; steps answer `DONE` with the stand-in results of C12-M1 11.3, other operations 501 | `STANDIN = True` in `router.py` |
| `provided` | provided by the organisers (C12-M1 Process Orchestration) | `PROVIDED = True` |
| `team` | a team's implementation | neither flag |
| `no folder` | the spec-driven fallback mounts the module | no `modules/<id>/` |

`Answered by: stand-in fallback` means `interface.py` does not define the function and
`__getattr__ = standin.missing_interface(MODULE)` fills it in: Process Orchestration still gets `DONE`, with stand-in
data. That is the most common reason why a flow "works" but carries wrong values.

## Findings and the rule behind each

| Finding | Rule |
|---|---|
| import of `modules.<other>.<anything but interface>` | AGENTS.md call convention 1 |
| step function with more or fewer than one argument | call convention 3 (`def create_company(input: dict) -> dict`) |
| step or query missing and no stand-in fallback | README module structure 8 |
| route not in `openapi.yaml` | AGENTS.md rule 3 (do not invent names) |
| environment variable not named in README section 4 | AGENTS.md rule 6 |
| reading `C3_M1_URL` & co. directly | AGENTS.md rule 6 (`portal_common.neighbours` resolves addresses) |
| no `reset()` in a team router | README "How a team replaces its module" 2 |
| no `tests/test_<id>_*.py`, no `OPEN-QUESTIONS.md` | AGENTS.md definition of done 1 and 4 |

The script is static: it cannot see behaviour. For the behaviour review use the scaffold's own `review-module` skill,
and for the real proof run `uv run pytest -q` and `uv run python demo.py` (definition of done).

## Requirements

The scaffold in this checkout (`modules/`, `portal_common/`), the backend spec (see `portal-spec-sources`), python3 +
PyYAML. On a checkout without the scaffold the script says so and exits 2.
