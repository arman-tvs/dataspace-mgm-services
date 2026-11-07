---
name: contract-seam
description: Check the seam between the Dataspace Management UI and the Dataspace Management Service - what the frontend expects (portal-frontend-spec, the vendored specs/<module>/openapi.yaml copies, the calls in the UI code) against what the backend spec defines (paths under /api/<module>, camelCase JSON, 400 Problem Details, SSE streams, permissions). Use for "will the UI work against the backend", "why does the UI get 404 or 400", "which path does the registration UI call", "is our vendored spec stale", "snake_case or camelCase", "who provides /me and /config", or before a merge window that touches both repositories.
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

# Contract seam

The two repositories are built by different people from two specs. The backend spec (FRAMEWORK 4) and the frontend
architecture (portal-frontend-spec) were written before the code and still differ on several points. Each difference is
a guaranteed bug on the first integration day. This skill makes the differences visible from either repository.

```bash
C=.agents/skills/contract-seam/scripts/seam-check.py
$C summary                       # every check that can run here, with a verdict list
$C casing                        # JSON field names of the backend schemas against the frontend's snake_case rule
$C errors                        # 400 Problem Details (backend) against "422 with error keys" (frontend)
$C assumptions                   # every call sketched in the frontend spec, checked against the backend paths
$C vendored --ui ../dataspace-mgm-ui   # the UI's specs/<module>/openapi.yaml copies against the backend spec
$C ui-calls --ui ../dataspace-mgm-ui   # client.GET/POST/... and '/api/...' in the UI code against the backend spec
```

`vendored` and `ui-calls` need the UI checkout: the UI repository itself, `../dataspace-mgm-ui`, or `--ui <path>`.
They exit 1 when the UI calls or copies something the backend spec does not have.

## The known seams (as of the specs of 4 Nov 2026; re-run the script, it reads the current text)

| Seam | Backend spec | Frontend spec | Resolution to propose |
|---|---|---|---|
| Base paths | `/api/<module id>`: `/api/c1-m2/applications`, `/api/c12-m1/processes/{processId}` (FRAMEWORK 4.1) | `/api/registration/...`, `/api/processes/...`, `/api/ebw/...` (assumptions, 14) | the core package adapters use the vendored spec's paths; only the adapters change (14 says so) |
| JSON casing | camelCase (FRAMEWORK 4.1) | `snake_case` DTOs (01.7) | DTO types follow the vendored spec (camelCase); mappers and MSW mocks follow |
| Validation errors | 400 Problem Details, `type` `urn:<module>:problem:<name>`, never 422 (FRAMEWORK 4.5, AGENTS.md) | 422 with error keys (14) | map `type` to the i18n key in the adapter |
| Session | the modules take a person's token in `Authorization: Bearer`; SSE only with the header (C12-M1 7.6) | BFF with an HttpOnly cookie, `/me`, `/config`, `/auth/*`, CSRF (05) | the BFF (server part of the UI) is not specified on the backend side: agree who builds it and its OpenAPI |
| Wallet step | the BFF is an OIDC client of the EBW-Connector and gets `ebw_attestation` in the token response (FRAMEWORK 5.2 step 2, C5-M1 6.8) | `POST /api/ebw/presentation-requests` (14) | follow C5-M1: authorization code + PKCE + `private_key_jwt` in the BFF |
| Process steps | the UI follows C12-M1 process state (`process-changed`); step keys come from flows.yaml (`create-company`, `open-review`, …) | `current_step` = `connect-wallets`, `company-data`, `submit`, `review` (14) | UI wizard steps are UI state before submission; after `ApplicationSubmitted` the UI renders C12-M1 state |

When a seam is decided, the decision belongs in the spec that changes (an issue or PR on portal-backend-spec or
portal-frontend-spec), not in a workaround in code.

## Requirements

python3 + PyYAML, the backend spec, and for the frontend checks the frontend spec (`spec-src.py sync` fetches both).
