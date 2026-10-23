-- ClaimSense — canonical schema.
-- Postgres 16+.
--
-- THREE SCHEMAS, ON PURPOSE. In the engagement these are three separate vendor
-- systems with three separate contracts, and an adjuster moves between them by
-- hand. Collapsing them into one namespace here would make the integration work
-- look easier than it is and would let a careless join paper over a boundary
-- that is real. Nothing below crosses a schema with a foreign key:
--
--   pas.*   policy administration — the system of record for cover
--   cms.*   claims management     — the system of record for the claim
--   dms.*   document store        — the files, and the text pulled out of them
--
-- Cross-system references are PLAIN COLUMNS (cms.claims.policy_id, no FK). That
-- is the honest shape: in the real estate there is no referential integrity
-- across vendors, and the agent has to tolerate a dangling reference. See
-- ADR-0003 in DECISIONS.md.
--
-- MONEY IS ALWAYS BIGINT CENTS. There is no NUMERIC and no float anywhere in
-- this file. Deductibles, limits and settlements are deterministic arithmetic;
-- storing them as cents is what makes that arithmetic exact.

DROP SCHEMA IF EXISTS cms CASCADE;
DROP SCHEMA IF EXISTS pas CASCADE;
DROP SCHEMA IF EXISTS dms CASCADE;

CREATE SCHEMA pas;
CREATE SCHEMA cms;
CREATE SCHEMA dms;

-- ===========================================================================
-- PAS — Policy Administration System
-- Read-only to ClaimSense. The agent never writes cover; it only reads it.
-- ===========================================================================

