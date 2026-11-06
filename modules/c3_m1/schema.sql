-- #################################################################################
-- #  Copyright (c) 2026 Contributors to the Eclipse Foundation
-- #
-- #  See the NOTICE file(s) distributed with this work for additional
-- #  information regarding copyright ownership.
-- #
-- #  This program and the accompanying materials are made available under the
-- #  terms of the Apache License, Version 2.0 which is available at
-- #  https://www.apache.org/licenses/LICENSE-2.0.
-- #
-- #  Unless required by applicable law or agreed to in writing, software
-- #  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
-- #  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
-- #  License for the specific language governing permissions and limitations
-- #  under the License.
-- #
-- #  AI Disclosure: This file was entirely AI-generated.
-- #  The AI-generated portions are made available under CC0-1.0 and not subject
-- #  to the project's license. The human contributor has reviewed and verified
-- #  that the code is correct.
-- #
-- #  SPDX-License-Identifier: Apache-2.0 AND CC0-1.0
-- #  Assisted-By: Hermes Agent (deepseek-v4.1-flash)
-- #################################################################################
-- C3-M1 Company Profile, own database `c3_m1` (README 4, 5). Field names, types, NOT NULLs,
-- enums and indexes are the ones of README 5; the comments name the section of every block.
-- Not executed by the tests: `modules/c3_m1/store.py` keeps the same shape in memory.

-- C3-M1 5 Table company
CREATE TABLE company (
    id                     uuid                     PRIMARY KEY,
    name                   text                     NOT NULL,
    short_name             text,
    street                 text                     NOT NULL,
    house_number           text,
    address_addition       text,
    postal_code            text,
    city                   text                     NOT NULL,
    region                 text,
    country_code           char(2)                  NOT NULL,
    status                 text                     NOT NULL,
    bpn                    text,
    bpn_assigned_at        timestamptz,
    core_data_source       text                     NOT NULL,
    core_data_verified_at  timestamptz,
    verification_ref       text,
    application_id         uuid,
    deactivation_reason    text,
    created_at             timestamptz              NOT NULL,
    changed_at             timestamptz              NOT NULL,
    activated_at           timestamptz,
    rejected_at            timestamptz,
    deactivated_at         timestamptz,
    reactivated_at         timestamptz,
    CONSTRAINT company_name_length      CHECK (char_length(name) BETWEEN 1 AND 160 AND name = btrim(name)),
    CONSTRAINT company_short_name_length CHECK (short_name IS NULL OR char_length(short_name) <= 100),
    CONSTRAINT company_street_length    CHECK (char_length(street) BETWEEN 1 AND 255),
    CONSTRAINT company_house_number_length CHECK (house_number IS NULL OR char_length(house_number) <= 50),
    CONSTRAINT company_address_addition_length CHECK (address_addition IS NULL OR char_length(address_addition) <= 255),
    CONSTRAINT company_postal_code_length CHECK (postal_code IS NULL OR char_length(postal_code) <= 12),
    CONSTRAINT company_city_length      CHECK (char_length(city) BETWEEN 1 AND 255),
    CONSTRAINT company_region_format    CHECK (region IS NULL OR region ~ '^[A-Z0-9]{1,3}$'),
    CONSTRAINT company_country_format   CHECK (country_code ~ '^[A-Z]{2}$'),
    CONSTRAINT company_status_enum      CHECK (status IN ('REQUESTED', 'ACTIVE', 'REJECTED', 'INACTIVE')),
    CONSTRAINT company_bpn_format       CHECK (bpn IS NULL OR bpn ~ '^BPNL[A-Z0-9]{12}$'),
    CONSTRAINT company_core_data_source_enum CHECK (core_data_source IN ('EBW', 'MANUAL')),
    CONSTRAINT company_deactivation_reason_enum
        CHECK (deactivation_reason IS NULL OR deactivation_reason IN ('MANUAL', 'TRANSFERRED')),
    -- C3-M1 5: the reason is filled only with status INACTIVE
    CONSTRAINT company_deactivation_reason_state
        CHECK (deactivation_reason IS NULL OR status = 'INACTIVE')
);

-- C3-M1 5: BPN unique among all companies with a status other than REJECTED (partial unique index)
CREATE UNIQUE INDEX company_bpn_unique ON company (bpn) WHERE status <> 'REJECTED';

-- C3-M1 5 Table company_identifier
CREATE TABLE company_identifier (
    company_id        uuid         NOT NULL REFERENCES company (id),
    type              text         NOT NULL,
    value             text         NOT NULL,
    value_normalized  text         NOT NULL,
    source            text         NOT NULL,
    created_at        timestamptz  NOT NULL,
    changed_at        timestamptz  NOT NULL,
    PRIMARY KEY (company_id, type),                    -- C3-M1 6.4: at most one per type
    CONSTRAINT company_identifier_type_enum
        CHECK (type IN ('EUID', 'EBWOID', 'VAT_ID', 'COMMERCIAL_REG_NUMBER', 'LEI_CODE', 'EORI')),
    CONSTRAINT company_identifier_source_enum CHECK (source IN ('BUSINESS_WALLET', 'DECLARED'))
);

