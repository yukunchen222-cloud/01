"""
飞书消息推送模块 - 用于异常预警通知和报告推送
"""
import json
import requests
from typing import Dict, Any, List, Optional
from cozeloop.decorator import observe


def get_webhook_url() -> str:
    """获取飞书机器人webhook URL"""
    try:
        from coze_workload_identity import Client
        client = Client()
        credential = client.get_integration_credential("integration-feishu-message")
        webhook_url = json.loads(credential).get("webhook_url", "")
        return webhook_url
    except Exception:
        # 未配置集成时返回空字符串
        return ""


@observe
def send_text_message(text: str, webhook_url: str = None) -> Dict:
    """
    发送文本消息
    
    Args:
        text: 消息内容
        webhook_url: webhook地址（可选，不传则自动获取）
    
    Returns:
        发送结果
    """
    if webhook_url is None:
        webhook_url = get_webhook_url()
    
    if not webhook_url:
        return {"status": "error", "message": "未配置飞书机器人"}
    
    payload = {
        "msg_type": "text",
        "content": {"text": text}
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@observe
def send_rich_text(title: str, content: str, link: str = None) -> Dict:
    """
    发送富文本消息
    
    Args:
        title: 标题
        content: 内容
        link: 链接（可选）
    
    Returns:
        发送结果
    """
    webhook_url = get_webhook_url()
    
    if not webhook_url:
        return {"status": "error", "message": "未配置飞书机器人"}
    
    content_elements = [{"tag": "text", "text": content}]
    if link:
        content_elements.append({"tag": "a", "text": "查看详情", "href": link})
    
    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": [content_elements]
                }
            }
        }
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@observe
def send_anomaly_alert(store_name: str, alerts: List[Dict], dashboard_url: str = None) -> Dict:
    """
    发送异常预警消息
    
    Args:
        store_name: 门店名称
        alerts: 预警列表
        dashboard_url: 看板链接（可选）
    
    Returns:
        发送结果
    """
    webhook_url = get_webhook_url()
    
    if not webhook_url:
        return {"status": "error", "message": "未配置飞书机器人"}
    
    if not alerts:
        return {"status": "skipped", "message": "无预警信息"}
    
    # 构建预警内容
    alert_lines = []
    for alert in alerts[:5]:  # 最多显示5条
        level = alert.get('level', 'info')
        emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(level, "⚠️")
        message = alert.get('message', '')
        alert_lines.append(f"{emoji} {message}")
    
    alert_text = "\n".join(alert_lines)
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"⚠️ {store_name}经营预警"},
                "template": "red" if any(a.get('level') == 'critical' for a in alerts) else "yellow"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": alert_text}
                }
            ]
        }
    }
    
    # 添加查看详情按钮
    if dashboard_url:
        payload["card"]["elements"].append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "查看数据看板"},
                    "type": "primary",
                    "url": dashboard_url
                }
            ]
        })
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@observe
def send_daily_report(
    store_name: str,
    summary: Dict,
    top_products: List[Dict] = None,
    report_url: str = None
) -> Dict:
    """
    发送每日经营简报
    
    Args:
        store_name: 门店名称
        summary: 经营汇总数据
        top_products: 畅销商品（可选）
        report_url: 报告下载链接（可选）
    
    Returns:
        发送结果
    """
    webhook_url = get_webhook_url()
    
    if not webhook_url:
        return {"status": "error", "message": "未配置飞书机器人"}
    
    # 构建简报内容
    revenue = summary.get('total_revenue', 0)
    profit = summary.get('gross_profit', 0)
    margin = summary.get('gross_margin', 0)
    transactions = summary.get('transaction_count', 0)
    change = summary.get('revenue_change', 0)
    
    change_text = f"↑ {change:.1%}" if change > 0 else f"↓ {abs(change):.1%}" if change < 0 else "持平"
    
    content = f"""**{store_name} - 今日经营简报**

💰 营收: ¥{revenue:,.2f} ({change_text})
📊 毛利: ¥{profit:,.2f}
📈 毛利率: {margin:.1%}
🛒 交易笔数: {transactions}笔"""
    
    elements = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": content}
        }
    ]
    
    # 添加畅销商品
    if top_products:
        product_text = "\n".join([f"{i+1}. {p.get('name', '-')} - {p.get('quantity', 0)}件" for i, p in enumerate(top_products[:3])])
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"\n**🔥 畅销TOP3**\n{product_text}"}
        })
    
    # 添加下载按钮
    if report_url:
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "下载详细报告"},
                    "type": "primary",
                    "url": report_url
                }
            ]
        })
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "📊 每日经营简报"},
                "template": "blue"
            },
            "elements": elements
        }
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@observe
def send_inventory_alert(store_name: str, low_stock_items: List[Dict]) -> Dict:
    """
    发送库存预警消息
    
    Args:
        store_name: 门店名称
        low_stock_items: 低库存商品列表
    
    Returns:
        发送结果
    """
    webhook_url = get_webhook_url()
    
    if not webhook_url:
        return {"status": "error", "message": "未配置飞书机器人"}
    
    if not low_stock_items:
        return {"status": "skipped", "message": "无库存预警"}
    
    # 构建库存预警内容
    items_text = "\n".join([
        f"• {item.get('name', '-')} ({item.get('sku', '-')}): 库存{item.get('stock', 0)}件"
        for item in low_stock_items[:10]
    ])
    
    content = f"""**{store_name} - 库存预警**

以下商品库存不足，请及时补货：

{items_text}"""
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "📦 库存预警"},
                "template": "orange"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": content}
                }
            ]
        }
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}
