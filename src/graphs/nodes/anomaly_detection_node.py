"""
异常检测节点
检测账目数据中的异常情况并生成预警
"""
import os
import json
import re
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient
from graphs.state import AnomalyInput, AnomalyOutput


def anomaly_detection_node(
    state: AnomalyInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> AnomalyOutput:
    """
    title: 异常检测
    desc: 检测账目数据中的异常情况并生成预警
    
    integrations: llm
    """
    ctx = runtime.context
    
    dashboard_data = state.dashboard_data
    records = state.records
    
    anomaly_alerts: List[Dict[str, Any]] = []
    
    # 读取配置文件
    cfg_path = config.get("metadata", {}).get("llm_cfg", "config/anomaly_detection_cfg.json")
    full_cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH", "."), cfg_path)
    
    with open(full_cfg_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    
    sp = cfg.get("sp", "")
    
    # 规则型异常检测
    summary = dashboard_data.get("summary", {})
    
    # 1. 毛利率过低预警
    gross_margin = summary.get("gross_margin", 0)
    if gross_margin < 20 and gross_margin > 0:
        anomaly_alerts.append({
            "type": "low_margin",
            "level": "warning",
            "message": f"毛利率偏低 ({gross_margin:.1f}%)，建议关注成本控制",
            "value": gross_margin
        })
    elif gross_margin <= 0:
        anomaly_alerts.append({
            "type": "negative_margin",
            "level": "critical",
            "message": f"毛利率为负 ({gross_margin:.1f}%)，存在严重亏损风险",
            "value": gross_margin
        })
    
    # 2. 门店业绩异常（如果有门店数据）
    store_stats = dashboard_data.get("store_stats", {})
    if store_stats:
        revenues = [s.get("revenue", 0) for s in store_stats.values()]
        avg_revenue = sum(revenues) / len(revenues) if revenues else 0
        
        for store_id, stats in store_stats.items():
            store_revenue = stats.get("revenue", 0)
            if avg_revenue > 0 and store_revenue < avg_revenue * 0.5:
                anomaly_alerts.append({
                    "type": "low_performance",
                    "level": "warning",
                    "message": f"门店 {store_id} 业绩显著低于平均水平",
                    "store_id": store_id,
                    "value": store_revenue
                })
    
    # 3. 使用LLM进行智能分析（如果有足够数据）
    if len(records) >= 3:
        try:
            llm_client = LLMClient(ctx=ctx)
            
            # 构建分析提示
            analysis_prompt = f"""分析以下经营数据，识别潜在的异常或风险：

经营概况：
- 总营收: ¥{summary.get('total_revenue', 0):,.2f}
- 总成本: ¥{summary.get('total_cost', 0):,.2f}
- 毛利润: ¥{summary.get('gross_profit', 0):,.2f}
- 毛利率: {summary.get('gross_margin', 0):.1f}%
- 交易笔数: {summary.get('transaction_count', 0)}

请识别可能的异常情况，返回JSON格式的预警列表：
{{"alerts": [{{"type": "异常类型", "level": "warning/critical", "message": "预警信息"}}]}}

如果没有明显异常，返回空列表。"""
            
            messages = [
                SystemMessage(content=sp),
                HumanMessage(content=analysis_prompt)
            ]
            
            response = llm_client.invoke(
                messages=messages,
                model="doubao-seed-2-0-mini-260215",
                temperature=0.1
            )
            
            # 安全地提取文本内容
            result_text = ""
            if isinstance(response.content, str):
                result_text = response.content
            elif isinstance(response.content, list):
                text_parts = []
                for item in response.content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        text_parts.append(item)
                result_text = " ".join(text_parts)
            else:
                result_text = str(response.content)
            
            # 解析LLM返回的预警
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                llm_result = json.loads(json_match.group())
                for alert in llm_result.get("alerts", []):
                    anomaly_alerts.append({
                        "type": alert.get("type", "llm_detected"),
                        "level": alert.get("level", "warning"),
                        "message": alert.get("message", ""),
                        "source": "ai_analysis"
                    })
                    
        except Exception as e:
            # LLM分析失败不影响基本检测
            pass
    
    has_anomaly = len(anomaly_alerts) > 0
    
    return AnomalyOutput(
        has_anomaly=has_anomaly,
        anomaly_alerts=anomaly_alerts
    )
