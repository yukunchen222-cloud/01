"""
数据库操作层 - 封装所有Supabase读写操作
替代原有的JSON文件存储
"""
import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from postgrest.exceptions import APIError

from utils.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def _get_client():
    """获取Supabase客户端"""
    return get_supabase_client()


# ============ 通用操作 ============

def _handle_error(operation: str, e: APIError) -> None:
    """统一错误处理"""
    logger.error(f"数据库操作失败 [{operation}]: {e.message}")
    raise Exception(f"数据库操作失败 [{operation}]: {e.message}")


# ============ 组织管理 ============

def get_organizations() -> List[Dict[str, Any]]:
    """获取所有组织"""
    try:
        client = _get_client()
        response = client.table("organizations").select("*").execute()
        return response.data if response.data else []
    except APIError as e:
        _handle_error("get_organizations", e)
        return []


def get_organization(org_id: str) -> Optional[Dict[str, Any]]:
    """获取单个组织"""
    try:
        client = _get_client()
        response = client.table("organizations").select("*").eq("id", org_id).maybe_single().execute()
        return response.data if response else None
    except APIError as e:
        _handle_error("get_organization", e)
        return None


# ============ 用户管理 ============

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """根据用户名获取用户"""
    try:
        client = _get_client()
        response = client.table("users").select("*").eq("username", username).maybe_single().execute()
        return response.data if response else None
    except APIError as e:
        _handle_error("get_user_by_username", e)
        return None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """根据ID获取用户"""
    try:
        client = _get_client()
        response = client.table("users").select("*").eq("id", user_id).maybe_single().execute()
        return response.data if response else None
    except APIError as e:
        _handle_error("get_user_by_id", e)
        return None


def get_users_by_org(org_id: str) -> List[Dict[str, Any]]:
    """获取组织下所有用户"""
    try:
        client = _get_client()
        response = client.table("users").select("*").eq("org_id", org_id).execute()
        return response.data if response.data else []
    except APIError as e:
        _handle_error("get_users_by_org", e)
        return []


# ============ 门店管理 ============

