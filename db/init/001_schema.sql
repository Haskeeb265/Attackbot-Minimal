CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


CREATE TABLE bounty_master (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    handle          TEXT NOT NULL UNIQUE,
    scope_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);


CREATE TABLE bounty_detail (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    master_id       UUID NOT NULL REFERENCES bounty_master(id) ON DELETE CASCADE,
    scope_type      TEXT NOT NULL,
    scope_identifier TEXT NOT NULL,
    max_severity    TEXT,
    scope_instructions    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (master_id, scope_type, scope_identifier)
);


CREATE TABLE program_weaknesses (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    master_id       UUID NOT NULL REFERENCES bounty_master(id) ON DELETE CASCADE,
    weakness_id     TEXT NOT NULL,
    weakness_name   TEXT,
    weakness_description    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (master_id, weakness_id)
);


CREATE TABLE bounty_exclusion (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    master_id       UUID NOT NULL REFERENCES bounty_master(id) ON DELETE CASCADE,
    exclusion_category        TEXT NOT NULL,
    exclusion_details         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_bounty_exclusion_master_id ON bounty_exclusion(master_id);