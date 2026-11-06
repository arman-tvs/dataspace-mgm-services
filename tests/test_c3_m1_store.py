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
#  Assisted-By: Hermes Agent (deepseek-v4.1-flash)
#################################################################################
"""Store and validation of C3-M1 without HTTP: README 5 tables, the constraints the database
would carry, the field rules of 5, the identifier rules of 6.4 and the comparison of 6.3."""
import itertools
import json

import pytest

from modules.c3_m1 import store
from modules.c3_m1 import validation as v
from portal_common import settings

_ids = itertools.count(1)


@pytest.fixture(autouse=True)
def _empty_store():
    store.reset()
    yield
    store.reset()


@pytest.fixture
def make():
    """A company row in the shape of README 5 (id assigned here, the store validates it)."""
    def _make(**fields) -> dict:
        n = next(_ids)
        row = {"id": f"c00000{n:02d}-0000-4000-8000-{n:012d}", "name": f"Beispiel Firma {n}",
               "street": "Musterstraße 1", "city": "Stuttgart", "country_code": "DE",
               "status": "ACTIVE"}
        row.update(fields)
        return store.create_company(row)
    return _make


# ------------------------------------------------------------------------------- company (5)
def test_get_company_returns_a_copy(make):
    company = make()
    fetched = store.get_company(company["id"])
    fetched["name"] = "geändert"
    assert store.get_company(company["id"])["name"] == company["name"]
    assert store.get_company("unknown") is None


def test_create_company_fills_defaults_and_timestamps(make):
    company = store.create_company({"id": "c0000001-0000-4000-8000-000000000001", "name": "A",
                                    "street": "Weg 1", "city": "Stadt", "country_code": "DE"})
    assert company["status"] == "REQUESTED"
    assert company["core_data_source"] == "MANUAL"
    assert company["bpn"] is None
    assert company["created_at"] and company["changed_at"]
    assert set(company) == set(store.COMPANY_FIELDS)


def test_create_company_rejects_unknown_field(make):
    with pytest.raises(ValueError):
        make(payload="x")


def test_update_company_sets_changed_at_and_returns_none_for_unknown(make):
    company = make()
    changed = store.update_company(company["id"], short_name="Kurz")
    assert changed["short_name"] == "Kurz"
    assert changed["changed_at"] >= company["changed_at"]
    assert store.update_company("unknown", short_name="x") is None


def test_bpn_is_stored_in_upper_case(make):
    assert make(bpn="bpnl00000000aaaa")["bpn"] == "BPNL00000000AAAA"


def test_bpn_is_unique_among_companies_that_are_not_rejected(make):
    make(bpn="BPNL00000000AAAA")
    with pytest.raises(ValueError):
        make(bpn="BPNL00000000AAAA")


def test_bpn_of_a_rejected_company_frees_it(make):
    rejected = make(bpn="BPNL00000000AAAA", status="REJECTED")
    assert make(bpn="BPNL00000000AAAA")["bpn"] == "BPNL00000000AAAA"
    assert store.get_company(rejected["id"])["bpn"] == "BPNL00000000AAAA"


def test_reactivating_a_rejected_company_takes_a_free_bpn(make):
    rejected = make(bpn="BPNL00000000AAAA", status="REJECTED")
    other = make()
    assert store.update_company(rejected["id"], status="ACTIVE", bpn="BPNL00000000AAAA")
    with pytest.raises(ValueError):
        store.update_company(other["id"], bpn="BPNL00000000AAAA")


def test_rejecting_a_company_keeps_its_bpn(make):
    company = make(bpn="BPNL00000000AAAA")
    assert store.update_company(company["id"], status="REJECTED")["bpn"] == "BPNL00000000AAAA"


def test_status_enum_is_enforced(make):
    with pytest.raises(ValueError):
        make(status="DELETED")
    company = make()
    with pytest.raises(ValueError):
        store.update_company(company["id"], status="DELETED")


def test_core_data_source_enum_is_enforced(make):
    with pytest.raises(ValueError):
        make(core_data_source="MASTER_DATA")


def test_deactivation_reason_enum_and_state_are_enforced(make):
    with pytest.raises(ValueError):
        make(status="INACTIVE", deactivation_reason="NO_PSP")
    with pytest.raises(ValueError):
        make(status="ACTIVE", deactivation_reason="MANUAL")
    company = make()
    assert store.update_company(company["id"], status="INACTIVE",
                                deactivation_reason="MANUAL")["deactivation_reason"] == "MANUAL"
    with pytest.raises(ValueError):
        store.update_company(company["id"], status="ACTIVE")


