CREATE TABLE bounty_master (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    handle         TEXT NOT NULL UNIQUE,
    scope_count    INTEGER NOT NULL DEFAULT 0,
    max_severity   TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active      BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE bounty_detail (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bounty_master_id   UUID NOT NULL REFERENCES bounty_master(id) ON DELETE CASCADE,
    asset_type         TEXT NOT NULL,
    asset_identifier   TEXT NOT NULL,
    instructions       TEXT,
    is_exclusion       BOOLEAN NOT NULL DEFAULT false,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active          BOOLEAN NOT NULL DEFAULT true,

    UNIQUE (bounty_master_id, asset_type, asset_identifier, is_exclusion)
);

CREATE INDEX idx_bounty_detail_master ON bounty_detail(bounty_master_id);