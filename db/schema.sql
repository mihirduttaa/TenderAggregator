CREATE TABLE tenders (
    id                  SERIAL PRIMARY KEY,
    tender_id           VARCHAR(100) UNIQUE,        -- Portal's own ID
    title               TEXT NOT NULL,
    department          TEXT,
    organisation        TEXT,
    district            TEXT,
    category            TEXT,                       -- Civil, Electrical, IT etc (AI-tagged later)
    estimated_value     NUMERIC(15, 2),
    emd_amount          NUMERIC(15, 2),             -- Earnest Money Deposit
    document_url        TEXT,
    published_date      DATE,
    submission_deadline TIMESTAMP,
    opening_date        TIMESTAMP,
    status              VARCHAR(50),                -- Active, Closed, Awarded
    source_portal       VARCHAR(100),               -- mptenders, cppp, gem
    raw_data            JSONB,                      -- Store full raw response for safety
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tenders_category ON tenders(category);
CREATE INDEX idx_tenders_district ON tenders(district);
CREATE INDEX idx_tenders_deadline ON tenders(submission_deadline);
CREATE INDEX idx_tenders_department ON tenders(department);