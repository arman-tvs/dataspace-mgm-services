#!/usr/bin/env bash
#################################################################################
#  Copyright (c) 2026 Catena-X Automotive Network e.V.
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
#
# Eclipse Dash license check exactly like .github/workflows/dependencies.yml (TRG 7.04), locally.
#
# Usage: dash-check.sh [--list-only] [--write]
#
#   (default)    build the dependency list like CI, run the Eclipse Dash License Tool, compare the result
#                with DEPENDENCIES and report restricted or rejected packages
#   --list-only  only build the list and compare its coordinates with DEPENDENCIES (no Java, no network
#                for the Dash APIs)
#   --write      replace DEPENDENCIES with the generated file (only when Dash ran)
#
# Service repository (uv.lock): the runtime dependencies from `uv export --frozen --no-dev`, as
# pypi/pypi/-/<name>/<version>. UI repository (package-lock.json): Dash reads the lock file itself.
# Exit code 1 when DEPENDENCIES is out of date or a package is restricted or rejected, as in CI.
set -euo pipefail

LIST_ONLY=false
WRITE=false
for a in "$@"; do
  case "$a" in
    --list-only) LIST_ONLY=true ;;
    --write) WRITE=true ;;
    -h|--help) sed -n '20,32p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $a" >&2; exit 2 ;;
  esac
done

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
WF=.github/workflows/dependencies.yml
DASH_VERSION=$(sed -n 's/^ *DASH_VERSION: *"\{0,1\}\([0-9.]*\)"\{0,1\}.*/\1/p' "$WF" 2>/dev/null | head -1 || true)
DASH_VERSION=${DASH_VERSION:-1.1.0}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

if [ -f uv.lock ]; then
  MODE=python
  command -v uv >/dev/null || { echo "uv is needed (https://docs.astral.sh/uv/)" >&2; exit 2; }
  # the same pipeline as the step "List the runtime dependencies" of the workflow
  uv export --frozen --no-dev --no-hashes --no-emit-project --format requirements-txt \
    | grep -E '^[A-Za-z0-9_.-]+==' \
    | sed -E 's/[[:space:]]*;.*$//' \
    | awk -F'==' '{ name=tolower($1); gsub(/[_.]/, "-", name); print "pypi/pypi/-/" name "/" $2 }' \
    | sort -u > "$WORK/PACKAGE"
  INPUT="$WORK/PACKAGE"
elif [ -f package-lock.json ]; then
  MODE=npm
  INPUT=package-lock.json
  # coordinates for --list-only: every installed package of the lock file, as Dash names them
  python3 - "$WORK/PACKAGE" <<'EOF'
import json, sys
lock = json.load(open("package-lock.json", encoding="utf-8"))
out = set()
for path, meta in (lock.get("packages") or {}).items():
    if not path or "node_modules/" not in path or meta.get("link") or not meta.get("version"):
        continue
    name = path.rsplit("node_modules/", 1)[1]
    scope, _, pkg = name.rpartition("/")
    out.add(f"npm/npmjs/{scope or '-'}/{pkg}/{meta['version']}")
open(sys.argv[1], "w").write("\n".join(sorted(out)) + "\n")
EOF
else
  echo "Neither uv.lock nor package-lock.json in $ROOT: nothing to check (CI skips too)."
  exit 0
fi

COUNT=$(wc -l < "$WORK/PACKAGE" | tr -d ' ')
echo "dash-check: $MODE, $COUNT package coordinate(s), Dash $DASH_VERSION"

if $LIST_ONLY; then
  : > "$WORK/known"
  if [ -f DEPENDENCIES ]; then
    { cut -d, -f1 DEPENDENCIES | sed 's/ *$//' | grep -v '^$' || true; } | sort -u > "$WORK/known"
  fi
  NEW=$(comm -23 "$WORK/PACKAGE" "$WORK/known" || true)
  GONE=$(comm -13 "$WORK/PACKAGE" "$WORK/known" || true)
  [ -n "$NEW" ] && { echo; echo "Not yet in DEPENDENCIES:"; echo "$NEW" | sed 's/^/  + /'; }
  [ -n "$GONE" ] && { echo; echo "In DEPENDENCIES but no longer used:"; echo "$GONE" | sed 's/^/  - /'; }
  if [ -z "$NEW" ] && [ -z "$GONE" ]; then
    echo "DEPENDENCIES lists exactly these coordinates."
    exit 0
  fi
  echo; echo "Run without --list-only to let Dash fill in licences and status, then --write."
  exit 1
fi

command -v java >/dev/null || { echo "Java 17+ is needed for the Dash tool (or use --list-only)." >&2; exit 2; }
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/eclipse-dash"
JAR="$CACHE/org.eclipse.dash.licenses-$DASH_VERSION.jar"
if [ ! -s "$JAR" ]; then
  mkdir -p "$CACHE"
  curl -sSL --fail --output "$JAR" "https://repo.eclipse.org/service/rest/v1/search/assets/download?repository=dash-maven2-releases&maven.groupId=org.eclipse.dash&maven.artifactId=org.eclipse.dash.licenses&maven.baseVersion=${DASH_VERSION}&maven.extension=jar"
fi
java -jar "$JAR" -project automotive.tractusx -timeout 300 -summary "$WORK/DEPENDENCIES.generated" "$INPUT" || true
sort -o "$WORK/DEPENDENCIES.generated" "$WORK/DEPENDENCIES.generated"

RC=0
if grep -E ', (restricted|rejected),' "$WORK/DEPENDENCIES.generated"; then
  echo "Restricted or rejected packages above: request an IP review (TRG 7.04), e.g. by running the workflow"
  echo "'Update DEPENDENCIES' (needs the secret DASH_GITLAB_API_TOKEN)."
  RC=1
fi
if diff -u <(sort DEPENDENCIES 2>/dev/null) "$WORK/DEPENDENCIES.generated"; then
  echo "DEPENDENCIES is up to date."
elif $WRITE; then
  cp "$WORK/DEPENDENCIES.generated" DEPENDENCIES
  echo "DEPENDENCIES replaced with the generated file; commit it."
else
  echo "DEPENDENCIES is out of date (CI fails the same way). Re-run with --write to replace it."
  RC=1
fi
exit $RC
