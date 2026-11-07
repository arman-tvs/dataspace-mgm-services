---
name: merge-guard
description: Check a team branch of the Dataspace Management Service before its pull request to eclipse-tractusx/dataspace-mgm-service - paths outside the team's module folder, the module against its spec, license headers on new files, commit authors and the Assisted-by trailer, Conventional Commits, secrets in added lines, DEPENDENCIES when the lock file changes, a committed spec/ clone - and optionally run the definition of done (pytest, demo.py). Use for "is my branch ready to merge", "review this PR before I open it", "why did the merge window reject us", "write the PR description", or before approving a hackathon PR.
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

# Merge guard

Green module tests are not enough: the module must work with the other modules on the first merge (AGENTS.md). Merges
break on changes outside the team's folder, field names, own error formats and secrets. This skill checks a branch the
way a Tractus-X committer reads it, before the merge window.

```bash
G=.agents/skills/merge-guard/scripts/merge-guard.py
$G                                  # against origin/main (upstream/main if that remote exists), module inferred
$G origin/main --module c3_m1       # name the team module explicitly
$G --run                            # also: pytest, demo.py and the quality gate (definition of done)
$G --strict                         # exit 1 on a blocker or high finding
```

The fork workflow: each team pushes to `team/<n>` of its own fork (`<fork-owner>/dataspace-mgm-services`) and opens
one PR to `main` of `eclipse-tractusx/dataspace-mgm-services` in the merge window at 14:45. Fetch the target first
(`git fetch origin` or `git fetch upstream`).

## What it checks

| Check | Severity | Rule |
|---|---|---|
| files outside `modules/<id>/` and `tests/test_<id>_*.py` | blocker (shared parts) / high | AGENTS.md rules 1-2 |
| several module folders in one team branch | high | AGENTS.md rule 1 |
| everything `module-map <id>` finds (call convention, routes, imports, config names, tests) | as there | AGENTS.md |
| `STANDIN = True` still set in a changed team module | high | AGENTS.md "The module folder" |
| added line that looks like a private key, client secret, API key, JWT, password, GitHub token (test-only values excluded) | blocker | FRAMEWORK 4.6, AGENTS.md rule 9 |
| `pyproject.toml` / `uv.lock` changed without `DEPENDENCIES` | high | TRG 7.04 |
| `spec/` committed | blocker | AGENTS.md "How to run" |
| new code file without `Copyright` + `SPDX-License-Identifier` | medium | TRG 7.02 |
| AI named as co-author instead of an `Assisted-by:` trailer | medium | AGENTS.md "Commits" |
| commit subjects that are not Conventional Commits | low | TRG 1.03 (the PR title must be one) |
| GitHub noreply author address | low | the ECA must cover the `Author` email |

The ECA check itself runs on the PR (Eclipse bot); the script cannot see the Eclipse account.

## After the scan

1. Fix every blocker and high, or explain it in the PR. A change in a shared part (`portal_common/`, `scaffold/`,
   `tools/`, `iam/`, `ebw/`, `testdata/`, `config/`) belongs in an issue, not in a team PR (AGENTS.md rule 2).
2. Run the definition of done (`--run`), or at least `uv run pytest -q && uv run python demo.py` and
   `uv run python tools/quality/gate.py` (ADR-0003; no new findings against `tools/quality/baseline.json`).
3. Write the PR description with `.github/PULL_REQUEST_TEMPLATE.md` (WHAT / WHY / FURTHER NOTES / CHECKLIST), list the
   open points of `modules/<id>/OPEN-QUESTIONS.md`, and paste the findings table you did not fix with the reason.
4. When the Captain posts it, wrap it in `docs/developers/dataspace-captain/comment-template.md`.
