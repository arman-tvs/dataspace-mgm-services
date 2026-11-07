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

# Dataspace Captain skills

Agent skills for building the Eclipse Tractus-X Dataspace Management product. Each skill is a folder with a `SKILL.md`
(the procedure, loaded on demand from `.agents/skills/` by GitHub Copilot, OpenAI Codex, OpenCode, Cursor and Gemini CLI,
and by Claude Code through the link `.claude/skills`) and a `scripts/` folder with
portable, tested scripts (`python3` 3.10+ with PyYAML, `bash`; macOS and Linux). The
[Dataspace Captain agent](../agents/dataspace-captain/instructions.md) routes matching tasks to them.

User documentation: [how to use the Captain](../../docs/developers/dataspace-captain/README.md).

Scripts run from anywhere inside the repository and read the specs that `portal-spec-sources` finds (`spec/`,
`SPEC_DIR`, a sibling checkout, or the cache filled by `spec-src.py sync`). They are read-only on the repository; only
`dash-check.sh --write` replaces `DEPENDENCIES`, and `merge-guard.py --run` runs the repository's own tests.

| Skill | Use it for | Script |
|---|---|---|
| [portal-spec-sources](portal-spec-sources/SKILL.md) | Modules, operations, permissions and scopes, steps and queries with their Python names, events, README sections, open points; fetch and update the specs | `spec-src.py` |
| [flow-trace](flow-trace/SKILL.md) | Process Orchestration flows: what runs next, what a step waits for, input sources, consistency of `flows.yaml` | `flow-trace.py` |
| [module-map](module-map/SKILL.md) | Which modules are stand-ins or team code, what each folder answers itself, call-convention findings | `module-map.py` |
| [merge-guard](merge-guard/SKILL.md) | A team branch before its PR: allowed paths, the module against its spec, headers, commits, secrets, definition of done | `merge-guard.py` |
| [contract-seam](contract-seam/SKILL.md) | UI against backend: base paths, casing, errors, BFF, vendored specs, calls in the UI code | `seam-check.py` |
| [portal-token-inspect](portal-token-inspect/SKILL.md) | 401 / 403 / 404 explained from a person's token and the operation's permission and scope | `token-inspect.py` |
| [dependencies-and-dash](dependencies-and-dash/SKILL.md) | Eclipse Dash like CI; `DEPENDENCIES`; IP reviews | `dash-check.sh` |

## How the scripts were tested

Against the hackathon scaffold (then in the former fork `tx-arena-events/dataspace-mgm-service`, branch
`feature/hackathon-scaffold` @ `f7a6b84`) and the specs `portal-backend-spec` @ `515b709` and `portal-frontend-spec` @ `e45a06b`:

- `spec-src.py`: 18 modules, 45 steps and 75 events read from the spec; `route` resolves literal segments before
  parameters (`GET /api/c3-m1/companies/{companyId}` → `getCompany`, `view_company`, scope `company`).
- `flow-trace.py check`: 25 flows, 77 steps, 3 lookups match the specs and the event catalogue; `completesOn` entries
  with `set` (wallet access) are handled.
- `module-map.py`: all 13 module folders recognised (12 stand-ins, C12-M1 provided); on a fixture team module it
  reports an import of `modules.c1_m2.router`, a step with two arguments, a route outside `openapi.yaml`, an own
  environment variable, a direct `C1_M2_URL` read, missing tests and `OPEN-QUESTIONS.md`, and exits 1 with `--strict`.
- `merge-guard.py` on the scaffold against `main` (maintainer change: shared parts as info, 24 non-conventional
  subjects) and on a fixture team branch (a change in `portal_common/`, a client secret, an AI co-author trailer:
  3 blocker, 3 high).
- `seam-check.py`: 19 calls of the frontend spec are not in the backend spec (with the matching backend operation,
  e.g. `POST /api/registration/applications` → `POST /api/c1-m2/applications`), camelCase vs snake_case, 400 vs 422;
  on a fixture UI checkout it finds a changed vendored spec and calls the backend does not have.
- `token-inspect.py` with fabricated tokens: 404 for another company (scope `company`), 403 for a missing
  `review_application`, 401 for the issuer of the other installation.
- `dash-check.sh` reproduces the workflow's 23 runtime coordinates from `uv.lock` and runs Dash 1.1.0: the scaffold's
  `DEPENDENCIES` still lists development tools and container images, and 10 runtime packages are `restricted`.

## Ideas for further skills

- **bff-contract**: an OpenAPI for the server part of the UI (`/me`, `/config`, `/auth/*`, the SSE relay, the
  EBW-Connector client), checked against C2-M5, C5-M1 6.8 and frontend architecture 05, once someone owns the BFF.
- **local-osp**: start OSP A, OSP B and the CSP stand-in (`demo.py --serve`) with Keycloak, then drive one scenario
  and map each failed check to the module that owns it.
- **chart-change**: `helm lint`, `helm template` per values file and the chart test of `charts/dataspace-mgm`, like the
  Helm workflow.