def test_find_companies_filters(make):
    active = make(bpn="BPNL00000000AAAA", core_data_source="EBW")
    make(name="Andere Logistik GmbH", status="REQUESTED")
    make(status="REJECTED")
    assert [c["id"] for c in store.find_companies(status="REQUESTED")[0]] != []
    assert all(c["status"] == "REQUESTED" for c in store.find_companies(status=["REQUESTED"])[0])
    found, total = store.find_companies(name="logistik")
    assert total == 1 and found[0]["name"] == "Andere Logistik GmbH"
    assert [c["id"] for c in store.find_companies(bpn="bpnl00000000aaaa")[0]] == [active["id"]]
    assert all(c["bpn"] for c in store.find_companies(has_bpn=True)[0])
    assert all(not c["bpn"] for c in store.find_companies(has_bpn=False)[0])
    assert all(c["core_data_source"] == "EBW" for c in store.find_companies(core_data_source="EBW")[0])


def test_find_companies_company_role_matches_active_roles_only(make):
    company = make()
    other = make()
    store.add_role(company["id"], "ACTIVE_PARTICIPANT", status="ACTIVE")
    store.add_role(other["id"], "APP_PROVIDER", status="REQUESTED")
    found, total = store.find_companies(company_role="ACTIVE_PARTICIPANT")
    assert total == 1 and found[0]["id"] == company["id"]
    assert store.find_companies(company_role="APP_PROVIDER")[1] == 0


def test_find_companies_is_newest_first_and_paged(make):
    companies = [make() for _ in range(5)]
    items, total = store.find_companies(page=0, size=2)
    assert total == 5 and len(items) == 2
    assert items[0]["id"] == companies[-1]["id"]      # newest first (7.10)
    rest, _ = store.find_companies(page=2, size=2)
    assert len(rest) == 1


# --------------------------------------------------------------------------- identifiers (5, 6.4)
def test_set_identifiers_normalises_and_replaces(make):
    company = make()
    rows = store.set_identifiers(company["id"], [
        {"type": "VAT_ID", "value": "de 123.456.789", "source": "DECLARED"},
        {"type": "EUID", "value": "DEXX001T.HRB100001", "source": "BUSINESS_WALLET"},
    ])
    assert {row["type"] for row in rows} == {"VAT_ID", "EUID"}
    by_type = {row["type"]: row for row in store.list_identifiers(company["id"])}
    assert by_type["VAT_ID"]["value_normalized"] == "DE123456789"
    store.set_identifiers(company["id"], [{"type": "LEI_CODE", "value": "A" * 20}])
    assert [row["type"] for row in store.list_identifiers(company["id"])] == ["LEI_CODE"]


def test_set_identifiers_enforces_one_per_type(make):
    company = make()
    with pytest.raises(ValueError):
        store.set_identifiers(company["id"], [{"type": "VAT_ID", "value": "DE123456789"},
                                             {"type": "VAT_ID", "value": "DE987654321"}])


def test_set_identifiers_enforces_the_enums(make):
    company = make()
    with pytest.raises(ValueError):
        store.set_identifiers(company["id"], [{"type": "VIES", "value": "DE123456789"}])
    with pytest.raises(ValueError):
        store.set_identifiers(company["id"], [{"type": "VAT_ID", "value": "DE123456789",
                                              "source": "ATTESTATION"}])


def test_set_identifiers_needs_a_known_company():
    with pytest.raises(ValueError):
        store.set_identifiers("unknown", [{"type": "VAT_ID", "value": "DE123456789"}])


# --------------------------------------------------------------------------------- roles (6.5)
def test_roles_report_status_and_none(make):
    company = make()
    assert store.role_status(company["id"], "APP_PROVIDER") == "NONE"
    store.add_role(company["id"], "ACTIVE_PARTICIPANT", status="ACTIVE")
    store.add_role(company["id"], "APP_PROVIDER", status="REQUESTED", source_kind="APPLICATION",
                   source_ref="a0000001-0000-4000-8000-000000000001")
    assert store.list_roles(company["id"]) == {"ACTIVE_PARTICIPANT": "ACTIVE",
                                               "APP_PROVIDER": "REQUESTED"}
    store.remove_role(company["id"], "APP_PROVIDER")
    assert store.role_status(company["id"], "APP_PROVIDER") == "INACTIVE"
    assert store.get_role(company["id"], "APP_PROVIDER")["deactivated_at"]
    assert store.remove_role(company["id"], "SERVICE_PROVIDER") is None


