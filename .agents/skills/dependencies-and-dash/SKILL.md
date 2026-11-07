---
name: dependencies-and-dash
description: Run the Eclipse Dash license check of the Dataspace Management repositories exactly like the workflow .github/workflows/dependencies.yml, locally - the runtime dependencies from uv.lock (service) or package-lock.json (UI), the generated DEPENDENCIES file, restricted or rejected packages, and the IP review. Use for "I added a dependency", "Eclipse Dash IP Check fails", "DEPENDENCIES is out of date", "is this library allowed", "request an IP review", or before a PR that changes pyproject.toml, uv.lock, package.json or package-lock.json.
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

# Dependencies and Eclipse Dash

TRG 7.04: every third-party package must be listed in `DEPENDENCIES` and approved by the Eclipse Dash License Tool. CI
(`Eclipse Dash IP Check`) regenerates the file and fails when it differs or a package is `restricted` or `rejected`.
This script runs the same steps locally, so the PR does not fail on it.

```bash
D=.agents/skills/dependencies-and-dash/scripts/dash-check.sh
$D --list-only     # coordinates only: what is new or gone compared with DEPENDENCIES (no Java, no Dash APIs)
$D                 # Dash like CI: licences and status, restricted/rejected, diff with DEPENDENCIES
$D --write         # replace DEPENDENCIES with the generated file, then commit it
```

| Repository | Input (as in CI) | Coordinates |
|---|---|---|
| dataspace-mgm-service | `uv export --frozen --no-dev --no-hashes --no-emit-project` (runtime dependencies only) | `pypi/pypi/-/<name>/<version>` |
| dataspace-mgm-ui | `package-lock.json` read by Dash | `npm/npmjs/<scope or ->/<name>/<version>` |

The Dash version comes from `DASH_VERSION` in the workflow (default 1.1.0); the jar is cached in
`~/.cache/eclipse-dash`.

## When a package is restricted

1. `restricted` means "not yet reviewed", not "forbidden". Prefer a version that is already approved, if one is.
2. Otherwise the workflow `Update DEPENDENCIES` (`.github/workflows/dependencies-update.yml`, after every lock file
   change on main, daily, or run manually) requests the review with the secret `DASH_GITLAB_API_TOKEN` and opens or
   updates the pull request `chore/update-dependencies`; or a committer runs Dash with `-review -token …`. The review
   appears at https://gitlab.eclipse.org/eclipsefdn/emo-team/iplab/-/issues.
3. `rejected` means: remove the package.
4. Development tools (pytest, Vite, ESLint) are not in the runtime list of the service; the UI lock file lists all.

## Requirements

`git`, `bash`, `uv` (service) or `python3` (UI, for `--list-only`), Java 17+ and network access to
`repo.eclipse.org` and the Eclipse / ClearlyDefined APIs for a full run.
