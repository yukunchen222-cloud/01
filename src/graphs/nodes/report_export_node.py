"""
报告导出节点 - 使用document-generation技能生成PDF/Excel报告
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import DocumentGenerationClient, PDFConfig, DOCXConfig, XLSXConfig


class ReportExportInput(BaseModel):
    """报告导出节点输入"""
    report_type: str = Field(default="pdf", description="报告类型: pdf/docx/xlsx")
    period: str = Field(default="month", description="统计周期: day/week/month")
    start_date: str = Field(default="", description="开始日期")
    end_date: str = Field(default="", description="结束日期")
    summary: Dict[str, Any] = Field(default={}, description="汇总数据")
    store_stats: Dict[str, Any] = Field(default={}, description="门店统计")
    category_stats: Dict[str, Any] = Field(default={}, description="品类统计")
    trend_data: List[Dict] = Field(default=[], description="趋势数据")
    anomaly_alerts: List[Dict] = Field(default=[], description="异常预警")
    product_analysis: Dict[str, Any] = Field(default={}, description="商品分析")
    org_name: str = Field(default="服装连锁", description="组织名称")


class ReportExportOutput(BaseModel):
    """报告导出节点输出"""
    success: bool = Field(default=False, description="是否成功")
    report_url: str = Field(default="", description="报告下载URL")
    report_type: str = Field(default="", description="报告类型")
    message: str = Field(default="", description="消息")


def report_export_node(
    state: ReportExportInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ReportExportOutput:
    """
    title: 报告导出
    desc: 生成PDF/Excel格式的经营分析报告，支持多种格式导出
    integrations: document-generation
    """
    ctx = runtime.context
    
    try:
        report_type = state.report_type.lower()
        
        if report_type == "xlsx":
            return _generate_xlsx_report(state)
        elif report_type == "docx":
            return _generate_docx_report(state)
        else:
            return _generate_pdf_report(state)
            
    except Exception as e:
        return ReportExportOutput(
            success=False,
            message=f"报告生成失败: {str(e)}"
        )


def _generate_pdf_report(state: ReportExportInput) -> ReportExportOutput:
    """生成PDF报告"""
    pdf_config = PDFConfig(
        page_size="A4",
        left_margin=72,
        right_margin=72,
        top_margin=72,
        bottom_margin=36
    )
    client = DocumentGenerationClient(pdf_config=pdf_config)
    
    # 构建Markdown内容
    period_text = {"day": "今日", "week": "本周", "month": "本月"}.get(state.period, "本月")
    
    markdown_content = f"""# {state.org_name}经营分析报告

## 报告概览

- **统计周期**: {period_text} ({state.start_date} 至 {state.end_date})
- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 一、经营概况

### 1.1 核心指标

| 指标 | 金额/数值 |
|------|----------|
| 总营收 | ¥{state.summary.get('total_revenue', 0):,.2f} |
| 总成本 | ¥{state.summary.get('total_cost', 0):,.2f} |
| 毛利润 | ¥{state.summary.get('gross_profit', 0):,.2f} |
| 净利润 | ¥{state.summary.get('net_profit', 0):,.2f} |
| 毛利率 | {state.summary.get('gross_margin', 0):.1%} |
| 净利率 | {state.summary.get('net_margin', 0):.1%} |
| 交易笔数 | {state.summary.get('transaction_count', 0)} 笔 |

### 1.2 环比变化

- **营收变化**: {_format_change(state.summary.get('revenue_change', 0))}
- **利润变化**: {_format_change(state.summary.get('profit_change', 0))}

---

## 二、门店业绩

{_format_store_stats(state.store_stats)}

---

## 三、品类分析

{_format_category_stats(state.category_stats)}

---

## 四、商品分析

### 4.1 畅销商品 TOP5

{_format_top_sellers(state.product_analysis.get('top_sellers', []))}

### 4.2 滞销商品预警

{_format_slow_sellers(state.product_analysis.get('slow_sellers', []))}

---

## 五、异常预警

{_format_anomaly_alerts(state.anomaly_alerts)}

