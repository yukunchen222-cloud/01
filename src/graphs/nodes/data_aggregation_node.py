"""
数据聚合节点
聚合账目数据，生成看板统计
"""
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import AggregationInput, AggregationOutput


def data_aggregation_node(
    state: AggregationInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> AggregationOutput:
    """
    title: 数据聚合
    desc: 聚合账目数据，生成看板统计信息，包括净利润、环比数据、款式分析等
    
    integrations: llm
    """
    ctx = runtime.context
    
    query_type = state.query_type or "month"
    store_id = state.store_id
    validated_data = state.validated_data
    records = list(state.records) if state.records else []
    fixed_expenses = state.fixed_expenses or {}
    last_period_data = state.last_period_data or {}
    
    # 如果有新的校验数据，添加到记录中
    if validated_data:
        records.append(validated_data)
    
    # 计算时间范围
    now = datetime.now()
    if query_type == "day":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_days = 1
    elif query_type == "month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_days = now.day
    else:  # year
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        period_days = now.timetuple().tm_yday
    
    # 初始化聚合变量
    total_revenue: float = 0.0
    total_cost: float = 0.0
    total_expense: float = 0.0
    total_returns: float = 0.0
    transaction_count: int = 0
    
    store_stats: Dict[str, Any] = {}
    category_stats: Dict[str, float] = {}
    product_sales: Dict[str, Dict[str, Any]] = {}
    
    # 遍历记录进行聚合（匹配records.json格式）
    for record in records:
        record_type = record.get("type", record.get("data_type", "revenue"))
        amount = float(record.get("total_amount", record.get("amount", 0)))
        record_store_id = record.get("store_id", "store_001")
        store_name = record.get("store_name", "默认门店")
        category = record.get("category", "其他")

        # 只统计已审核的记录
        if record.get("status") and record.get("status") != "approved":
            continue

        if record_type == "revenue":
            total_revenue += amount
        elif record_type == "purchase":
            total_cost += amount
        elif record_type == "return":
            total_returns += amount
        elif record_type == "expense":
            total_expense += amount

        transaction_count += 1

        # 门店统计
        if record_store_id not in store_stats:
            store_stats[record_store_id] = {
                "store_name": store_name,
                "revenue": 0.0,
                "cost": 0.0,
                "count": 0
            }
        if record_type == "revenue":
            store_stats[record_store_id]["revenue"] += amount
            store_stats[record_store_id]["count"] += 1
        elif record_type == "purchase":
            store_stats[record_store_id]["cost"] += amount

        # 品类统计（只统计营收）
        if record_type == "revenue":
            category_stats[category] = category_stats.get(category, 0.0) + amount

        # 商品销售统计（从items数组中提取）
        for item in record.get("items", []):
            item_name = item.get("name", "")
            if not item_name:
                continue
            if item_name not in product_sales:
                product_sales[item_name] = {
                    "name": item_name,
                    "category": category,
                    "total_sales": 0.0,
                    "quantity": 0
                }
            item_amount = float(item.get("amount", item.get("price", 0)) * item.get("quantity", 1))
            product_sales[item_name]["total_sales"] += item_amount
            product_sales[item_name]["quantity"] += int(item.get("quantity", 1))
    
    # 固定费用计算
    period_ratio = period_days / 30.0  # 按月计算
    period_fixed_expenses: Dict[str, float] = {
        "rent": float(fixed_expenses.get("rent", 0)) * period_ratio,
        "utilities": float(fixed_expenses.get("utilities", 0)) * period_ratio,
        "salary": float(fixed_expenses.get("salary", 0)) * period_ratio,
        "other": float(fixed_expenses.get("other", 0)) * period_ratio
    }
    total_fixed = sum(period_fixed_expenses.values())
    
    # 计算毛利和净利润
    gross_profit = total_revenue - total_cost
    gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0.0
    net_profit = gross_profit - total_expense - total_fixed + total_returns
    net_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0.0
    
    # 环比数据（从历史数据获取）
    last_revenue = float(last_period_data.get("total_revenue", 0))
    last_profit = float(last_period_data.get("net_profit", 0))
    
    revenue_change = ((total_revenue - last_revenue) / last_revenue * 100) if last_revenue > 0 else 0.0
    profit_change = ((net_profit - last_profit) / last_profit * 100) if last_profit > 0 else 0.0
    
    # 款式分析
    sorted_products = sorted(product_sales.values(), key=lambda x: x["total_sales"], reverse=True) if product_sales else []
    top_sellers = sorted_products[:5]  # 销量TOP5
    avg_threshold = total_revenue / max(len(sorted_products), 1) * 0.3
    slow_sellers = [p for p in sorted_products if p["total_sales"] < avg_threshold] if sorted_products else []
    
    # 趋势数据（从历史数据获取或生成空列表）
    trend_data: List[Dict[str, Any]] = []
    historical_trends = last_period_data.get("trend_data", [])
    if historical_trends:
        trend_data = historical_trends
    elif total_revenue > 0:
        for i in range(7):
            day_date = (now - timedelta(days=6-i)).strftime("%m-%d")
            trend_data.append({
                "date": day_date,
                "revenue": round(total_revenue / 7.0, 2)
            })
    
    # 生成看板数据
    dashboard_data: Dict[str, Any] = {
        "period": query_type,
        "start_date": start_date.isoformat(),
        "end_date": now.isoformat(),
        "summary": {
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2),
            "total_expense": round(total_expense, 2),
            "total_returns": round(total_returns, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_margin": round(gross_margin, 2),
            "net_profit": round(net_profit, 2),
            "net_margin": round(net_margin, 2),
            "transaction_count": transaction_count,
            "fixed_expenses": period_fixed_expenses,
            "revenue_change": round(revenue_change, 1),
            "profit_change": round(profit_change, 1)
        },
        "store_stats": store_stats,
        "category_stats": category_stats,
        "trend_data": trend_data,
        "product_analysis": {
            "top_sellers": top_sellers,
            "slow_sellers": slow_sellers,
            "product_count": len(sorted_products)
        }
    }
    
    return AggregationOutput(
        dashboard_data=dashboard_data
    )
