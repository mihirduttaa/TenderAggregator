CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS tenders (
    id                  SERIAL PRIMARY KEY,
    tender_id           VARCHAR(200) UNIQUE,
    title               TEXT NOT NULL,
    reference_no        VARCHAR(200),
    department          TEXT,
    work_category       VARCHAR(100),        -- AI-tagged later: Civil, Electrical, IT
    estimated_value     NUMERIC(15, 2),
    emd_amount          NUMERIC(15, 2),      -- from detail page later
    document_url        TEXT,               -- from detail page later
    published_date      TIMESTAMP,
    submission_deadline TIMESTAMP,
    opening_date        TIMESTAMP,
    tender_url          TEXT,
    status              VARCHAR(50) DEFAULT 'active',
    source_portal       VARCHAR(100) DEFAULT 'mptenders',
    raw_data            JSONB,
    embedding           vector(1536),       -- OpenAI text-embedding-3-small
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_category   ON tenders(work_category);
CREATE INDEX IF NOT EXISTS idx_deadline   ON tenders(submission_deadline);
CREATE INDEX IF NOT EXISTS idx_department ON tenders(department);
CREATE INDEX IF NOT EXISTS idx_status     ON tenders(status);
CREATE INDEX IF NOT EXISTS idx_embedding  ON tenders USING ivfflat (embedding vector_cosine_ops);

ALTER TABLE tenders
    ADD COLUMN IF NOT EXISTS tender_type          VARCHAR(100),
    ADD COLUMN IF NOT EXISTS form_of_contract     VARCHAR(100),
    ADD COLUMN IF NOT EXISTS tender_category      VARCHAR(100),
    ADD COLUMN IF NOT EXISTS product_category     VARCHAR(200),
    ADD COLUMN IF NOT EXISTS sub_category         VARCHAR(200),
    ADD COLUMN IF NOT EXISTS work_description     TEXT,
    ADD COLUMN IF NOT EXISTS location             VARCHAR(200),
    ADD COLUMN IF NOT EXISTS pincode              VARCHAR(20),
    ADD COLUMN IF NOT EXISTS period_of_work       VARCHAR(100),
    ADD COLUMN IF NOT EXISTS bid_validity_days    VARCHAR(50),
    ADD COLUMN IF NOT EXISTS tender_fee           NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS bid_submission_start TIMESTAMP,
    ADD COLUMN IF NOT EXISTS bid_submission_end   TIMESTAMP,
    ADD COLUMN IF NOT EXISTS doc_download_start   TIMESTAMP,
    ADD COLUMN IF NOT EXISTS doc_download_end     TIMESTAMP,
    ADD COLUMN IF NOT EXISTS nit_documents        JSONB,
    ADD COLUMN IF NOT EXISTS work_documents       JSONB,
    ADD COLUMN IF NOT EXISTS inviting_authority   JSONB,
    ADD COLUMN IF NOT EXISTS embedding           vector(1536);