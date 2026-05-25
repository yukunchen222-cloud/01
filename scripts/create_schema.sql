-- ============ 门店 ============
CREATE TABLE IF NOT EXISTS stores (
    store_id     TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL DEFAULT 'org_default',
    name         TEXT NOT NULL,
    address      TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_stores_org ON stores(org_id);

-- ============ 用户 ============
CREATE TABLE IF NOT EXISTS users (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL DEFAULT 'org_default',
    username     TEXT UNIQUE,
    phone        TEXT,
    name         TEXT,
    role         TEXT,                 -- owner / manager / accountant
    password_hash TEXT,
    store_ids    JSONB DEFAULT '[]',
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    last_login   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_users_org ON users(org_id);

-- ============ 商品库 ============
CREATE TABLE IF NOT EXISTS products (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL DEFAULT 'org_default',
    code         TEXT,
    name         TEXT NOT NULL,
    category     TEXT,
    cost_price   NUMERIC(10,2) DEFAULT 0,
    sale_price   NUMERIC(10,2) DEFAULT 0,
    stock        INTEGER DEFAULT 0,
    sku          TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_products_org ON products(org_id);

-- ============ 交易记录（核心表） ============
CREATE TABLE IF NOT EXISTS records (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL DEFAULT 'org_default',
    store_id        TEXT NOT NULL,
    store_name      TEXT,
    type            TEXT NOT NULL,        -- revenue / purchase / expense / return / stocktake
    category        TEXT,
    items           JSONB DEFAULT '[]',
    total_amount    NUMERIC(12,2) DEFAULT 0,
    payment_method  TEXT,
    confidence      REAL DEFAULT 1.0,
    status          TEXT DEFAULT 'approved',  -- pending / approved / rejected
    operator        TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_records_org_store ON records(org_id, store_id);
CREATE INDEX IF NOT EXISTS idx_records_org_type ON records(org_id, type);
CREATE INDEX IF NOT EXISTS idx_records_status   ON records(status);
CREATE INDEX IF NOT EXISTS idx_records_created  ON records(created_at DESC);

-- ============ AI 原始记录（审计/调优用） ============
CREATE TABLE IF NOT EXISTS ai_raw_records (
    id              BIGSERIAL PRIMARY KEY,
    raw_type        TEXT NOT NULL,        -- asr / ocr / nlu
    raw_url         TEXT,                 -- OSS 上图片/录音 URL
    ai_response     JSONB,
    user_confirmed  JSONB,
    confidence      REAL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ai_raw_type    ON ai_raw_records(raw_type);
CREATE INDEX IF NOT EXISTS idx_ai_raw_created ON ai_raw_records(created_at DESC);

-- ============ 审计日志 ============
CREATE TABLE IF NOT EXISTS audit_logs (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT,
    action      TEXT NOT NULL,
    target_table TEXT,
    target_id   TEXT,
    old_value   JSONB,
    new_value   JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
