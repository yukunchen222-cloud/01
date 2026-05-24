"""
数据聚合节点
聚合账目数据，生成看板统计
"""
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
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
    desc: 聚合账目数据，生成看板统计信息
    
    integrations: llm
    """
    ctx = runtime.context
    
    query_type = state.query_type
    store_id = state.store_id
    validated_data = state.validated_data
    records = state.records
    
    # 如果有新的校验数据，添加到记录中
    if validated_data:
        records = list(records) + [validated_data]
    
    # 计算时间范围
    now = datetime.now()
    if query_type == "day":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif query_type == "month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # year
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # 聚合计算
    total_revenue: float = 0.0
    total_cost: float = 0.0
    total_expense: float = 0.0
    transaction_count: int = 0
    
    store_stats: Dict[str, Any] = {}
    category_stats: Dict[str, float] = {}
    
    for record in records:
        data_type = record.get("data_type", "sale")
        amount = float(record.get("amount", record.get("total_price", record.get("total_amount", 0))))
        
        if data_type == "sale":
            total_revenue += amount
        elif data_type == "purchase":
            total_cost += amount
        else:
            total_expense += amount
        
        transaction_count += 1
        
        # 门店统计
        record_store_id = record.get("store_id", "default")
        if record_store_id not in store_stats:
            store_stats[record_store_id] = {"revenue": 0, "count": 0}
        store_stats[record_store_id]["revenue"] += amount
        store_stats[record_store_id]["count"] += 1
        
        # 品类统计
        category = record.get("category", record.get("product_name", "其他"))
        category_stats[category] = category_stats.get(category, 0) + amount
    
    # 计算毛利
    gross_profit = total_revenue - total_cost
    gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    # 生成看板数据
    dashboard_data: Dict[str, Any] = {
        "period": query_type,
        "start_date": start_date.isoformat(),
        "end_date": now.isoformat(),
        "summary": {
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2),
            "total_expense": round(total_expense, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_margin": round(gross_margin, 2),
            "net_profit": round(gross_profit - total_expense, 2),
            "transaction_count": transaction_count
        },
        "store_stats": store_stats,
        "category_stats": category_stats
    }
    
    return AggregationOutput(
        dashboard_data=dashboard_data
    )
