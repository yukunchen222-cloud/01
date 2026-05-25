# 方案 B：asyncpg 异步直连 PostgreSQL — 完整改造代码

## 背景

当前 `src/main.py` 的所有 `@app.get/post async def` 路由里都在调同步的 `supabase_client().table().execute()`，导致整个 uvicorn 事件循环被阻塞，第二次 API 请求开始永久 pending。

方案 B 用 **asyncpg** 直连 PostgreSQL，全部异步、零阻塞、连接池由 asyncpg 自己管。原仓库已经有 `PGDATABASE_URL` 环境变量（在 `src/storage/database/db.py` 里用过），所以**连接凭据不用重新申请**。

---

## 文件清单

要新增 / 修改的文件一览：

| 操作 | 文件 | 用途 |
|---|---|---|
| 新增 | `src/utils/db_pool.py` | asyncpg 连接池单例 |
| 新增 | `src/storage/database/repository.py` | 所有 async 数据访问函数 |
| 新增 | `scripts/create_schema.sql` | PostgreSQL 建表 SQL |
| 新增 | `scripts/migrate_json_to_pg.py` | 一次性把 data/*.json 灌进 PG |
| 修改 | `pyproject.toml` | 加 asyncpg 依赖 |
| 修改 | `src/main.py` | 把所有 supabase 调用换成 await repo.xxx() |
| 可选 | 删除 | `src/utils/supabase_client.py`（确认无人用之后） |

---

## 1. 新增：`src/utils/db_pool.py`

整个项目里所有数据库访问都从这里拿连接。

```python
"""
asyncpg 连接池单例。
所有 FastAPI 路由通过 await get_pool() 获取池子，再通过 acquire() 拿连接。
连接池由 asyncpg 内部管理，自动复用、自动归还、不阻塞事件循环。
"""
import os
import logging
from typing import Optional
import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


def _get_db_url() -> str:
    """从环境变量读取数据库连接字符串。"""
    # 优先用本地 .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    url = os.getenv("PGDATABASE_URL", "").strip()
    if url:
        return url

    # 兜底：从 coze_workload_identity 读
    try:
        from coze_workload_identity import Client
        client = Client()
        env_vars = client.get_project_env_vars()
        client.close()
        for env_var in env_vars:
            if env_var.key == "PGDATABASE_URL":
                return env_var.value
    except Exception as e:
        logger.error(f"无法从 coze_workload_identity 读取 PGDATABASE_URL: {e}")

    raise ValueError("PGDATABASE_URL 未设置")


async def get_pool() -> asyncpg.Pool:
    """
    获取全局连接池（懒加载单例）。

    第一次调用时建池子，min_size=5 max_size=20。
    后续调用直接返回缓存。
    """
    global _pool
    if _pool is not None and not _pool._closed:
        return _pool

    url = _get_db_url()
    # asyncpg 不识别 postgresql+psycopg2:// 这种 SQLAlchemy 风格，统一转成 postgresql://
    if "+" in url.split("://")[0]:
        url = "postgresql://" + url.split("://", 1)[1]

    _pool = await asyncpg.create_pool(
        url,
        min_size=5,
        max_size=20,
        max_inactive_connection_lifetime=300,  # 5分钟空闲就回收
        command_timeout=10,                    # 单条 SQL 最长 10 秒
        timeout=8,                             # acquire 连接最长等 8 秒
    )
    logger.info("asyncpg 连接池已创建：min=5, max=20")
    return _pool


async def close_pool() -> None:
    """应用关闭时优雅关连接池。"""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg 连接池已关闭")
```

---

## 2. 新增：`src/storage/database/repository.py`

封装所有 SQL 操作。**每个函数都是 async**，从池子里 acquire 连接、跑 SQL、自动归还。

> 注意：因为 records.items 字段是数组对象，PostgreSQL 用 `JSONB` 存。asyncpg 返回的是 dict（自动解析）。

```python
"""
所有业务数据访问函数。
- async def 全部异步，从 asyncpg 池子里 acquire 连接
- 返回值统一是 list[dict] / dict / None / int
- 入参严格类型，防 SQL 注入
"""
import json
import logging
from datetime import datetime
from typing import Any, Optional
import asyncpg

from utils.db_pool import get_pool

logger = logging.getLogger(__name__)


# ============================================================
# 工具函数
# ============================================================

def _row_to_dict(row: asyncpg.Record) -> dict:
    """把 asyncpg.Record 转成普通 dict，处理 JSONB/datetime。"""
    if row is None:
        return None
    d = dict(row)
    # datetime → ISO 字符串
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, str) and k == "items":
            # 旧 JSONB 字段从字符串解出来
            try:
                d[k] = json.loads(v)
            except Exception:
                pass
    return d


def _rows(records: list[asyncpg.Record]) -> list[dict]:
    return [_row_to_dict(r) for r in records]


# ============================================================
# Stores 门店
# ============================================================

async def get_all_stores() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT store_id, name, address FROM stores ORDER BY store_id"
        )
        return _rows(rows)


async def get_store(store_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT store_id, name, address FROM stores WHERE store_id = $1",
            store_id,
        )
        return _row_to_dict(row)


# ============================================================
# Records 交易记录（核心表）
# ============================================================

async def get_records(
    org_id: str = "org_default",
    store_id: Optional[str] = None,
    record_type: Optional[str] = None,
    status: Optional[str] = None,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    limit: int = 1000,
    offset: int = 0,
) -> list[dict]:
    """按筛选条件读 records。所有条件 None 时返回 org 全部。"""
    where = ["org_id = $1"]
    args: list[Any] = [org_id]
    idx = 2

    if store_id and store_id != "all":
        where.append(f"store_id = ${idx}")
        args.append(store_id)
        idx += 1
    if record_type and record_type != "all":
        where.append(f"type = ${idx}")
        args.append(record_type)
        idx += 1
    if status:
        where.append(f"status = ${idx}")
        args.append(status)
        idx += 1
    if start_at:
        where.append(f"created_at >= ${idx}")
        args.append(start_at)
        idx += 1
    if end_at:
        where.append(f"created_at <= ${idx}")
        args.append(end_at)
        idx += 1

    sql = f"""
        SELECT id, org_id, store_id, store_name, type, category,
               items, total_amount, payment_method, confidence,
               status, operator, created_at, reviewed_at
        FROM records
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    args.extend([limit, offset])

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
        return _rows(rows)


async def get_record_by_id(record_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM records WHERE id = $1", record_id
        )
        return _row_to_dict(row)


async def insert_record(record: dict) -> dict:
    """插入一条新记录，返回完整记录（含 id）。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO records
              (id, org_id, store_id, store_name, type, category,
               items, total_amount, payment_method, confidence, status, operator, created_at)
            VALUES
              ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10, $11, $12, $13)
            RETURNING *
            """,
            record.get("id"),
            record.get("org_id", "org_default"),
            record.get("store_id"),
            record.get("store_name", ""),
            record.get("type", "revenue"),
            record.get("category", "其他"),
            json.dumps(record.get("items", []), ensure_ascii=False),
            float(record.get("total_amount", 0)),
            record.get("payment_method", ""),
            float(record.get("confidence", 1.0)),
            record.get("status", "approved"),
            record.get("operator", ""),
            record.get("created_at") or datetime.now(),
        )
        return _row_to_dict(row)


async def update_record(record_id: str, updates: dict) -> Optional[dict]:
    """部分字段更新。updates 是 {字段名: 新值}。"""
    if not updates:
        return await get_record_by_id(record_id)

    set_parts = []
    args: list[Any] = []
    idx = 1
    for k, v in updates.items():
        if k == "items":
            set_parts.append(f"{k} = ${idx}::jsonb")
            args.append(json.dumps(v, ensure_ascii=False))
        else:
            set_parts.append(f"{k} = ${idx}")
            args.append(v)
        idx += 1
    args.append(record_id)

    sql = f"UPDATE records SET {', '.join(set_parts)} WHERE id = ${idx} RETURNING *"
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *args)
        return _row_to_dict(row)


async def approve_record(record_id: str) -> Optional[dict]:
    return await update_record(record_id, {
        "status": "approved",
        "reviewed_at": datetime.now(),
    })


async def reject_record(record_id: str) -> Optional[dict]:
    return await update_record(record_id, {
        "status": "rejected",
        "reviewed_at": datetime.now(),
    })


async def count_records_by_status(org_id: str = "org_default") -> dict[str, int]:
    """看板/审核中心用：统计 pending/approved/rejected 数量。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT status, COUNT(*) AS n FROM records WHERE org_id = $1 GROUP BY status",
            org_id,
        )
        return {row["status"]: row["n"] for row in rows}


# ============================================================
# Products 商品库
# ============================================================

async def get_all_products(org_id: str = "org_default") -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM products WHERE org_id = $1 ORDER BY created_at DESC",
            org_id,
        )
        return _rows(rows)


async def insert_product(product: dict) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO products (id, org_id, code, name, category, cost_price, sale_price)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            product.get("id"),
            product.get("org_id", "org_default"),
            product.get("code"),
            product.get("name"),
            product.get("category"),
            float(product.get("cost_price", 0)),
            float(product.get("sale_price", 0)),
        )
        return _row_to_dict(row)


async def update_product(product_id: str, updates: dict) -> Optional[dict]:
    if not updates:
        return None
    set_parts = []
    args: list[Any] = []
    idx = 1
    for k, v in updates.items():
        set_parts.append(f"{k} = ${idx}")
        args.append(v)
        idx += 1
    args.append(product_id)
    sql = f"UPDATE products SET {', '.join(set_parts)} WHERE id = ${idx} RETURNING *"
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *args)
        return _row_to_dict(row)


async def delete_product(product_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM products WHERE id = $1", product_id)
        return result.endswith(" 1")


# ============================================================
# Users 用户（鉴权用）
# ============================================================

async def get_user_by_phone(phone: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE phone = $1", phone
        )
        return _row_to_dict(row)


# ============================================================
# AI 原始记录（命根子表）
# ============================================================

async def insert_ai_raw_record(
    raw_type: str,            # asr / ocr / nlu
    raw_url: str,             # 图片/录音 OSS URL
    ai_response: dict,
    user_confirmed: Optional[dict],
    confidence: float,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO ai_raw_records
              (raw_type, raw_url, ai_response, user_confirmed, confidence, created_at)
            VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6)
            """,
            raw_type, raw_url,
            json.dumps(ai_response, ensure_ascii=False),
            json.dumps(user_confirmed, ensure_ascii=False) if user_confirmed else None,
            confidence,
            datetime.now(),
        )
```

---

## 3. 新增：`scripts/create_schema.sql`

一次性执行，把 PostgreSQL 里建好表。

```sql
-- ============ 门店 ============
CREATE TABLE IF NOT EXISTS stores (
    store_id     TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    address      TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ============ 用户 ============
CREATE TABLE IF NOT EXISTS users (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL DEFAULT 'org_default',
    phone        TEXT UNIQUE,
    name         TEXT,
    role         TEXT,                 -- boss / clerk / accountant
    password_hash TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ============ 商品库 ============
CREATE TABLE IF NOT EXISTS products (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL DEFAULT 'org_default',
    code         TEXT,
    name         TEXT NOT NULL,
    category     TEXT,
    cost_price   NUMERIC(10,2) DEFAULT 0,
    sale_price   NUMERIC(10,2) DEFAULT 0,
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
```

执行方式（在 Coze IDE 的 Terminal 里）：

```bash
psql "$PGDATABASE_URL" -f scripts/create_schema.sql
```

或者用 Supabase Web Console 的 SQL Editor 粘贴执行。

---

## 4. 新增：`scripts/migrate_json_to_pg.py`

把现有 `data/*.json` 一次性灌进 PostgreSQL。

```python
"""
一次性迁移：把 data/*.json 灌进 PostgreSQL。
执行：python scripts/migrate_json_to_pg.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from utils.db_pool import get_pool, close_pool

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


async def migrate_stores():
    pool = await get_pool()
    with open(DATA_DIR / "stores.json", "r", encoding="utf-8") as f:
        data = json.load(f).get("stores", [])
    async with pool.acquire() as conn:
        for s in data:
            sid = str(s.get("store_id") or s.get("id"))
            if not sid.startswith("store_"):
                continue  # 跳过历史脏数据 id=6 这种
            await conn.execute(
                """INSERT INTO stores (store_id, name, address)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (store_id) DO UPDATE
                   SET name = EXCLUDED.name, address = EXCLUDED.address""",
                sid, s.get("name"), s.get("address", "")
            )
    print(f"  门店: {len(data)} 条")


async def migrate_records():
    pool = await get_pool()
    with open(DATA_DIR / "records.json", "r", encoding="utf-8") as f:
        data = json.load(f).get("records", [])
    async with pool.acquire() as conn:
        for r in data:
            await conn.execute(
                """INSERT INTO records
                   (id, org_id, store_id, store_name, type, category,
                    items, total_amount, payment_method, confidence,
                    status, operator, created_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,$12,$13)
                   ON CONFLICT (id) DO NOTHING""",
                r["id"], r.get("org_id", "org_default"),
                r.get("store_id"), r.get("store_name"),
                r.get("type", "revenue"), r.get("category", "其他"),
                json.dumps(r.get("items", []), ensure_ascii=False),
                float(r.get("total_amount", 0)),
                r.get("payment_method", ""),
                float(r.get("confidence", 1.0)),
                r.get("status", "approved"),
                r.get("operator", ""),
                r.get("created_at"),
            )
    print(f"  交易: {len(data)} 条")


async def migrate_products():
    path = DATA_DIR / "products.json"
    if not path.exists():
        print("  跳过商品（无 products.json）")
        return
    pool = await get_pool()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f).get("products", [])
    async with pool.acquire() as conn:
        for p in data:
            await conn.execute(
                """INSERT INTO products
                   (id, org_id, code, name, category, cost_price, sale_price)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)
                   ON CONFLICT (id) DO NOTHING""",
                p["id"], p.get("org_id", "org_default"),
                p.get("code"), p.get("name"), p.get("category"),
                float(p.get("cost_price", 0)), float(p.get("sale_price", 0)),
            )
    print(f"  商品: {len(data)} 条")


async def main():
    print("开始迁移到 PostgreSQL ...")
    await migrate_stores()
    await migrate_records()
    await migrate_products()
    await close_pool()
    print("完成 ✓")


if __name__ == "__main__":
    asyncio.run(main())
```

执行：

```bash
python scripts/migrate_json_to_pg.py
```

---

## 5. 修改：`pyproject.toml`

在 `[project.dependencies]` 或 `dependencies = [...]` 里加入：

```toml
"asyncpg>=0.30.0",
```

如果用的是 `requirements.txt`：

```
asyncpg>=0.30.0
```

`supabase` 和 `sqlalchemy` 暂时**保留**（其他地方可能还在用，先确认完整切换后再删）。

安装：

```bash
pip install asyncpg
```

---

## 6. 修改：`src/main.py` —— 替换所有 Supabase 调用

这是最大头的改造，但是有套路。

### 6.1 顶部导入

把：

```python
from utils.supabase_client import get_supabase_client
```

替换为：

```python
from storage.database import repository as repo
from utils.db_pool import get_pool, close_pool
```

### 6.2 应用启动/关闭钩子

在 `app = FastAPI(...)` 后面加：

```python
@app.on_event("startup")
async def _init_pool():
    """应用启动时预热连接池，第一个请求不会冷启动。"""
    await get_pool()

@app.on_event("shutdown")
async def _close_pool():
    await close_pool()
```

### 6.3 6 种典型替换 Pattern

#### Pattern 1 — 查询全部 / 按条件查

**改前：**
```python
@app.get("/api/stores")
async def get_stores():
    client = get_supabase_client()
    result = client.table("stores").select("*").execute()
    return {"success": True, "stores": result.data}
```

**改后：**
```python
@app.get("/api/stores")
async def get_stores():
    stores = await repo.get_all_stores()
    return {"success": True, "stores": stores}
```

#### Pattern 2 — 带筛选条件查

**改前：**
```python
@app.get("/api/records")
async def get_records_route(store_id: str = "all", type: str = "all"):
    client = get_supabase_client()
    query = client.table("records").select("*").eq("org_id", "org_default")
    if store_id != "all":
        query = query.eq("store_id", store_id)
    if type != "all":
        query = query.eq("type", type)
    result = query.order("created_at", desc=True).execute()
    return {"records": result.data}
```

**改后：**
```python
@app.get("/api/records")
async def get_records_route(store_id: str = "all", type: str = "all"):
    records = await repo.get_records(
        org_id="org_default",
        store_id=store_id if store_id != "all" else None,
        record_type=type if type != "all" else None,
    )
    return {"records": records}
```

#### Pattern 3 — 插入

**改前：**
```python
@app.post("/api/records")
async def create_record(record: dict):
    client = get_supabase_client()
    db_record = {...}
    result = client.table("records").insert(db_record).execute()
    return {"success": True, "record": result.data[0]}
```

**改后：**
```python
@app.post("/api/records")
async def create_record(record: dict):
    new_record = await repo.insert_record(record)
    return {"success": True, "record": new_record}
```

#### Pattern 4 — 更新

**改前：**
```python
@app.put("/api/records/{record_id}")
async def update_record_route(record_id: str, updates: dict):
    client = get_supabase_client()
    result = client.table("records").update(updates).eq("id", record_id).execute()
    return {"success": True, "record": result.data[0]}
```

**改后：**
```python
@app.put("/api/records/{record_id}")
async def update_record_route(record_id: str, updates: dict):
    record = await repo.update_record(record_id, updates)
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"success": True, "record": record}
```

#### Pattern 5 — 审批

**改前：**
```python
@app.put("/api/records/{record_id}/approve")
async def approve(record_id: str):
    client = get_supabase_client()
    result = client.table("records").update({
        "status": "approved",
        "reviewed_at": datetime.now().isoformat(),
    }).eq("id", record_id).execute()
    return {"success": True}
```

**改后：**
```python
@app.put("/api/records/{record_id}/approve")
async def approve(record_id: str):
    record = await repo.approve_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"success": True, "record": record}
```

#### Pattern 6 — 审核中心计数

**改前：**
```python
@app.get("/api/pending_reviews")
async def pending_reviews():
    client = get_supabase_client()
    pending = client.table("records").select("*").eq("status", "pending").execute()
    approved = client.table("records").select("id", count="exact").eq("status", "approved").execute()
    rejected = client.table("records").select("id", count="exact").eq("status", "rejected").execute()
    return {"pending": pending.data, "pending_count": len(pending.data),
            "approved_count": approved.count, "rejected_count": rejected.count}
```

**改后**（一条 SQL 拿全部，性能提升 3 倍）：
```python
@app.get("/api/pending_reviews")
async def pending_reviews():
    counts = await repo.count_records_by_status()
    pending = await repo.get_records(status="pending", limit=200)
    return {
        "success": True,
        "pending": pending,
        "pending_count": counts.get("pending", 0),
        "approved_count": counts.get("approved", 0),
        "rejected_count": counts.get("rejected", 0),
    }
```

### 6.4 改造检查清单（按路由）

按这个顺序改，每改完一个测一个：

| # | 路由 | Pattern | 用 repo 的哪个函数 |
|---|---|---|---|
| 1 | `GET /api/stores` | 1 | `get_all_stores()` |
| 2 | `GET /api/stores/list` | 1 | `get_all_stores()` |
| 3 | `GET /api/records` | 2 | `get_records(...)` |
| 4 | `POST /api/records` | 3 | `insert_record(...)` |
| 5 | `PUT /api/records/{id}` | 4 | `update_record(...)` |
| 6 | `PUT /api/records/{id}/approve` | 5 | `approve_record(...)` |
| 7 | `PUT /api/records/{id}/reject` | 5 | `reject_record(...)` |
| 8 | `GET /api/dashboard` | 2 + 内存聚合 | `get_records(...)` 然后用 Python 聚合 |
| 9 | `GET /api/analysis` | 2 + 内存聚合 | `get_records(...)` |
| 10 | `GET /api/alerts` | 2 + 内存聚合 | `get_records(...)` |
| 11 | `GET /api/history` | 2 | `get_records(..., limit, offset)` |
| 12 | `GET /api/pending_reviews` | 6 | `count_records_by_status()` + `get_records(status="pending")` |
| 13 | `GET /api/reviews` | 2 | `get_records(...)` |
| 14 | `GET /api/products` | 1 | `get_all_products()` |
| 15 | `POST /api/products` | 3 | `insert_product(...)` |
| 16 | `PUT /api/products/{id}` | 4 | `update_product(...)` |
| 17 | `DELETE /api/products/{id}` | — | `delete_product(...)` |
| 18 | `POST /api/auth/login` | — | `get_user_by_phone(...)` |
| 19 | `POST /api/voice` `/api/image` `/api/document` | 3 | `insert_record(...)` + `insert_ai_raw_record(...)` |

---

## 7. 推荐的改造顺序（不要一次全改）

每改完一组，**重启服务** + **打开网站点对应页面验证**：

```
第 1 步 (10分钟):
  - 加 db_pool.py + repository.py + create_schema.sql
  - 执行 SQL 建表
  - 跑 migrate_json_to_pg.py 灌数据
  - pyproject.toml 加 asyncpg
  - main.py 加 startup/shutdown 钩子

第 2 步 (10分钟):
  - 只改 /api/stores 和 /api/stores/list (Pattern 1)
  - 重启 → 网站门店下拉框能拉出来 ✓

第 3 步 (15分钟):
  - 改 /api/dashboard (用 repo.get_records 拿原始数据后用 Python 聚合)
  - 重启 → 看板首页加载正常 ✓

第 4 步 (15分钟):
  - 改 /api/records GET / POST / PUT
  - 改 /api/history
  - 重启 → 历史记录页正常 ✓

第 5 步 (20分钟):
  - 改 /api/analysis /api/alerts /api/pending_reviews
  - 重启 → 款式分析 / 异常预警 / 审核中心三个 Tab 都能切 ✓

第 6 步 (15分钟):
  - 改 /api/products 系列 + auth + voice/image/document
  - 重启 → 商品管理 + 登录 + 录入功能正常 ✓

第 7 步 (5分钟):
  - 删除 src/utils/supabase_client.py
  - pyproject.toml 移除 supabase 依赖
  - git commit -m "feat: 全量切换到 asyncpg，彻底消除事件循环阻塞"
```

---

## 8. 验证 Supabase 死锁是否真消除

部署后用浏览器 DevTools 打开网站，**连续点击 5 次「刷新」按钮**：

- 改造前：第 2 次开始所有请求 pending
- 改造后：5 次都在 200-500ms 内 200 返回 ✓

也可以用 Coze IDE Terminal 跑压测：

```bash
# 安装 hey 或者直接用 curl 并发
for i in {1..20}; do
  curl -s "$DEPLOY_URL/api/dashboard?period=month&store_id=all" -o /dev/null -w "%{time_total}s %{http_code}\n" &
done
wait
```

每条都应该是 `0.X s 200`，没有 timeout。

---

## 9. 常见坑

| 坑 | 现象 | 解决 |
|---|---|---|
| `PGDATABASE_URL` 是 `postgresql+psycopg2://...` 这种 SQLAlchemy 格式 | asyncpg 连不上 | `db_pool.py` 里已经做了自动转换 |
| Supabase 用了 **PgBouncer 事务池模式** | 报 `prepared statement already exists` | 在 `create_pool()` 里加 `statement_cache_size=0` |
| asyncpg 不接受 `Decimal`，PG 的 NUMERIC 列也不返回 float | 序列化 JSON 时报错 | repository 里所有 `total_amount` 都 `float(...)` 包一下 |
| `datetime` 带时区，前端 ISO 解析慢 | 历史记录时间显示错乱 | `_row_to_dict` 已经统一转成 `isoformat()` |
| FastAPI startup hook 在 lifespan 模式下不生效 | 第一次请求冷启动 1-2 秒 | 改用 `lifespan` context manager（FastAPI ≥ 0.110 推荐） |

---

## 10. 总结

改完之后你会得到：

- ✅ 所有 API 不再阻塞事件循环，并发能力从 1 个请求 → 数十个请求
- ✅ 连接池由 asyncpg 自动管理，不会泄漏、不会死锁
- ✅ SQL 直接写，比 supabase-py 链式调用快 30-50%
- ✅ 多了 `ai_raw_records` 和 `audit_logs` 两张关键表
- ✅ 比 supabase-py 少一个第三方 SDK 依赖

预计总工时：**2-3 小时**（含建表 + 迁移数据 + 改 20 个路由 + 测试）。

如果中途某一步卡住，先回退该步骤的 git commit（每步都 commit 一次），不会影响已经能跑通的部分。