CREATE TABLE pas.insureds (
    insured_id    BIGINT PRIMARY KEY,
    full_name     TEXT        NOT NULL,
    email         TEXT        NOT NULL,
    date_of_birth DATE        NOT NULL,
    state         TEXT        NOT NULL,
    tenure_years  INT         NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pas.policies (
    policy_id       BIGINT PRIMARY KEY,
    policy_number   TEXT        NOT NULL UNIQUE,
    insured_id      BIGINT      NOT NULL REFERENCES pas.insureds(insured_id),
    product         TEXT        NOT NULL,   -- HO3 | HO4 | AUTO
    -- The two dates every coverage decision starts from. A loss outside
    -- [effective_date, expiration_date) is not covered, and that is arithmetic,
    -- not judgment — see determinism/eligibility.py.
    effective_date  DATE        NOT NULL,
    expiration_date DATE        NOT NULL,
    status          TEXT        NOT NULL,   -- active | lapsed | cancelled
    -- Set when status='lapsed'. A loss on or after this date has no cover even
    -- though it falls inside the policy term — the non-payment case.
    lapse_date      DATE,
    premium_cents   BIGINT      NOT NULL,
    payment_status  TEXT        NOT NULL DEFAULT 'current',  -- current | late | delinquent
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_policies_insured ON pas.policies(insured_id);
CREATE INDEX idx_policies_status ON pas.policies(status);

CREATE TABLE pas.coverages (
    coverage_id     BIGINT PRIMARY KEY,
    policy_id       BIGINT NOT NULL REFERENCES pas.policies(policy_id),
    coverage_code   TEXT   NOT NULL,   -- DWELL | PP | LIAB | ALE | COLL | COMP
    limit_cents     BIGINT NOT NULL,
    deductible_cents BIGINT NOT NULL,
    -- Percent the insurer pays after the deductible, 0-100. 100 for most
    -- first-party cover; lower where the policy shares the loss.
    coinsurance_pct INT    NOT NULL DEFAULT 100,
    UNIQUE (policy_id, coverage_code)
);
CREATE INDEX idx_coverages_policy ON pas.coverages(policy_id);

CREATE TABLE pas.endorsements (
    endorsement_id BIGINT PRIMARY KEY,
    policy_id      BIGINT NOT NULL REFERENCES pas.policies(policy_id),
    code           TEXT   NOT NULL,
    effective_date DATE   NOT NULL,
    summary        TEXT   NOT NULL
);
CREATE INDEX idx_endorsements_policy ON pas.endorsements(policy_id);

-- The policy corpus the coverage agent retrieves over.
--
-- clause_id is a HUMAN-MEANINGFUL STRING, not a serial: 'HO3-I-EXCL-3b' is what
-- a coverage opinion cites and what an adjuster looks up. The milestone requires
-- coverage output to cite the identifiers actually retrieved, so the id has to
-- survive the round trip from corpus -> retrieval -> model -> UI intact, and an
-- opaque integer would make a wrong citation impossible to spot by eye.
CREATE TABLE pas.policy_clauses (
    clause_id   TEXT PRIMARY KEY,
    product     TEXT NOT NULL,          -- HO3 | HO4 | AUTO | ALL
    section     TEXT NOT NULL,
    title       TEXT NOT NULL,
    clause_type TEXT NOT NULL,          -- grant | exclusion | condition | definition | limit
    body        TEXT NOT NULL,
    -- Perils this clause speaks to, for the deterministic pre-filter that runs
    -- before BM25. Empty means it applies regardless of peril.
    perils      TEXT[] NOT NULL DEFAULT '{}',
    -- The vocabulary CLAIMANTS use for what this clause governs. A policy form
    -- is legal register and a first notice of loss is written by someone whose
    -- house just flooded; they share almost no words, and BM25 scores on words.
    -- Without this the wear-and-tear exclusion ranked LAST of 25 on a claim
    -- that said the roof "has been leaking" and the ceiling was "sagging".
    keywords    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_clauses_product ON pas.policy_clauses(product);
CREATE INDEX idx_clauses_type ON pas.policy_clauses(clause_type);

-- ===========================================================================
-- CMS — Claims Management System
-- The only system ClaimSense writes to, and only after a human confirms.
-- ===========================================================================

CREATE TABLE cms.adjusters (
    adjuster_id    BIGINT PRIMARY KEY,
    full_name      TEXT        NOT NULL,
    email          TEXT        NOT NULL UNIQUE,
    -- A decision is only valid if the person confirming it holds a licence.
    -- Checked in code on every write-back; never inferred by a model.
    license_number TEXT,
    role           TEXT        NOT NULL,   -- adjuster | siu | supervisor
    -- What this seat may see. 'all' for supervisors; SIU sees referred claims.
    scope          TEXT        NOT NULL DEFAULT 'standard',  -- standard | siu | all
    active         BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cms.claims (
    claim_id            BIGINT PRIMARY KEY,
    claim_number        TEXT        NOT NULL UNIQUE,
    -- Cross-system references. NO foreign key: PAS is another vendor's
    -- database. A claim CAN point at a policy that does not resolve, and the
    -- pipeline has to report that rather than crash on it.
    policy_id           BIGINT      NOT NULL,
    insured_id          BIGINT      NOT NULL,
    peril               TEXT        NOT NULL,   -- fire | water | theft | wind | collision | liability
    date_of_loss        DATE        NOT NULL,
    reported_at         TIMESTAMPTZ NOT NULL,
    claimed_amount_cents BIGINT     NOT NULL,
    status              TEXT        NOT NULL DEFAULT 'intake',  -- intake | investigating | decided | closed
    assigned_adjuster_id BIGINT     REFERENCES cms.adjusters(adjuster_id),
    loss_state          TEXT        NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_claims_policy ON cms.claims(policy_id);
CREATE INDEX idx_claims_status ON cms.claims(status);
CREATE INDEX idx_claims_peril ON cms.claims(peril);

-- First Notice of Loss: the claimant's own account, in their words. This is the
-- primary thing the intake agent reads, and the primary place an adversarial
-- input arrives.
CREATE TABLE cms.fnol (
    fnol_id      BIGINT PRIMARY KEY,
    claim_id     BIGINT      NOT NULL REFERENCES cms.claims(claim_id),
    reported_by  TEXT        NOT NULL,   -- insured | agent | third_party
    channel      TEXT        NOT NULL,   -- phone | web | agent | app
    narrative    TEXT        NOT NULL,
    recorded_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_fnol_claim ON cms.fnol(claim_id);

CREATE TABLE cms.claim_notes (
    note_id    BIGINT PRIMARY KEY,
    claim_id   BIGINT      NOT NULL REFERENCES cms.claims(claim_id),
    author_id  BIGINT      REFERENCES cms.adjusters(adjuster_id),
    body       TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_notes_claim ON cms.claim_notes(claim_id);

-- Fraud signals are OBSERVATIONS, recorded by upstream systems. The model
-- interprets them; it does not invent them. Keeping them as rows is what lets
-- a risk assessment name the evidence it relied on.
CREATE TABLE cms.fraud_signals (
    signal_id      BIGINT PRIMARY KEY,
    claim_id       BIGINT NOT NULL REFERENCES cms.claims(claim_id),
    indicator_code TEXT   NOT NULL,   -- LATE_REPORT | RECENT_INCEPTION | PRIOR_CLAIMS | ...
    detail         TEXT   NOT NULL,
    -- Weight is fixed per indicator and lives in the data, not in a prompt: the
    -- SCORE is deterministic arithmetic, only its MEANING is judgment.
    weight         INT    NOT NULL
);
CREATE INDEX idx_signals_claim ON cms.fraud_signals(claim_id);

-- The recommendation, and then the human's disposition of it.
--
-- `source` is the milestone requirement made structural: a verdict the model
-- produced and a verdict a deterministic check substituted are different kinds
-- of output, and they must never be mistaken for one another. It is a column
-- here, a field on the typed output, and a badge in the console.
CREATE TABLE cms.decisions (
    decision_id          BIGINT PRIMARY KEY,
    claim_id             BIGINT      NOT NULL REFERENCES cms.claims(claim_id),
    outcome              TEXT        NOT NULL,   -- APPROVE | DENY | MORE_INFO | SIU_REFERRAL
    -- THREE values, not two. A decision an adjuster typed by hand is neither
    -- a model verdict nor a deterministic fallback, and collapsing it into
    -- either would make the before/after comparison meaningless: the whole
    -- question the engagement answers is what changed when the draft stopped
    -- being human-written.
    source               TEXT        NOT NULL,   -- model | deterministic_fallback | manual_adjuster
    rationale            TEXT        NOT NULL,
    cited_clause_ids     TEXT[]      NOT NULL DEFAULT '{}',
    settlement_cents     BIGINT,
    confidence           NUMERIC(4,3),
    -- Null until a licensed adjuster confirms. A row with a recommendation and
    -- no confirmation is exactly what the figure means by "first decision":
    -- produced by the system, not yet owned by a human.
    confirmed_by         BIGINT      REFERENCES cms.adjusters(adjuster_id),
    confirmed_at         TIMESTAMPTZ,
    -- Set when the adjuster disagreed. This is the single most valuable column
    -- in the schema: every override is a future eval case.
    override_outcome     TEXT,
    override_reason      TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_decisions_claim ON cms.decisions(claim_id);
CREATE INDEX idx_decisions_unconfirmed ON cms.decisions(claim_id) WHERE confirmed_at IS NULL;

-- ===========================================================================
-- DMS — Document Store
-- ===========================================================================

CREATE TABLE dms.documents (
    document_id    BIGINT PRIMARY KEY,
    claim_id       BIGINT      NOT NULL,   -- cross-system: no FK, see above
    doc_type       TEXT        NOT NULL,   -- police_report | photo | estimate | invoice | proof_of_loss | receipt
    filename       TEXT        NOT NULL,
    uploaded_at    TIMESTAMPTZ NOT NULL,
    page_count     INT         NOT NULL DEFAULT 1,
    -- What OCR pulled out. The model reads THIS, never a file handle.
    extracted_text TEXT        NOT NULL DEFAULT '',
    -- The adversarial surface. A document whose text carries an instruction
    -- aimed at the model is flagged here by upstream scanning, and the input
    -- guardrail drops it BEFORE it reaches model context. Flagged rather than
    -- deleted so the quarantine is visible and auditable.
    is_poisoned    BOOLEAN     NOT NULL DEFAULT FALSE
);
CREATE INDEX idx_documents_claim ON dms.documents(claim_id);
CREATE INDEX idx_documents_type ON dms.documents(doc_type);

-- The one DMS write: asking the claimant for a document that is missing. This
-- is what a MORE_INFO outcome produces, and it is idempotent — asking twice
-- because a pipeline retried must not send two letters.
CREATE TABLE dms.document_requests (
    request_id    BIGINT PRIMARY KEY,
    claim_id      BIGINT      NOT NULL,
    doc_type      TEXT        NOT NULL,
    reason        TEXT        NOT NULL,
    requested_by  BIGINT      NOT NULL,
    requested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    fulfilled_at  TIMESTAMPTZ
);
CREATE INDEX idx_docreq_claim ON dms.document_requests(claim_id);