---

## 六、固定费用

| 费用项目 | 金额 |
|---------|------|
| 房租 | ¥{state.summary.get('fixed_expenses', {}).get('rent', 0):,.2f} |
| 水电 | ¥{state.summary.get('fixed_expenses', {}).get('utilities', 0):,.2f} |
| 人工 | ¥{state.summary.get('fixed_expenses', {}).get('salary', 0):,.2f} |
| 其他 | ¥{state.summary.get('fixed_expenses', {}).get('other', 0):,.2f} |
| **合计** | **¥{sum(state.summary.get('fixed_expenses', {}).values()):,.2f}** |

---

*报告由AI记账助手自动生成*
"""
    
    title = f"business_report_{state.period}_{datetime.now().strftime('%Y%m%d')}"
    url = client.create_pdf_from_markdown(markdown_content, title)
    
    return ReportExportOutput(
        success=True,
        report_url=url,
        report_type="pdf",
        message="PDF报告生成成功"
    )


def _generate_docx_report(state: ReportExportInput) -> ReportExportOutput:
    """生成DOCX报告"""
    docx_config = DOCXConfig(
        font_name="Noto Sans CJK SC",
        font_size=11,
        top_margin=0.75,
        bottom_margin=0.75,
        left_margin=0.75,
        right_margin=0.75
    )
    client = DocumentGenerationClient(docx_config=docx_config)
    
    # 复用PDF的Markdown内容
    period_text = {"day": "今日", "week": "本周", "month": "本月"}.get(state.period, "本月")
    
    markdown_content = f"""# {state.org_name}经营分析报告

## 报告概览

- **统计周期**: {period_text} ({state.start_date} 至 {state.end_date})
- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 一、经营概况

### 核心指标

- 总营收: ¥{state.summary.get('total_revenue', 0):,.2f}
- 总成本: ¥{state.summary.get('total_cost', 0):,.2f}
- 毛利润: ¥{state.summary.get('gross_profit', 0):,.2f}
- 净利润: ¥{state.summary.get('net_profit', 0):,.2f}
- 毛利率: {state.summary.get('gross_margin', 0):.1%}
- 交易笔数: {state.summary.get('transaction_count', 0)} 笔

## 二、门店业绩

{_format_store_stats(state.store_stats)}

## 三、异常预警

{_format_anomaly_alerts(state.anomaly_alerts)}

---

