-- ClaimSense — the integration layer's own tables.
--
-- Applied after schema.sql. Deliberately a FOURTH schema: these are not part of
-- any client system, they belong to the integration ClaimSense puts in front of
-- all three. Keeping them out of cms/pas/dms means a reader can tell at a glance
-- which tables are the client's and which are ours.

DROP SCHEMA IF EXISTS platform CASCADE;
CREATE SCHEMA platform;

-- API credentials. Keys are stored as sha256 HASHES and never in the clear —
-- `make keys` prints the plaintext once and the database never sees it.
--
-- `system` scopes a key to ONE client system. A CMS key cannot read PAS. That
-- is deliberate: the three integration points have three contracts and three
-- credentials, so a compromise of one does not hand over the other two.
CREATE TABLE platform.api_keys (
    key_id      BIGSERIAL PRIMARY KEY,
    key_hash    TEXT        NOT NULL UNIQUE,
    system      TEXT        NOT NULL,   -- cms | pas | dms
    -- The adjuster seat this key acts as. Access control resolves to a PERSON,
    -- not to a service account: a write-back has to name the licensed human it
    -- was made on behalf of.
    adjuster_id BIGINT      NOT NULL,
    label       TEXT        NOT NULL,
    revoked     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_api_keys_system ON platform.api_keys(system) WHERE NOT revoked;

-- Every request, allowed or denied. A denial is as much a record as an approval
-- — "who tried to read what and was stopped" is the question an audit asks.
CREATE TABLE platform.audit_log (
    audit_id      BIGSERIAL PRIMARY KEY,
    adjuster_id   BIGINT,
    system        TEXT        NOT NULL,
    action        TEXT        NOT NULL,
    resource_type TEXT,
    resource_id   TEXT,
    decision      TEXT        NOT NULL,   -- allow | deny
    reason        TEXT,
    detail        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_created ON platform.audit_log(created_at DESC);
CREATE INDEX idx_audit_resource ON platform.audit_log(resource_type, resource_id);

-- Idempotency for every write.
--
-- A duplicated claim decision is a duplicated payment, so this is a correctness
-- requirement rather than a nicety. The key is scoped to (adjuster, system,
-- key) and stores the response that was actually returned, so a replay gets the
-- ORIGINAL record back rather than a fresh one.
--
-- request_fingerprint catches the dangerous case: the same Idempotency-Key sent
-- with a DIFFERENT body. That is a client bug, and returning the first response
-- would silently discard the second intent — so it is a 409 instead.
CREATE TABLE platform.idempotency_keys (
    idem_id              BIGSERIAL PRIMARY KEY,
    idem_key             TEXT        NOT NULL,
    system               TEXT        NOT NULL,
    adjuster_id          BIGINT      NOT NULL,
    request_fingerprint  TEXT        NOT NULL,
    resource_type        TEXT        NOT NULL,
    resource_id          TEXT        NOT NULL,
    response_body        JSONB       NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (adjuster_id, system, idem_key)
);

-- Pipeline runs, for the console's trace view and for measuring the success
-- criteria. One row per claim the agent worked.
CREATE TABLE platform.agent_runs (
    run_id            BIGSERIAL PRIMARY KEY,
    trace_id          TEXT        NOT NULL,
    claim_id          BIGINT      NOT NULL,
    brain             TEXT        NOT NULL,   -- mock | llm
    outcome           TEXT,
    source            TEXT,                   -- model | deterministic_fallback
    -- Latency is one of the four quantified success criteria, so it is measured
    -- and stored rather than inferred from logs after the fact.
    duration_ms       INT         NOT NULL,
    guardrails_fired  TEXT[]      NOT NULL DEFAULT '{}',
    cited_clause_ids  TEXT[]      NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_runs_claim ON platform.agent_runs(claim_id);
CREATE INDEX idx_runs_created ON platform.agent_runs(created_at DESC);
