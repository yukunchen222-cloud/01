"""
一次性迁移：把 data/*.json 灌进 PostgreSQL。
执行：python scripts/migrate_json_to_pg.py
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# 确保 src 目录在 Python 路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from utils.db_pool import get_pool, close_pool

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _parse_dt(val) -> Optional[datetime]:
    """将字符串/None/datetime 统一转成 datetime 对象，供 asyncpg 写入 TIMESTAMPTZ。"""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
    return None


async def migrate_stores():
    pool = await get_pool()
    path = DATA_DIR / "stores.json"
    if not path.exists():
        print("  跳过门店（无 stores.json）")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f).get("stores", [])
    async with pool.acquire() as conn:
        for s in data:
            sid = str(s.get("store_id") or s.get("id", ""))
            if not sid:
                continue
            await conn.execute(
                """INSERT INTO stores (store_id, org_id, name, address)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (store_id) DO UPDATE
                   SET name = EXCLUDED.name, address = EXCLUDED.address, org_id = EXCLUDED.org_id""",
                sid,
                s.get("org_id", "org_default"),
                s.get("name", ""),
                s.get("address", ""),
            )
    print(f"  门店: {len(data)} 条")


async def migrate_users():
    pool = await get_pool()
    path = DATA_DIR / "users.json"
    if not path.exists():
        print("  跳过用户（无 users.json）")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f).get("users", [])
    async with pool.acquire() as conn:
        for u in data:
            uid = str(u.get("user_id") or u.get("id", ""))
            if not uid:
                continue
            store_ids = u.get("store_ids", [])
            if isinstance(store_ids, list):
                store_ids_json = json.dumps(store_ids, ensure_ascii=False)
            else:
                store_ids_json = "[]"
            await conn.execute(
                """INSERT INTO users (id, org_id, username, name, role, password_hash, phone, store_ids, is_active)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
                   ON CONFLICT (username) DO UPDATE
                   SET name = EXCLUDED.name, role = EXCLUDED.role, password_hash = EXCLUDED.password_hash""",
                uid,
                u.get("org_id", "org_default"),
                u.get("username", ""),
                u.get("name", ""),
                u.get("role", ""),
                u.get("password_hash", ""),
                u.get("phone", ""),
                store_ids_json,
                u.get("is_active", True),
            )
    print(f"  用户: {len(data)} 条")


async def migrate_records():
    pool = await get_pool()
    path = DATA_DIR / "records.json"
    if not path.exists():
        print("  跳过交易（无 records.json）")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f).get("records", [])
    async with pool.acquire() as conn:
        for r in data:
            rid = r.get("id", "")
            if not rid:
                continue
            await conn.execute(
                """INSERT INTO records
                   (id, org_id, store_id, store_name, type, category,
                    items, total_amount, payment_method, confidence,
                    status, operator, created_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,$12,$13)
                   ON CONFLICT (id) DO NOTHING""",
                rid, r.get("org_id", "org_default"),
                r.get("store_id"), r.get("store_name"),
                r.get("type", "revenue"), r.get("category", "其他"),
                json.dumps(r.get("items", []), ensure_ascii=False),
                float(r.get("total_amount", 0)),
                r.get("payment_method", ""),
                float(r.get("confidence", 1.0)),
                r.get("status", "approved"),
                r.get("operator", ""),
                _parse_dt(r.get("created_at")),
            )
    print(f"  交易: {len(data)} 条")


async def migrate_products():
    pool = await get_pool()
    path = DATA_DIR / "products.json"
    if not path.exists():
        print("  跳过商品（无 products.json）")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f).get("products", [])
    async with pool.acquire() as conn:
        for p in data:
            pid = str(p.get("product_id") or p.get("id", ""))
            if not pid:
                continue
            await conn.execute(
                """INSERT INTO products
                   (id, org_id, code, name, category, cost_price, sale_price)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)
                   ON CONFLICT (id) DO NOTHING""",
                pid, p.get("org_id", "org_default"),
                p.get("sku") or p.get("code"), p.get("name"), p.get("category"),
                float(p.get("cost_price", 0)), float(p.get("sale_price", 0)),
            )
    print(f"  商品: {len(data)} 条")


async def main():
    print("开始迁移到 PostgreSQL ...")
    await migrate_stores()
    await migrate_users()
    await migrate_records()
    await migrate_products()
    await close_pool()
    print("完成 ✓")


if __name__ == "__main__":
    asyncio.run(main())