def test_add_role_enforces_the_enums(make):
    company = make()
    with pytest.raises(ValueError):
        store.add_role(company["id"], "ACTIVE_PARTICIPANT", status="ADDED")
    with pytest.raises(ValueError):
        store.add_role(company["id"], "ACTIVE_PARTICIPANT", source_kind="FLOW")


# -------------------------------------------------------------------------------- consents (5)
def test_consents_are_keyed_by_company_and_key(make):
    company = make()
    store.set_consent(company["id"], "terms-active-participant", version="1.0",
                      source_kind="COMPANY", consented_by="sub")
    store.set_consent(company["id"], "terms-active-participant", version="1.0", status="INACTIVE")
    store.set_consent(company["id"], "security-regulations", version="1.0")
    consent = store.get_consent(company["id"], "terms-active-participant")
    assert consent["status"] == "INACTIVE" and consent["agreement_version"] == "1.0"
    assert len(store.list_consents(company["id"])) == 2
    assert store.get_consent(company["id"], "unknown") is None


# ------------------------------------------------------------------------- change requests (5, 7)
def test_at_most_one_open_change_request_per_company(make):
    company = make()
    first = store.create_change_request({"company_id": company["id"], "comment": "neu",
                                         "requested_by": "sub"})
    with pytest.raises(ValueError):
        store.create_change_request({"company_id": company["id"], "comment": "nochmal"})
    store.withdraw_change_request(first["id"])
    assert store.create_change_request({"company_id": company["id"], "comment": "neu"})
    assert store.get_change_request(first["id"])["status"] == "WITHDRAWN"


def test_a_closed_request_does_not_block_another_company(make):
    a, b = make(), make()
    store.create_change_request({"company_id": a["id"]})
    assert store.create_change_request({"company_id": b["id"]})["status"] == "OPEN"


def test_decide_requires_open_and_a_reason_for_declined(make):
    company = make()
    request = store.create_change_request({"company_id": company["id"], "comment": "c"})
    with pytest.raises(ValueError):
        store.decide_change_request(request["id"], "DECLINED", decided_by="sub")
    decided = store.decide_change_request(request["id"], "DECLINED", decided_by="sub",
                                          decision_reason="fehlt")
    assert decided["status"] == "DECLINED" and decided["decided_by"] == "sub"
    assert decided["closed_at"]
    with pytest.raises(ValueError):
        store.decide_change_request(request["id"], "APPROVED")


def test_decide_enforces_the_decision_status(make):
    company = make()
    request = store.create_change_request({"company_id": company["id"]})
    with pytest.raises(ValueError):
        store.decide_change_request(request["id"], "WITHDRAWN")
    assert store.decide_change_request("unknown", "APPROVED") is None


def test_list_change_requests_filters_and_order(make):
    company = make()
    first = store.create_change_request({"company_id": company["id"], "comment": "1"})
    store.withdraw_change_request(first["id"])
    second = store.create_change_request({"company_id": company["id"], "comment": "2",
                                         "changes": {"name": "Neu"}})
    items, total = store.list_change_requests(company_id=company["id"])
    assert total == 2 and [row["id"] for row in items] == [first["id"], second["id"]]
    newest, _ = store.list_change_requests(company_id=company["id"], newest_first=True)
    assert newest[0]["id"] == second["id"]
    assert store.list_change_requests(status="OPEN")[1] == 1
    assert items[1]["changes"] == {"name": "Neu"}


# ------------------------------------------------------------------------------ documents (5)
def test_documents_are_stored_with_checksum(make):
    company = make()
    request = store.create_change_request({"company_id": company["id"]})
    document = store.add_document(request["id"], file_name="auszug.pdf",
                                  media_type="application/pdf", content=b"%PDF-1.7 test")
    assert document["size_bytes"] == len(b"%PDF-1.7 test")
    assert len(document["sha256"]) == 64
    assert store.get_document(document["id"])["file_name"] == "auszug.pdf"
    assert len(store.list_documents(request["id"])) == 1
    with pytest.raises(ValueError):
        store.add_document(request["id"], file_name="x.txt", media_type="text/plain",
                           content=b"x")
    with pytest.raises(ValueError):
        store.add_document("unknown", file_name="x.pdf", media_type="application/pdf")


