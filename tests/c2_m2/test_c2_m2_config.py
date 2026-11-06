#################################################################################
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
#  Assisted-By: GitHub Copilot (claude-opus-5-5)
#################################################################################
"""C2-M2 configuration from the application.properties file named by C2_M2_CONFIG_FILE."""
from __future__ import annotations

import re

import pytest

from modules.c2_m2.c2_m2_impl.config import DEFAULT_CONFIG_FILE, Config
from modules.c2_m2.c2_m2_impl.config import properties


def test_parse_comments_separators_and_continuation():
    text = "# comment\n! also\n\nA=1\nB: two words\nC = x=y:z\nD=a,\\\n   b\nE\n"
    assert properties.parse(text) == {"A": "1", "B": "two words", "C": "x=y:z", "D": "a,b", "E": ""}


def test_placeholders_take_environment_then_default():
    env = {"SET": "from-env", "EMPTY": "", "INNER": "inner"}
    assert properties.expand("${SET:d}", env) == "from-env"
    assert properties.expand("${EMPTY:d}", env) == "d"
    assert properties.expand("${MISSING:}", env) == ""
    assert properties.expand("x-${MISSING:${INNER:y}}-z", env) == "x-inner-z"
    assert properties.expand("${MISSING:${NONE:deep}}", env) == "deep"
    with pytest.raises(ValueError):
        properties.expand("${MISSING}", env)
    with pytest.raises(ValueError):
        properties.expand("${OPEN:x", env)


def test_conversions():
    assert properties.as_list(" a, b ,,c ") == ("a", "b", "c") and properties.as_list("") == ()
    assert properties.as_int("168") == 168
    assert (properties.as_bool("TRUE"), properties.as_bool("false")) == (True, False)
    with pytest.raises(ValueError):
        properties.as_bool("yes")


def test_default_file_gives_the_readme_defaults(monkeypatch):
    for name in re.findall(r"\$\{([A-Z0-9_]+)", DEFAULT_CONFIG_FILE.read_text()):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("C2_M2_CONFIG_FILE", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@db/c2_m2")
    c = Config()
    assert c.config_file == DEFAULT_CONFIG_FILE
    assert c.from_properties("database.url") == "postgresql://u@db/c2_m2"
    assert c.from_properties("c2-m2.client.id") == "svc-c2-m2"
    assert c.from_properties("portal.core.client.id") == "portal-core"
    assert c.from_properties("invitation.ttl.hours") == "168"
    assert c.from_properties("company.portal.roles") == "Company Admin,IT Admin,Member"
    assert c.from_properties("instance.client.optional.scopes") == ""
    assert c.from_properties("invitation.name.check") == "true"


def test_config_file_variable_points_to_another_file(tmp_path, monkeypatch):
    file = tmp_path / "application.properties"
    file.write_text("database.url=postgresql://x@db/c2_m2\ninvitation.max.open=7\nlanguages=en\n")
    monkeypatch.setenv("C2_M2_CONFIG_FILE", str(file))
    monkeypatch.setenv("INVITATION_MAX_OPEN", "99")   # not referenced by the file, so ignored
    c = Config()
    assert c.config_file == file
    assert (c.from_properties("invitation.max.open"), c.from_properties("languages")) == ("7", "en")
    with pytest.raises(RuntimeError, match="company.admin.role missing in"):
        c.from_properties("company.admin.role")


def test_missing_config_file_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.setenv("C2_M2_CONFIG_FILE", str(tmp_path / "nope.properties"))
    with pytest.raises(RuntimeError, match="C2_M2_CONFIG_FILE"):
        Config()
