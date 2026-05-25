"""
所有业务数据访问函数。
- async def 全部异步，从 asyncpg 池子里 acquire 连接
- 返回值统一是 list[dict] / dict / None / int
- 入参严格类型，防 SQL 注入
"""
import json
import logging
import contextvars
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, List, Dict, AsyncIterator
import asyncpg

from utils.db_pool import get_pool

logger = logging.getLogger(__name__)

_in_acquire: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "in_acquire", default=False
)


def _check_no_nested_acquire() -> None:
    """Fail fast if repository code tries to acquire while already holding a connection."""
    if _in_acquire.get():
        raise RuntimeError(
            "Nested database acquire detected: do not call a repository function "
            "while another repository acquire block is still active."
        )


@asynccontextmanager
async def _acquire_conn() -> AsyncIterator[asyncpg.Connection]:
    _check_no_nested_acquire()
    pool = await get_pool()
    token = _in_acquire.set(True)
    try:
        async with pool.acquire() as conn:
            yield conn
    finally:
        _in_acquire.reset(token)


# ============================================================
# 工具函数
# ============================================================

def _row_to_dict(row: asyncpg.Record) -> Optional[dict]:
    """把 asyncpg.Record 转成普通 dict，统一处理 PG 类型。

    asyncpg 返回的特殊类型必须在这一层转干净，否则下游 Python 算术会报错：
    - NUMERIC  → decimal.Decimal  → float
    - REAL/FP  → float（保留 2 位，规避精度泄漏如 0.800000011920929）
    - JSONB    → 已是 dict/list，但旧表存成字符串时手动 json.loads
    - TIMESTAMPTZ → datetime → ISO 字符串
    """
    if row is None:
        return None
    d: dict = dict(row)
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, Decimal):
            # 金额类全部转 float，否则 main.py 里 Decimal * float 会 500
            d[k] = float(v)
        elif isinstance(v, float) and k in ("confidence",):
            # REAL 列存到 32 位浮点会有精度泄漏，前端展示也乱
            d[k] = round(v, 2)
        elif isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, str) and k == "items":
            try:
                d[k] = json.loads(v)
            except Exception:
                pass
    return d


def _rows(records: List[asyncpg.Record]) -> List[dict]:
    return [_row_to_dict(r) for r in records]


# ============================================================
# Stores 门店
# ============================================================

async def get_all_stores(org_id: Optional[str] = None) -> List[dict]:
    async with _acquire_conn() as conn:
        if org_id:
            rows = await conn.fetch(
                "SELECT store_id, name, address, org_id FROM stores WHERE org_id = $1 ORDER BY store_id",
                org_id,
            )
        else:
            rows = await conn.fetch(
                "SELECT store_id, name, address, org_id FROM stores ORDER BY store_id"
            )
        return _rows(rows)


# 别名：main.py 中使用 repo.get_stores
get_stores = get_all_stores


async def get_store(store_id: str) -> Optional[dict]:
    async with _acquire_conn() as conn:
        row = await conn.fetchrow(
            "SELECT store_id, name, address, org_id FROM stores WHERE store_id = $1",
            store_id,
        )
        return _row_to_dict(row)


# ============================================================
# Users 用户（鉴权用）
# ============================================================

async def get_user_by_username(username: str) -> Optional[dict]:
    async with _acquire_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE username = $1", username
        )
        return _row_to_dict(row)


async def get_user_by_id(user_id: str) -> Optional[dict]:
    async with _acquire_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1", user_id
        )
        return _row_to_dict(row)


async def get_users_by_org(org_id: str) -> List[dict]:
    async with _acquire_conn() as conn:
        rows = await conn.fetch(
            "SELECT * FROM users WHERE org_id = $1", org_id
        )
        return _rows(rows)


async def update_user_login_time(user_id: str) -> None:
    """更新用户最后登录时间。"""
    async with _acquire_conn() as conn:
        await conn.execute(
            "UPDATE users SET last_login = $1 WHERE id = $2",
            datetime.now(), user_id,
        )


# ============================================================
# Records 交易记录（核心表）
# ============================================================

async def get_records(
    org_id: str = "org_default",
    store_id: Optional[str] = None,
    record_type: Optional[str] = None,
    status: Optional[str] = None,
    start_at: Optional[str] = None,
    end_at: Optional[str] = None,
    limit: int = 10000,
    offset: int = 0,
) -> List[dict]:
    """按筛选条件读 records。所有条件 None 时返回 org 全部。"""
    where: List[str] = ["org_id = $1"]
    args: List[Any] = [org_id]
    idx: int = 2

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

    async with _acquire_conn() as conn:
        rows = await conn.fetch(sql, *args)
        return _rows(rows)