-- C3-M1 5: index for the duplicate search on the normalised value (README 6.4, 9.3)
CREATE INDEX company_identifier_value_normalized ON company_identifier (type, value_normalized);

-- C3-M1 5 Table company_role_assignment
CREATE TABLE company_role_assignment (
    company_id     uuid         NOT NULL REFERENCES company (id),
    company_role   text         NOT NULL,
    status         text         NOT NULL,
    source_kind    text         NOT NULL,
    source_ref     text,
    activated_at   timestamptz,
    deactivated_at timestamptz,
    changed_at     timestamptz  NOT NULL,
    PRIMARY KEY (company_id, company_role),
    CONSTRAINT company_role_assignment_status_enum CHECK (status IN ('REQUESTED', 'ACTIVE', 'INACTIVE')),
    CONSTRAINT company_role_assignment_source_enum CHECK (source_kind IN ('APPLICATION', 'COMPANY', 'SEED')),
    CONSTRAINT company_role_assignment_source_ref_length
        CHECK (source_ref IS NULL OR char_length(source_ref) <= 100)
);

-- C3-M1 5 Table consent: one row per company and terms, with the latest state
CREATE TABLE consent (
    company_id        uuid         NOT NULL REFERENCES company (id),
    agreement_key     text         NOT NULL,
    agreement_version text,
    status            text         NOT NULL,
    source_kind       text         NOT NULL,
    source_ref        text,
    consented_by      text,
    consented_at      timestamptz,
    changed_at        timestamptz  NOT NULL,
    PRIMARY KEY (company_id, agreement_key),
    CONSTRAINT consent_status_enum CHECK (status IN ('ACTIVE', 'INACTIVE')),
    CONSTRAINT consent_source_kind_enum CHECK (source_kind IN ('APPLICATION', 'COMPANY')),
    CONSTRAINT consent_source_ref_length CHECK (source_ref IS NULL OR char_length(source_ref) <= 100),
    CONSTRAINT consent_consented_by_length CHECK (consented_by IS NULL OR char_length(consented_by) <= 200)
);

-- C3-M1 5 Table change_request
CREATE TABLE change_request (
    id               uuid         PRIMARY KEY,
    company_id       uuid         NOT NULL REFERENCES company (id),
    status           text         NOT NULL,
    changes          jsonb        NOT NULL DEFAULT '{}'::jsonb,
    comment          text,
    requested_by     text,
    decided_by       text,
    decision_reason  text,
    created_at       timestamptz  NOT NULL,
    closed_at        timestamptz,
    CONSTRAINT change_request_status_enum CHECK (status IN ('OPEN', 'APPROVED', 'DECLINED', 'WITHDRAWN')),
    CONSTRAINT change_request_comment_length CHECK (comment IS NULL OR char_length(comment) BETWEEN 1 AND 1000),
    CONSTRAINT change_request_decision_reason_length
        CHECK (decision_reason IS NULL OR char_length(decision_reason) BETWEEN 1 AND 1000),
    -- C3-M1 7.18: the justification is required with DECLINED
    CONSTRAINT change_request_declined_needs_reason
        CHECK (status <> 'DECLINED' OR decision_reason IS NOT NULL)
);

-- C3-M1 5: at most one change request with status OPEN per company (partial unique index)
CREATE UNIQUE INDEX change_request_open_per_company ON change_request (company_id) WHERE status = 'OPEN';

-- C3-M1 5 Table change_request_document
CREATE TABLE change_request_document (
    id                 uuid         PRIMARY KEY,
    change_request_id  uuid         NOT NULL REFERENCES change_request (id),
    file_name          text         NOT NULL,
    media_type         text         NOT NULL,
    size_bytes         integer      NOT NULL,
    sha256             text         NOT NULL,
    content            bytea        NOT NULL,
    created_at         timestamptz  NOT NULL,
    CONSTRAINT change_request_document_file_name_length CHECK (char_length(file_name) <= 200),
    CONSTRAINT change_request_document_media_type_enum
        CHECK (media_type IN ('application/pdf', 'image/png', 'image/jpeg'))
);

CREATE INDEX change_request_document_request ON change_request_document (change_request_id);

-- C3-M1 5 Table used_attestation: one row per used verification attestation (README 6.7, 7.3)
CREATE TABLE used_attestation (
    jti        text         PRIMARY KEY,
    company_id uuid         NOT NULL REFERENCES company (id),
    used_at    timestamptz  NOT NULL
);

-- C3-M1 5 Table audit_log (FRAMEWORK 4.3): no secrets, no names of people
CREATE TABLE audit_log (
    id          uuid         PRIMARY KEY,
    occurred_at timestamptz  NOT NULL,
    sub         text         NOT NULL DEFAULT '',
    company_id  uuid,
    operation   text         NOT NULL,
    object_id   text,
    details     jsonb        NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX audit_log_company ON audit_log (company_id, occurred_at);

-- C3-M1 5: in addition the table `outbox` of the base skeleton (events in the same transaction, 6.9)