def get_stores(org_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取门店列表"""
    try:
        client = _get_client()
        query = client.table("stores").select("*")
        if org_id:
            query = query.eq("org_id", org_id)
        response = query.execute()
        return response.data if response.data else []
    except APIError as e:
        _handle_error("get_stores", e)
        return []


def get_store(store_id: str) -> Optional[Dict[str, Any]]:
    """获取单个门店"""
    try:
        client = _get_client()
        response = client.table("stores").select("*").eq("id", store_id).maybe_single().execute()
        return response.data if response else None
    except APIError as e:
        _handle_error("get_store", e)
        return None


# ============ 商品管理 ============

def get_stores_by_org_db(org_id: str) -> List[Dict[str, Any]]:
    """获取组织下所有门店"""
    try:
        client = _get_client()
        response = client.table("stores").select("*").eq("org_id", org_id).execute()
        stores = []
        for s in (response.data or []):
            stores.append({
                "id": s.get("store_id") or s.get("id"),
                "store_id": s.get("store_id") or s.get("id"),
                "name": s.get("name", ""),
                "address": s.get("address", "")
            })
        return stores
    except APIError as e:
        _handle_error("get_stores_by_org_db", e)
        return []


def get_products(org_id: Optional[str] = None, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取商品列表"""
    try:
        client = _get_client()
        query = client.table("products").select("*")
        if org_id:
            query = query.eq("org_id", org_id)
        if store_id:
            query = query.eq("store_id", store_id)
        response = query.order("name").execute()
        return response.data if response.data else []
    except APIError as e:
        _handle_error("get_products", e)
        return []


def get_product(product_id: str) -> Optional[Dict[str, Any]]:
    """获取单个商品"""
    try:
        client = _get_client()
        response = client.table("products").select("*").eq("id", product_id).maybe_single().execute()
        return response.data if response else None
    except APIError as e:
        _handle_error("get_product", e)
        return None


def create_product(product_data: Dict[str, Any]) -> Dict[str, Any]:
    """创建商品"""
    try:
        client = _get_client()
        response = client.table("products").insert(product_data).execute()
        return response.data[0] if response.data else {}
    except APIError as e:
        _handle_error("create_product", e)
        return {}


def update_product(product_id: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
    """更新商品"""
    try:
        client = _get_client()
        response = client.table("products").update(product_data).eq("id", product_id).execute()
        return response.data[0] if response.data else {}
    except APIError as e:
        _handle_error("update_product", e)
        return {}


def delete_product(product_id: str) -> bool:
    """删除商品"""
    try:
        client = _get_client()
        client.table("products").delete().eq("id", product_id).execute()
        return True
    except APIError as e:
        _handle_error("delete_product", e)
        return False


# ============ 记录管理 ============

def get_all_records(
    org_id: Optional[str] = None,
    store_id: Optional[str] = None,
    record_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """获取全部记录（不分页，用于聚合统计）"""
    try:
        client = _get_client()
        query = client.table("records").select("*")

        if org_id:
            query = query.eq("org_id", org_id)
        if store_id:
            query = query.eq("store_id", store_id)
        if record_type:
            query = query.eq("type", record_type)
        if status:
            query = query.eq("status", status)
        if start_date:
            query = query.gte("created_at", start_date)
        if end_date:
            query = query.lte("created_at", end_date + "T23:59:59")

        response = query.order("created_at", desc=True).limit(1000).execute()
        return response.data if response.data else []
    except APIError as e:
        _handle_error("get_all_records", e)
        return []


def get_records(
    org_id: Optional[str] = None,
    store_id: Optional[str] = None,
    record_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> Dict[str, Any]:
    """获取记录列表（分页）"""
    try:
        client = _get_client()
        query = client.table("records").select("*", count="exact")

        if org_id:
            query = query.eq("org_id", org_id)
        if store_id:
            query = query.eq("store_id", store_id)
        if record_type:
            query = query.eq("type", record_type)
        if status:
            query = query.eq("status", status)
        if start_date:
            query = query.gte("created_at", start_date)
        if end_date:
            query = query.lte("created_at", end_date + "T23:59:59")

        # 分页
        offset = (page - 1) * page_size
        query = query.order("created_at", desc=True).range(offset, offset + page_size - 1)

        response = query.execute()
        total = response.count if response.count is not None else 0
        records = response.data if response.data else []

        return {
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0
        }
    except APIError as e:
        _handle_error("get_records", e)
        return {"records": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}


def get_record(record_id: str) -> Optional[Dict[str, Any]]:
    """获取单条记录"""
    try:
        client = _get_client()
        response = client.table("records").select("*").eq("id", record_id).maybe_single().execute()
        return response.data if response else None
    except APIError as e:
        _handle_error("get_record", e)
        return None


def create_record(record_data: Dict[str, Any]) -> Dict[str, Any]:
    """创建记录"""
    try:
        client = _get_client()
        response = client.table("records").insert(record_data).execute()
        return response.data[0] if response.data else {}
    except APIError as e:
        _handle_error("create_record", e)
        return {}


def update_record(record_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
    """更新记录"""
    try:
        client = _get_client()
        response = client.table("records").update(record_data).eq("id", record_id).execute()
        return response.data[0] if response.data else {}
    except APIError as e:
        _handle_error("update_record", e)
        return {}


def approve_record(record_id: str, reviewer_id: str) -> Dict[str, Any]:
    """审核通过"""
    try:
        client = _get_client()
        response = client.table("records").update({
            "status": "approved",
            "reviewer_id": reviewer_id,
            "reviewed_at": datetime.now().isoformat()
        }).eq("id", record_id).execute()
        return response.data[0] if response.data else {}
    except APIError as e:
        _handle_error("approve_record", e)
        return {}


def reject_record(record_id: str, reviewer_id: str, reason: str = "") -> Dict[str, Any]:
    """审核驳回"""
    try:
        client = _get_client()
        response = client.table("records").update({
            "status": "rejected",
            "reviewer_id": reviewer_id,
            "reviewed_at": datetime.now().isoformat(),
            "reject_reason": reason
        }).eq("id", record_id).execute()
        return response.data[0] if response.data else {}
    except APIError as e:
        _handle_error("reject_record", e)
        return {}


# ============ 审核日志 ============

def get_audit_logs(
    org_id: Optional[str] = None,
    record_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """获取审核日志"""
    try:
        client = _get_client()
        query = client.table("audit_logs").select("*")
        if org_id:
            query = query.eq("org_id", org_id)
        if record_id:
            query = query.eq("record_id", record_id)
        response = query.order("created_at", desc=True).limit(limit).execute()
        return response.data if response.data else []
    except APIError as e:
        _handle_error("get_audit_logs", e)
        return []


def create_audit_log(log_data: Dict[str, Any]) -> Dict[str, Any]:
    """创建审核日志"""
    try:
        client = _get_client()
        response = client.table("audit_logs").insert(log_data).execute()
        return response.data[0] if response.data else {}
    except APIError as e:
        _handle_error("create_audit_log", e)
        return {}


# ============ 数据聚合 ============

def aggregate_dashboard(
    org_id: Optional[str] = None,
    store_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """聚合看板数据"""
    try:
        client = _get_client()

        # 查询已审核记录
        query = client.table("records").select("type, total_amount, store_id, items, created_at, category_name").eq("status", "approved")
        if org_id:
            query = query.eq("org_id", org_id)
        if store_id:
            query = query.eq("store_id", store_id)
        if start_date:
            query = query.gte("created_at", start_date)
        if end_date:
            query = query.lte("created_at", end_date + "T23:59:59")

        response = query.execute()
        records = response.data if response.data else []

        # 聚合计算
        total_revenue = 0.0
        total_cost = 0.0
        total_expense = 0.0
        total_returns = 0.0
        store_stats: Dict[str, Dict[str, float]] = {}
        category_stats: Dict[str, Dict[str, float]] = {}
        daily_stats: Dict[str, Dict[str, float]] = {}

        for r in records:
            r_type = r.get("type", "")
            amount = float(r.get("total_amount", 0))
            s_id = r.get("store_id", "unknown")
            items = r.get("items", [])
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except Exception:
                    items = []
            created = r.get("created_at", "")[:10]  # YYYY-MM-DD

            # 初始化门店统计
            if s_id not in store_stats:
                store_stats[s_id] = {"revenue": 0.0, "cost": 0.0, "count": 0}
            store_stats[s_id]["count"] += 1

            # 初始化日统计
            if created not in daily_stats:
                daily_stats[created] = {"revenue": 0.0, "cost": 0.0, "profit": 0.0}

            if r_type == "revenue":
                total_revenue += amount
                store_stats[s_id]["revenue"] += amount
                daily_stats[created]["revenue"] += amount
                # 品类统计
                for item in items:
                    cat = item.get("category", "其他") if isinstance(item, dict) else "其他"
                    if cat not in category_stats:
                        category_stats[cat] = {"revenue": 0.0, "cost": 0.0, "return_amount": 0.0}
                    category_stats[cat]["revenue"] += float(item.get("amount", 0)) if isinstance(item, dict) else 0
            elif r_type == "purchase":
                total_cost += amount
                store_stats[s_id]["cost"] += amount
                daily_stats[created]["cost"] += amount
                for item in items:
                    cat = item.get("category", "其他") if isinstance(item, dict) else "其他"
                    if cat not in category_stats:
                        category_stats[cat] = {"revenue": 0.0, "cost": 0.0, "return_amount": 0.0}
                    category_stats[cat]["cost"] += float(item.get("amount", 0)) if isinstance(item, dict) else 0
            elif r_type == "return":
                total_returns += amount
                daily_stats[created]["revenue"] -= amount
                for item in items:
                    cat = item.get("category", "其他") if isinstance(item, dict) else "其他"
                    if cat not in category_stats:
                        category_stats[cat] = {"revenue": 0.0, "cost": 0.0, "return_amount": 0.0}
                    category_stats[cat]["return_amount"] += float(item.get("amount", 0)) if isinstance(item, dict) else 0
            elif r_type == "expense":
                total_expense += amount
                daily_stats[created]["cost"] += amount

        # 计算利润
        gross_profit = total_revenue - total_cost
        gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0.0
        net_profit = gross_profit - total_expense - total_returns
        net_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0.0

        # 趋势数据（按日期排序）
        trend_data = []
        for d in sorted(daily_stats.keys()):
            v = daily_stats[d]
            trend_data.append({
                "date": d,
                "revenue": v["revenue"],
                "cost": v["cost"],
                "profit": v["revenue"] - v["cost"]
            })

        # 获取门店名称
        stores_resp = client.table("stores").select("id, name").execute()
        store_name_map = {s["id"]: s["name"] for s in (stores_resp.data or [])}
        store_stats_final = {}
        for s_id, vals in store_stats.items():
            store_stats_final[s_id] = {
                "store_name": store_name_map.get(s_id, s_id),
                "revenue": vals["revenue"],
                "cost": vals["cost"],
                "count": vals["count"]
            }

        return {
            "summary": {
                "total_revenue": total_revenue,
                "total_cost": total_cost,
                "total_expense": total_expense,
                "total_returns": total_returns,
                "gross_profit": gross_profit,
                "gross_margin": round(gross_margin, 1),
                "net_profit": net_profit,
                "net_margin": round(net_margin, 1),
                "transaction_count": len(records),
                "fixed_expenses": {"rent": 0.0, "utilities": 0.0, "salary": 0.0, "other": 0.0}
            },
            "store_stats": store_stats_final,
            "category_stats": category_stats,
            "trend_data": trend_data,
            "product_analysis": {
                "top_sellers": [],
                "slow_sellers": [],
                "product_count": 0
            }
        }
    except APIError as e:
        _handle_error("aggregate_dashboard", e)
        return {}
    except Exception as e:
        logger.error(f"聚合看板数据失败: {e}")
        return {}