async def get_record_by_id(record_id: str) -> Optional[dict]:
    async with _acquire_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM records WHERE id = $1", record_id
        )
        return _row_to_dict(row)


async def insert_record(record: dict) -> dict:
    """插入一条新记录，返回完整记录（含 id）。"""
    async with _acquire_conn() as conn:
        # 处理 created_at：asyncpg 要求 TIMESTAMPTZ 列传入 datetime 对象
        created_at_val = record.get("created_at")
        if isinstance(created_at_val, str):
            try:
                created_at_val = datetime.fromisoformat(created_at_val.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                created_at_val = datetime.now()
        elif not isinstance(created_at_val, datetime):
            created_at_val = datetime.now()

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
            created_at_val,
        )
        return _row_to_dict(row)


async def update_record(record_id: str, updates: dict) -> Optional[dict]:
    """部分字段更新。updates 是 {字段名: 新值}。"""
    if not updates:
        return await get_record_by_id(record_id)

    set_parts: List[str] = []
    args: List[Any] = []
    idx: int = 1
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
    async with _acquire_conn() as conn:
        row = await conn.fetchrow(sql, *args)
        result = _row_to_dict(row)
        if result and "id" in result and "product_id" not in result:
            result["product_id"] = result["id"]
        return result


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


async def count_records_by_status(org_id: str = "org_default") -> Dict[str, int]:
    """看板/审核中心用：统计 pending/approved/rejected 数量。"""
    async with _acquire_conn() as conn:
        rows = await conn.fetch(
            "SELECT status, COUNT(*) AS n FROM records WHERE org_id = $1 GROUP BY status",
            org_id,
        )
        return {row["status"]: row["n"] for row in rows}


# ============================================================
# Products 商品库
# ============================================================

async def get_all_products(org_id: str = "org_default") -> List[dict]:
    async with _acquire_conn() as conn:
        rows = await conn.fetch(
            "SELECT * FROM products WHERE org_id = $1 ORDER BY created_at DESC",
            org_id,
        )
        result: List[dict] = _rows(rows)
        # 前端用 product_id 字段，数据库主键是 id，添加别名
        for p in result:
            if "id" in p and "product_id" not in p:
                p["product_id"] = p["id"]
        return result


# 别名：main.py 中使用 repo.get_products
get_products = get_all_products


async def insert_product(product: dict) -> dict:
    # 自动生成 id（如果未提供）
    if not product.get("id"):
        import uuid
        product["id"] = "prod_" + uuid.uuid4().hex[:16]
    async with _acquire_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO products (id, org_id, code, name, category, cost_price, sale_price, stock, sku)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
            """,
            product.get("id"),
            product.get("org_id", "org_default"),
            product.get("code") or product.get("sku"),
            product.get("name"),
            product.get("category"),
            float(product.get("cost_price", 0)),
            float(product.get("sale_price", 0)),
            int(product.get("stock", 0)),
            product.get("sku", ""),
        )
        result = _row_to_dict(row)
        if result and "id" in result and "product_id" not in result:
            result["product_id"] = result["id"]
        return result


async def update_product(product_id: str, updates: dict) -> Optional[dict]:
    if not updates:
        return None
    set_parts: List[str] = []
    args: List[Any] = []
    idx: int = 1
    for k, v in updates.items():
        set_parts.append(f"{k} = ${idx}")
        args.append(v)
        idx += 1
    args.append(product_id)
    sql = f"UPDATE products SET {', '.join(set_parts)} WHERE id = ${idx} RETURNING *"
    async with _acquire_conn() as conn:
        row = await conn.fetchrow(sql, *args)
        return _row_to_dict(row)


async def delete_product(product_id: str) -> bool:
    async with _acquire_conn() as conn:
        result = await conn.execute("DELETE FROM products WHERE id = $1", product_id)
        return result.endswith(" 1")


# ============================================================
# AI 原始记录（审计/调优用）
# ============================================================

async def insert_ai_raw_record(
    raw_type: str,            # asr / ocr / nlu
    raw_url: str,             # 图片/录音 OSS URL
    ai_response: dict,
    user_confirmed: Optional[dict],
    confidence: float,
) -> None:
    async with _acquire_conn() as conn:
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
