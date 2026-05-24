"""
报告生成节点
生成月度/年度经营报告
"""
import os
import json
from datetime import datetime
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient
from graphs.state import ReportInput, ReportOutput


def report_generation_node(
    state: ReportInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ReportOutput:
    """
    title: 报告生成
    desc: 生成经营分析报告，支持日/月/年度报告
    
    integrations: llm
    """
    ctx = runtime.context
    
    dashboard_data = state.dashboard_data
    anomaly_alerts = state.anomaly_alerts
    query_type = state.query_type
    
    # 读取配置文件
    cfg_path = config.get("metadata", {}).get("llm_cfg", "config/report_generation_cfg.json")
    full_cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH", "."), cfg_path)
    
    with open(full_cfg_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    
    sp = cfg.get("sp", "")
    
    # 初始化LLM客户端
    llm_client = LLMClient(ctx=ctx)
    
    # 构建报告内容
    summary = dashboard_data.get("summary", {})
    store_stats = dashboard_data.get("store_stats", {})
    
    # 格式化预警信息
    alerts_text = ""
    if anomaly_alerts:
        alerts_text = "\n异常预警：\n"
        for alert in anomaly_alerts:
            alerts_text += f"- [{alert.get('level', 'warning')}] {alert.get('message', '')}\n"
    
    # 生成报告提示词
    report_prompt = f"""请根据以下经营数据生成一份{query_type}度经营分析报告：

【经营概况】
- 统计周期: {query_type}
- 总营收: ¥{summary.get('total_revenue', 0):,.2f}
- 总成本: ¥{summary.get('total_cost', 0):,.2f}
- 毛利润: ¥{summary.get('gross_profit', 0):,.2f}
- 毛利率: {summary.get('gross_margin', 0):.1f}%
- 净利润: ¥{summary.get('net_profit', 0):,.2f}
- 交易笔数: {summary.get('transaction_count', 0)}
{alerts_text}

【门店业绩】
{json.dumps(store_stats, ensure_ascii=False, indent=2)}

请生成包含以下内容的报告：
1. 经营概况总结
2. 业绩分析
3. 问题与建议
4. 下一步行动建议

报告格式要求：使用Markdown格式，内容专业、简洁。"""
    
    try:
        # 调用LLM生成报告
        messages = [
            SystemMessage(content=sp),
            HumanMessage(content=report_prompt)
        ]
        
        response = llm_client.invoke(
            messages=messages,
            model="doubao-seed-2-0-lite-260215",
            temperature=0.3
        )
        
        # 安全地提取文本内容
        report_content = ""
        if isinstance(response.content, str):
            report_content = response.content
        elif isinstance(response.content, list):
            text_parts = []
            for item in response.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            report_content = " ".join(text_parts)
        else:
            report_content = str(response.content)
        
    except Exception as e:
        # 如果LLM失败，生成基础报告
        report_content = f"""# {query_type}度经营报告

## 经营概况
- 总营收: ¥{summary.get('total_revenue', 0):,.2f}
- 毛利润: ¥{summary.get('gross_profit', 0):,.2f}
- 毛利率: {summary.get('gross_margin', 0):.1f}%

{alerts_text}

---
报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    
    # 保存报告到临时文件
    report_filename = f"report_{query_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    temp_path = f"/tmp/{report_filename}"
    
    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    # 返回本地文件路径（实际部署时可以上传到对象存储）
    report_url = f"file://{temp_path}"
    
    # 生成摘要
    report_summary = f"已生成{query_type}度经营报告，营收¥{summary.get('total_revenue', 0):,.2f}，毛利率{summary.get('gross_margin', 0):.1f}%"
    
    return ReportOutput(
        report_url=report_url,
        report_summary=report_summary
    )