*报告由AI记账助手自动生成*
"""
    
    title = f"business_report_{state.period}_{datetime.now().strftime('%Y%m%d')}"
    url = client.create_docx_from_markdown(markdown_content, title)
    
    return ReportExportOutput(
        success=True,
        report_url=url,
        report_type="docx",
        message="DOCX报告生成成功"
    )


def _generate_xlsx_report(state: ReportExportInput) -> ReportExportOutput:
    """生成Excel报告"""
    xlsx_config = XLSXConfig(
        header_bg_color="4472C4",
        auto_width=True
    )
    client = DocumentGenerationClient(xlsx_config=xlsx_config)
    
    # 构建Excel数据
    data = []
    
    # 汇总数据
    data.append({"项目": "=== 经营汇总 ===", "数值": "", "备注": ""})
    data.append({"项目": "统计周期", "数值": state.period, "备注": f"{state.start_date} 至 {state.end_date}"})
    data.append({"项目": "总营收", "数值": state.summary.get('total_revenue', 0), "备注": "元"})
    data.append({"项目": "总成本", "数值": state.summary.get('total_cost', 0), "备注": "元"})
    data.append({"项目": "毛利润", "数值": state.summary.get('gross_profit', 0), "备注": "元"})
    data.append({"项目": "净利润", "数值": state.summary.get('net_profit', 0), "备注": "元"})
    data.append({"项目": "毛利率", "数值": f"{state.summary.get('gross_margin', 0):.1%}", "备注": ""})
    data.append({"项目": "交易笔数", "数值": state.summary.get('transaction_count', 0), "备注": "笔"})
    data.append({"项目": "", "数值": "", "备注": ""})
    
    # 门店数据
    data.append({"项目": "=== 门店业绩 ===", "数值": "", "备注": ""})
    for store_id, stats in state.store_stats.items():
        store_name = stats.get('name', store_id)
        data.append({"项目": store_name, "数值": stats.get('revenue', 0), "备注": f"营收/利润率{stats.get('margin', 0):.1%}"})
    data.append({"项目": "", "数值": "", "备注": ""})
    
    # 品类数据
    data.append({"项目": "=== 品类分析 ===", "数值": "", "备注": ""})
    for category, stats in state.category_stats.items():
        data.append({"项目": category, "数值": stats.get('revenue', 0), "备注": f"占比{stats.get('percentage', 0):.1%}"})
    data.append({"项目": "", "数值": "", "备注": ""})
    
    # 异常预警
    data.append({"项目": "=== 异常预警 ===", "数值": "", "备注": ""})
    for alert in state.anomaly_alerts:
        data.append({"项目": alert.get('message', ''), "数值": alert.get('value', ''), "备注": alert.get('level', '')})
    
    title = f"business_report_{state.period}_{datetime.now().strftime('%Y%m%d')}"
    url = client.create_xlsx_from_list(data, title, "经营报告")
    
    return ReportExportOutput(
        success=True,
        report_url=url,
        report_type="xlsx",
        message="Excel报告生成成功"
    )


def _format_change(value: float) -> str:
    """格式化变化值"""
    if value > 0:
        return f"↑ {value:.1%}"
    elif value < 0:
        return f"↓ {abs(value):.1%}"
    else:
        return "持平"


def _format_store_stats(store_stats: Dict) -> str:
    """格式化门店统计"""
    if not store_stats:
        return "暂无数据"
    
    lines = ["| 门店 | 营收 | 利润率 |", "|------|------|--------|"]
    for store_id, stats in store_stats.items():
        name = stats.get('name', store_id)
        revenue = stats.get('revenue', 0)
        margin = stats.get('margin', 0)
        lines.append(f"| {name} | ¥{revenue:,.2f} | {margin:.1%} |")
    
    return "\n".join(lines)


def _format_category_stats(category_stats: Dict) -> str:
    """格式化品类统计"""
    if not category_stats:
        return "暂无数据"
    
    lines = ["| 品类 | 营收 | 占比 |", "|------|------|------|"]
    for category, stats in category_stats.items():
        revenue = stats.get('revenue', 0)
        percentage = stats.get('percentage', 0)
        lines.append(f"| {category} | ¥{revenue:,.2f} | {percentage:.1%} |")
    
    return "\n".join(lines)


def _format_top_sellers(top_sellers: List) -> str:
    """格式化畅销商品"""
    if not top_sellers:
        return "暂无数据"
    
    lines = ["| 排名 | 商品 | 销量 | 营收 |", "|------|------|------|------|"]
    for i, item in enumerate(top_sellers[:5], 1):
        name = item.get('name', '-')
        qty = item.get('quantity', 0)
        revenue = item.get('revenue', 0)
        lines.append(f"| {i} | {name} | {qty}件 | ¥{revenue:,.2f} |")
    
    return "\n".join(lines)


def _format_slow_sellers(slow_sellers: List) -> str:
    """格式化滞销商品"""
    if not slow_sellers:
        return "✅ 无滞销商品"
    
    lines = ["| 商品 | 库存 | 最后销售日期 |", "|------|------|------------|"]
    for item in slow_sellers:
        name = item.get('name', '-')
        stock = item.get('stock', 0)
        last_sale = item.get('last_sale_date', '-')
        lines.append(f"| {name} | {stock}件 | {last_sale} |")
    
    return "\n".join(lines)


def _format_anomaly_alerts(alerts: List) -> str:
    """格式化异常预警"""
    if not alerts:
        return "✅ 无异常"
    
    lines = []
    for alert in alerts:
        level = alert.get('level', 'info')
        emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(level, "⚠️")
        message = alert.get('message', '')
        lines.append(f"- {emoji} {message}")
    
    return "\n".join(lines)
