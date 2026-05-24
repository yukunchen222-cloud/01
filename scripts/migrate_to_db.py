#!/usr/bin/env python3
"""将JSON文件数据迁移到Supabase数据库 - 使用upsert避免重复"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.getenv("COZE_WORKSPACE_PATH", ""), "src"))

from utils.supabase_client import get_supabase_client


def upsert_table(table_name: str, data: list, transform=None, pk_col: str = "id"):
    """使用upsert迁移数据（有则更新，无则插入）"""
    client = get_supabase_client()
    
    if not data:
        print(f"  表 {table_name} 无数据需要迁移")
        return
    
    # 转换数据
    if transform:
        data = [transform(item) for item in data]
    
    # 批量upsert
    success = 0
    failed = 0
    for item in data:
        try:
            client.table(table_name).upsert(item, on_conflict=f"{pk_col}").execute()
            success += 1
        except Exception as e:
            failed += 1
            err_msg = str(e)[:150]
            if failed <= 3:
                print(f"  ❌ 失败: {err_msg}")
    
    print(f"  ✅ {table_name}: 成功{success}条, 失败{failed}条")


def transform_org(o: dict) -> dict:
    return {
        "org_id": o.get("org_id", o.get("id", "org_default")),
        "name": o.get("name", ""),
        "plan": o.get("plan", "free"),
        "is_active": True,
    }


def transform_store(s: dict) -> dict:
    return {
        "store_id": s.get("store_id", s.get("id", "")),
        "org_id": s.get("org_id", "org_default"),
        "name": s.get("name", ""),
        "address": s.get("address", ""),
        "manager_name": s.get("manager", s.get("manager_name", "")),
        "is_active": s.get("status", "active") == "active",
    }


def transform_user(u: dict) -> dict:
    return {
        "user_id": u.get("user_id", u.get("id", "")),
        "org_id": u.get("org_id", "org_default"),
        "username": u.get("username", ""),
        "password_hash": u.get("password_hash", ""),
        "role": u.get("role", "manager"),
        "store_ids": u.get("store_ids", []),
        "name": u.get("real_name", u.get("name", u.get("username", ""))),
        "phone": u.get("phone", ""),
        "is_active": True,
    }


def transform_product(p: dict) -> dict:
    return {
        "product_id": p.get("product_id", p.get("id", "")),
        "org_id": p.get("org_id", "org_default"),
        "sku": p.get("sku", ""),
        "name": p.get("name", ""),
        "category": p.get("category", ""),
        "cost_price": float(p.get("cost_price", 0)),
        "sale_price": float(p.get("unit_price", p.get("sale_price", 0))),
        "stock": int(p.get("stock", 0)),
        "status": p.get("status", "active"),
    }


def transform_record(r: dict) -> dict:
    items_val = r.get("items", [])
    if isinstance(items_val, str):
        try:
            items_val = json.loads(items_val)
        except Exception:
            items_val = []
    
    return {
        "record_id": r.get("record_id", r.get("id", "")),
        "org_id": r.get("org_id", "org_default"),
        "store_id": r.get("store_id", ""),
        "store_name": r.get("store_name", ""),
        "type": r.get("type", "revenue"),
        "category": r.get("category", ""),
        "items": items_val,
        "total_amount": float(r.get("total_amount", 0)),
        "payment_method": r.get("payment_method", ""),
        "confidence": float(r.get("confidence", 0)),
        "status": r.get("status", "pending"),
        "input_type": r.get("input_type", "voice"),
        "original_text": r.get("original_text", ""),
        "operator": r.get("operator", ""),
        "notes": r.get("notes", ""),
    }


def main():
    data_dir = os.path.join(os.getenv("COZE_WORKSPACE_PATH", ""), "data")
    
    print("=" * 50)
    print("开始数据迁移：JSON → Supabase (upsert模式)")
    print("=" * 50)
    
    # 按依赖顺序迁移：先父表后子表
    # 1. 组织
    print("\n📦 迁移 organizations...")
    with open(os.path.join(data_dir, "organizations.json"), "r") as f:
        org_data = json.load(f)
    upsert_table("organizations", org_data.get("organizations", []), transform_org, "org_id")
    
    # 2. 门店
    print("\n📦 迁移 stores...")
    with open(os.path.join(data_dir, "stores.json"), "r") as f:
        store_data = json.load(f)
    upsert_table("stores", store_data.get("stores", []), transform_store, "store_id")
    
    # 3. 用户
    print("\n📦 迁移 users...")
    with open(os.path.join(data_dir, "users.json"), "r") as f:
        user_data = json.load(f)
    upsert_table("users", user_data.get("users", []), transform_user, "user_id")
    
    # 4. 商品
    print("\n📦 迁移 products...")
    with open(os.path.join(data_dir, "products.json"), "r") as f:
        prod_data = json.load(f)
    upsert_table("products", prod_data.get("products", []), transform_product, "product_id")
    
    # 5. 记录
    print("\n📦 迁移 records...")
    with open(os.path.join(data_dir, "records.json"), "r") as f:
        rec_data = json.load(f)
    upsert_table("records", rec_data.get("records", []), transform_record, "record_id")
    
    # 验证
    print("\n" + "=" * 50)
    print("验证迁移结果:")
    client = get_supabase_client()
    for table in ["organizations", "stores", "users", "products", "records"]:
        try:
            result = client.table(table).select("*", count="exact").execute()
            print(f"  {table}: {result.count}条记录")
        except Exception as e:
            print(f"  {table}: 查询失败 - {str(e)[:80]}")
    
    print("\n✅ 数据迁移完成！")


if __name__ == "__main__":
    main()
