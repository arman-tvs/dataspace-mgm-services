---
name: portal-token-inspect
description: Explain a 401, 403 or 404 of a portal module from the person's token, offline - decode the Portal IAM access token (without verifying it), check it the way the shared token library does (C2-M5 7.6 - RS256, iss of the installation, exp, aud portal-core, typ Bearer), and predict the answer of a given call from its x-permission and x-permission-scope (company, osp, own). Use for "why 401", "why 403 although I am Company Admin", "why 404 for a company that exists", "token of OSP B against OSP A", "which permission does this call need", "decode this token".
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

# Portal token inspect

Every call of a person carries their token from the OSP's Portal IAM (Keycloak, C2-M5). The module answers 401 when the
token fails the validation, 403 when the permission is missing, and 404 when the object belongs to another company or
person (FRAMEWORK 4.3: the object stays invisible). Three different causes, three different fixes.

```bash
T=.agents/skills/portal-token-inspect/scripts/token-inspect.py
uv run python iam/test/get-token.py erika > /tmp/erika.jwt        # service repo: a test person's token
$T /tmp/erika.jwt                                                  # claims + C2-M5 7.6 checks
$T /tmp/erika.jwt --op "GET /api/c3-m1/companies/c0000002-0000-4000-8000-000000000002"
$T /tmp/erika.jwt --op "POST /api/c1-m3/review-cases/{id}/approve" --iss http://localhost:8080/auth/realms/CX-Central
pbpaste | $T -                                                     # from stdin; a Keycloak token response works too
```

## Reading the result

| Answer | Cause | Fix |
|---|---|---|
| 401 `unauthorized` | signature, `iss` (a token of another installation: OSP A realm `CX-Central`, OSP B `CX-Central-B` in the test IAM), `exp`, `aud` without `portal-core` (technical users and apps), `typ` | get a token from this installation's Portal IAM for the UI client |
| 403 `forbidden` | the permission (`x-permission`) is not in `resource_access.portal-core.roles` | the person's portal role does not bundle it (C2-M5 6.3); OSP staff roles are `OSP Reviewer`, `OSP Admin` |
| 404 `not-found` on scope `company` | `company_id` missing (account not bound yet) or another company | bind the account (onboarding, invitation); use the person's own company |
| 404 on scope `own` | the object belongs to another `sub` | each person sees only their own applications and notifications |

The script decodes only. It never verifies the signature and never calls Keycloak; the real check is
`portal_common.tokens`. Names are shown as "set". **Never paste a production token into an issue, PR or chat**: tokens
carry personal and company data (FRAMEWORK 4.6). Describe the claims instead.

## Requirements

python3 + PyYAML and the backend spec (for `--op`).