# ------------------------------------------------------------------------ used attestation (5)
def test_an_attestation_is_used_exactly_once(make):
    company = make()
    assert store.add_if_unused("jti-1", company["id"]) is True
    assert store.add_if_unused("jti-1", company["id"]) is False
    assert store.is_used("jti-1") and not store.is_used("jti-2")


# ---------------------------------------------------------------------------------- audit (5)
def test_audit_entry_is_written_and_readable(make):
    company = make()
    store.audit(company["id"], "5a1c0001-0000-4000-8000-000000000001", "patchCompany",
                details={"shortName": {"old": None, "new": "Kurz"}})
    store.audit(None, None, "createCompany")
    entries = store.list_audit(company["id"])
    assert len(entries) == 1
    assert entries[0]["operation"] == "patchCompany"
    assert entries[0]["details"]["shortName"]["new"] == "Kurz"
    assert store.list_audit()[1]["sub"] == ""       # steps have no sub
    assert store.list_audit("unknown") == []


# ----------------------------------------------------------------------------------- lock (6.9)
def test_lock_yields_the_company_id():
    with store.lock("company-1") as locked:
        assert locked == "company-1"


# ---------------------------------------------------------------------------------- reset
def test_reset_clears_every_table(make):
    company = make(bpn="BPNL00000000AAAA")
    store.set_identifiers(company["id"], [{"type": "VAT_ID", "value": "DE123456789"}])
    store.add_role(company["id"], "ACTIVE_PARTICIPANT")
    store.set_consent(company["id"], "terms-active-participant", version="1.0")
    request = store.create_change_request({"company_id": company["id"]})
    store.add_document(request["id"], file_name="a.pdf", media_type="application/pdf",
                       content=b"%PDF-1")
    store.add_if_unused("jti", company["id"])
    store.audit(company["id"], "sub", "op")

    store.reset()

    assert store.get_company(company["id"]) is None
    assert store.list_identifiers(company["id"]) == []
    assert store.list_roles(company["id"]) == {}
    assert store.list_consents(company["id"]) == []
    assert store.list_change_requests(company_id=company["id"]) == ([], 0)
    assert store.list_documents(request["id"]) == []
    assert not store.is_used("jti")
    assert store.list_audit() == []
    assert store.find_companies()[1] == 0


# ------------------------------------------------------------------------------ comparison (6.3)
def test_normalise_is_nfkc_trimmed_and_collapsed():
    assert v.normalise("  Beispiel \t Maschinenbau  GmbH ") == "Beispiel Maschinenbau GmbH"
    assert v.normalise("ＡＧ") == "AG"
    assert v.same_value("Beispiel  Maschinenbau GmbH", "beispiel maschinenbau gmbh")
    assert not v.same_value("Beispiel Maschinenbau GmbH", "Beispiel Maschinenbau AG")


def test_value_normalized_drops_spaces_and_punctuation():
    assert v.value_normalized("de 123.456/789-0") == "DE1234567890"
    assert v.value_normalized(" DEXX001T.HRB100001 ") == "DEXX001THRB100001"


# ------------------------------------------------------------------ field rules of section 5
def test_name_rules():
    base = {"street": "Weg 1", "city": "Stadt", "country_code": "DE"}
    assert v.validate_company({"name": "Beispiel GmbH", **base}) == []
    assert {"field": "name", "reason": "required"} in v.validate_company(base)
    assert {"field": "name", "reason": "required"} in v.validate_company({"name": " ", **base})
    assert {"field": "name", "reason": "whitespace"} in v.validate_company({"name": " A", **base})
    assert {"field": "name", "reason": "too-long"} in v.validate_company({"name": "x" * 161, **base})


def test_required_address_fields_and_lengths():
    errors = v.validate_company({"name": "A"})
    assert {(e["field"], e["reason"]) for e in errors} >= {("street", "required"),
                                                           ("city", "required"),
                                                           ("country_code", "required")}
    errors = v.validate_company({"short_name": "x" * 101, "house_number": "x" * 51,
                                 "address_addition": "x" * 256, "postal_code": "x" * 13})
    assert {(e["field"], e["reason"]) for e in errors} >= {
        ("short_name", "too-long"), ("house_number", "too-long"),
        ("address_addition", "too-long"), ("postal_code", "too-long")}


def test_region_rules():
    base = {"name": "A", "street": "Weg 1", "city": "Stadt", "country_code": "DE"}
    assert v.validate_company({"region": "BW", **base}) == []
    assert v.validate_company({"region": "B1", **base}) == []
    assert v.validate_company(base) == []
    assert {"field": "region", "reason": "format"} in v.validate_company({"region": "bw", **base})
    assert {"field": "region", "reason": "format"} in v.validate_company({"region": "BWX1", **base})


