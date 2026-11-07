---
name: portal-spec-sources
description: Find anything in the specs of the Dataspace Management product (the new Tractus-X portal, OSP 2.0) - the backend module specs (portal-backend-spec - FRAMEWORK.md, README.md, openapi.yaml, open-points.md per module, flows.yaml) and the frontend architecture (portal-frontend-spec). Use for "which module does X", "what is the path / permission / scope of X", "which step or query does module Y provide and how is the Python function called", "which events exist", "what does section N of the C3-M1 README say", "which configuration variables", "which call hits this URL", "where is the spec", or to fetch or update the specs.
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

# Portal spec sources

The spec is the contract (AGENTS.md rule 3). Every path, method, field, permission, scope, error type, event and
configuration variable comes from it. This skill finds them fast and cites them, instead of answering from memory.

```bash
S=.agents/skills/portal-spec-sources/scripts/spec-src.py
$S where                      # which spec checkout is used, at which commit
$S sync                       # clone or fast-forward both specs into ~/.cache/dataspace-mgm/specs
$S modules                    # every module: base path, version, kind, operations, steps, queries
$S ops c3-m1                  # operations: method, path, operationId, x-permission, scope, tags, SSE
$S steps c3-m1                # steps with the interface.py function name (create-company -> create_company)
$S queries                    # queries (/internal/...) with the function name (operationId in snake_case)
$S events c4-m1               # event catalogue, FRAMEWORK 6
$S perm register_company      # operations that need a permission
$S route POST /api/c1-m2/applications   # which operation a URL hits, with permission and scope
$S sse                        # Server-Sent Events streams for the UI
$S section c1-m2 4            # README section 4 (configuration); 8 steps, 9 queries, 11 calls, 12 errors, 13 acceptance
$S section FRAMEWORK 4.3      # a framework section (4.3 scopes, 4.5 errors, 4.7 stand-ins, 5.2 onboarding, 7a test IDs)
$S open-points c3-m2          # provisional decisions and open questions of a module (no module: cross-module OP-xx)
$S grep "home OSP" --be       # search; --fe for the frontend spec only
```

## Where the specs are found

The scripts never guess a location silently; `where` prints it. First hit wins:

| Spec | Order |
|---|---|
| backend (`portal-backend-spec`) | `$SPEC_DIR`, `<repo>/spec` (the service convention: `git clone … spec`, not committed), `<repo>/../portal-backend-spec`, `~/.cache/dataspace-mgm/specs/portal-backend-spec` |
| frontend (`portal-frontend-spec`) | `$FRONTEND_SPEC_DIR`, `<repo>/../portal-frontend-spec`, `~/.cache/dataspace-mgm/specs/portal-frontend-spec` |

Upstream: https://github.com/tx-arena-events/portal-backend-spec and https://github.com/tx-arena-events/portal-frontend-spec
(until they move to Eclipse Tractus-X). In the service repository, update the local clone with
`git -C spec pull --ff-only` before a lookup that matters; the scaffold reads `spec/` at start-up.

## Reading order for a question about a module

1. `FRAMEWORK.md` sections 1 (architecture), 4 (conventions), 5 (flows), 6 (events), 7 (steps), 7a (test IDs).
2. The module `README.md`: 4 configuration, 6 rules and permissions, 7 operations, 8 steps, 9 queries, 10 events,
   11 calls to neighbours (with the built-in stand-in), 12 errors, 13 acceptance, 14 test data.
3. `openapi.yaml` for exact names; `open-points.md` for what is provisional.
4. Cross-module `open-points.md` (OP-xx) when two modules disagree.

## Rules for answers

- Cite as `C3-M1 README 7.4`, `FRAMEWORK 4.3`, `C1-M2 openapi.yaml createApplication`, plus the commit that `where` prints.
- A module identifier has three spellings: `C3-M1` (spec), `c3-m1` (URL path, `Problem`, `service_token`), `c3_m1`
  (folder, Python package). Use the right one for the place.
- If the spec does not say it, say so and point to the open point (or propose one), never fill the gap from memory.
- `C2-M5` (Keycloak) and `C5-M1` (EBW-Connector, standards) have no `/api/<module>` base path; `C1-M1`, `C2-M1`,
  `C2-M4` are dropped with OSP 2.0 and keep only a short README.

## Requirements

`python3` (3.10+) with PyYAML. Without PyYAML: `uv run --no-project --with pyyaml python3 <script> …`.