def test_country_code_rules():
    assert v.validate_country_code("DE") == []
    assert {"field": "country_code", "reason": "format"} in v.validate_country_code("de")
    assert {"field": "country_code", "reason": "format"} in v.validate_country_code("D1")
    assert {"field": "country_code", "reason": "unknown-country"} in v.validate_country_code("AT")
    assert {"field": "country_code", "reason": "required"} in v.validate_country_code(None)


def test_company_enums_and_bpn_format():
    base = {"name": "A", "street": "Weg 1", "city": "Stadt", "country_code": "DE"}
    assert {"field": "status", "reason": "unknown"} in v.validate_company({"status": "DELETED", **base})
    assert {"field": "core_data_source", "reason": "unknown"} in v.validate_company(
        {"core_data_source": "X", **base})
    assert {"field": "deactivation_reason", "reason": "unknown"} in v.validate_company(
        {"deactivation_reason": "NO_PSP", **base})
    assert v.validate_company({"bpn": "BPNL00000000AAAA", **base}) == []
    assert {"field": "bpn", "reason": "format"} in v.validate_company({"bpn": "DE123", **base})


def test_camel_case_and_nested_address_are_understood():
    errors = v.validate_company({"name": "A", "address": {"street": "Weg 1", "city": "Stadt",
                                                          "countryCode": "de"},
                                 "shortName": "x" * 101})
    assert errors == [{"field": "short_name", "reason": "too-long"},
                      {"field": "country_code", "reason": "format"}]


def test_partial_validation_checks_only_given_fields():
    assert v.validate_company({"short_name": "Kurz"}, partial=True) == []
    assert v.validate_company({"name": " A"}, partial=True) == [{"field": "name",
                                                                "reason": "whitespace"}]


# --------------------------------------------------------------------- identifier rules (6.4)
def test_a_company_needs_at_least_one_identifier():
    assert v.validate_identifiers([], "DE") == [{"field": "identifiers", "reason": "missing"}]
    assert v.validate_identifiers(None, "DE") == [{"field": "identifiers", "reason": "missing"}]


def test_identifier_type_enum_and_one_per_type():
    errors = v.validate_identifiers([{"type": "VIES", "value": "DE123456789"},
                                     {"type": "VAT_ID", "value": "DE123456789"},
                                     {"type": "VAT_ID", "value": "DE987654321"}], "DE")
    assert {"field": "identifiers[0].type", "reason": "unknown"} in errors
    assert {"field": "identifiers[2].type", "reason": "duplicate-type"} in errors


def test_de_vat_id_accepts_and_rejects():
    assert v.validate_identifiers([{"type": "VAT_ID", "value": "DE123456789"}], "DE") == []
    errors = v.validate_identifiers([{"type": "VAT_ID", "value": "DE12345678"}], "DE")
    assert errors == [{"field": "identifiers[0].value", "reason": "format"}]
    errors = v.validate_identifiers([{"type": "VAT_ID", "value": "ATU12345678"}], "DE")
    assert errors == [{"field": "identifiers[0].value", "reason": "format"}]


def test_euid_and_ebwoid_are_loose():
    assert v.validate_identifiers([{"type": "EUID", "value": "DEXX001T.HRB100001"}], "DE") == []
    assert v.validate_identifiers([{"type": "EBWOID", "value": "EBWOID-DE-0000000001"}], "DE") == []
    assert v.validate_identifiers([{"type": "EBWOID", "value": "A" * 200}], "DE") == []
    assert {"field": "identifiers[0].value", "reason": "format"} in v.validate_identifiers(
        [{"type": "EUID", "value": "DE1"}], "DE")
    # EBWOID: 1 to 255 characters without whitespace (6.4); the reference data has `^\S{1,200}$`
    assert {"field": "identifiers[0].value", "reason": "format"} in v.validate_identifiers(
        [{"type": "EBWOID", "value": "EBWOID DE 1"}], "DE")


def test_lei_and_eori_formats():
    assert v.validate_identifiers([{"type": "LEI_CODE", "value": "529900T8BM49AURSDO55"}], "DE") == []
    assert {"field": "identifiers[0].value", "reason": "format"} in v.validate_identifiers(
        [{"type": "LEI_CODE", "value": "kurz"}], "DE")
    assert v.validate_identifiers([{"type": "EORI", "value": "DE1234567"}], "DE") == []
    assert {"field": "identifiers[0].value", "reason": "format"} in v.validate_identifiers(
        [{"type": "EORI", "value": "1234567"}], "DE")


def test_a_business_wallet_source_can_be_refused():
    errors = v.validate_identifiers([{"type": "EUID", "value": "DEXX001T.HRB100001",
                                      "source": "BUSINESS_WALLET"}], "DE",
                                    allow_business_wallet=False)
    assert errors == [{"field": "identifiers[0].source", "reason": "business-wallet-source"}]


def test_patterns_fall_back_to_readme_6_4_without_reference_data(tmp_path, monkeypatch):
    settings_file = tmp_path / "installation.json"
    settings_file.write_text(json.dumps({"ospId": "22222222-2222-4222-8222-222222222222",
                                         "ospName": "OSP X",
                                         "ospCompanyId": "11111111-1111-4111-8111-111111111111"}))
    monkeypatch.setenv("SETTINGS_FILE", str(settings_file))
    settings.reset()

    assert v.validate_country_code("AT") == []                      # no country list: format only
    assert v.validate_identifiers([{"type": "EUID", "value": "ABCD"}], "DE") == []
    assert v.validate_identifiers([{"type": "EBWOID", "value": "x" * 255}], "DE") == []
    assert v.validate_identifiers([{"type": "VAT_ID", "value": "DE123456789"}], "DE") == []
    assert {"field": "identifiers[0].value", "reason": "format"} in v.validate_identifiers(
        [{"type": "VAT_ID", "value": "DE12345678"}], "DE")


# -------------------------------------------------------------------- change request (7.4)
def test_change_request_needs_a_change_a_comment_and_declared_identifiers():
    errors = v.validate_change_request({"comment": "bitte ändern"}, "DE")
    assert errors == [{"field": "changes", "reason": "missing"}]
    errors = v.validate_change_request({"name": "Neu"}, "DE")
    assert errors == [{"field": "comment", "reason": "required"}]
    errors = v.validate_change_request({"identifiers": [{"type": "VAT_ID", "value": "DE123456789",
                                                         "source": "BUSINESS_WALLET"}],
                                        "comment": "c"}, "DE")
    assert errors == [{"field": "identifiers[0].source", "reason": "business-wallet-source"}]
    assert v.validate_change_request({"identifiers": [{"type": "VAT_ID", "value": "DE123456789"}],
                                      "comment": "c"}, "DE") == []


def test_comment_and_reason_lengths():
    assert v.validate_comment("") == [{"field": "comment", "reason": "required"}]
    assert v.validate_comment("x" * 1001) == [{"field": "comment", "reason": "too-long"}]
    assert v.validate_comment("x" * 1000) == []
    assert v.validate_reason("x" * 501) == [{"field": "reason", "reason": "too-long"}]
    assert v.validate_reason("x" * 500) == []
    assert v.validate_decision_reason("x" * 1000) == []
    assert v.validate_decision_reason("x" * 1001) == [{"field": "reason", "reason": "too-long"}]


# ------------------------------------------------------------------------ documents (4, 5)
def test_media_type_comes_from_the_first_bytes():
    assert v.detect_media_type(b"%PDF-1.7") == "application/pdf"
    assert v.detect_media_type(b"\x89PNG\r\n\x1a\n") == "image/png"
    assert v.detect_media_type(b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert v.detect_media_type(b"PK\x03\x04") is None
    assert v.detect_media_type("text") is None


def test_a_stated_media_type_is_ignored():
    assert v.validate_document("auszug.pdf", b"%PDF-1.7") == []
    assert v.validate_document("auszug.pdf", b"nur Text",
                               stated_media_type="application/pdf") == [
        {"field": "document", "reason": "media-type"}]
    assert v.validate_document("auszug.png", b"\x89PNG\r\n", max_bytes=4) == [
        {"field": "document", "reason": "too-large"}]


def test_file_name_rules():
    assert v.validate_file_name("auszug.pdf") == []
    assert v.validate_file_name("x" * 201) == [{"field": "file_name", "reason": "too-long"}]
    assert {"field": "file_name", "reason": "path-parts"} in v.validate_file_name("tmp/auszug.pdf")
    assert {"field": "file_name", "reason": "path-parts"} in v.validate_file_name(r"tmp\auszug.pdf")
    assert v.validate_file_name("") == [{"field": "file_name", "reason": "required"}]
