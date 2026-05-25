"""
智能表格识别模块 - 使用大模型识别表格数据
"""
import json
import logging
import base64
from typing import List, Dict, Any, Optional
from coze_coding_dev_sdk import LLMClient
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# 系统提示词 - 商品表格识别
PRODUCT_TABLE_SP = """你是一个专业的表格数据提取专家，专门处理服装行业的商品清单、进货单、销售单等表格。

你的任务是：
1. 识别表格中的所有商品信息
2. 提取每个商品的款号(SKU)、名称、类目、进价、售价、库存等
3. 分析商品之间的连带关系（哪些商品经常一起进货或销售）
4. 将数据整理为标准JSON格式输出

字段映射规则：
- 款号/货号/编码/SKU/条码 → sku
- 商品名称/品名/名称 → name
- 类目/分类/类别/品类 → category
- 进价/成本价/采购价 → cost_price
- 售价/零售价/单价 → sale_price
- 库存/数量/库存数量 → stock

输出格式（必须是合法JSON）：
{
  "type": "products",  // 表格类型: products(商品清单) / purchase(进货单) / sales(销售单)
  "items": [
    {
      "sku": "款号",
      "name": "商品名称",
      "category": "类目",
      "cost_price": 进价(数字),
      "sale_price": 售价(数字),
      "stock": 库存(整数)
    }
  ],
  "relations": [
    {
      "sku1": "款号1",
      "sku2": "款号2", 
      "relation": "经常一起进货/搭配销售/同系列",
      "confidence": 0.8
    }
  ],
  "summary": {
    "total_items": 商品种类数,
    "total_quantity": 总数量,
    "total_value": 总金额,
    "notes": "其他备注信息"
  }
}

注意：
1. 必须返回合法的JSON格式
2. 数字字段不要加引号
3. 如果某个字段无法识别，使用默认值（category默认"其他"，价格默认0）
4. 分析连带关系时，考虑商品类目相似性、价格区间等因素
"""

# 进货单识别提示词
PURCHASE_TABLE_SP = """你是一个专业的表格数据提取专家，专门处理服装行业的进货单、采购单。

你的任务是：
1. 识别进货单中的商品信息
2. 提取每个商品的款号、名称、进货数量、进货价格
3. 分析进货模式（如：哪些商品经常一起采购）
4. 识别可能的供应商信息

输出格式（必须是合法JSON）：
{
  "type": "purchase",
  "supplier": "供应商名称（如有）",
  "date": "日期（如有）",
  "items": [
    {
      "sku": "款号",
      "name": "商品名称",
      "category": "类目",
      "cost_price": 进价(数字),
      "quantity": 进货数量(整数),
      "amount": 金额(数字)
    }
  ],
  "relations": [
    {
      "skus": ["款号1", "款号2"],
      "relation": "经常一起采购",
      "frequency": "高频/中频/低频"
    }
  ],
  "summary": {
    "total_items": 商品种类数,
    "total_quantity": 总数量,
    "total_amount": 总金额
  }
}
"""


def get_text_content(content: Any) -> str:
    """安全地提取文本内容"""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        if content and isinstance(content[0], str):
            return " ".join(content)
        else:
            return " ".join(
                item.get("text", "") 
                for item in content 
                if isinstance(item, dict) and item.get("type") == "text"
            )
    return str(content)


async def recognize_table_with_llm(
    image_url: str = None,
    image_base64: str = None,
    table_type: str = "auto"
) -> Dict[str, Any]:
    """
    使用大模型识别表格图片
    
    Args:
        image_url: 图片URL
        image_base64: 图片base64编码
        table_type: 表格类型 (auto/products/purchase/sales)
    
    Returns:
        识别结果字典
    """
    try:
        client = LLMClient()
        
        # 选择系统提示词
        if table_type == "purchase":
            sp = PURCHASE_TABLE_SP
        else:
            sp = PRODUCT_TABLE_SP
        
        # 构建图片URL
        if image_base64:
            img_url = f"data:image/jpeg;base64,{image_base64}"
        elif image_url:
            img_url = image_url
        else:
            return {"success": False, "error": "请提供图片URL或base64编码"}
        
        # 构建消息
        messages = [
            SystemMessage(content=sp),
            HumanMessage(content=[
                {"type": "text", "text": "请识别这张表格图片，提取其中的商品信息和连带关系，以JSON格式输出："},
                {"type": "image_url", "image_url": {"url": img_url}}
            ])
        ]
        
        # 调用大模型
        response = client.invoke(
            messages=messages,
            model="doubao-seed-1-8-251228",
            temperature=0.1
        )
        
        # 提取文本内容
        text_content = get_text_content(response.content)
        logger.info(f"大模型返回内容: {text_content[:500]}...")
        
        # 解析JSON
        # 尝试提取JSON部分
        json_start = text_content.find("{")
        json_end = text_content.rfind("}") + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = text_content[json_start:json_end]
            result = json.loads(json_str)
            result["success"] = True
            return result
        else:
            return {
                "success": False,
                "error": "无法从响应中提取JSON",
                "raw_response": text_content
            }
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}")
        return {"success": False, "error": f"JSON解析失败: {str(e)}"}
    except Exception as e:
        logger.error(f"表格识别失败: {e}")
        return {"success": False, "error": str(e)}


async def recognize_excel_with_llm(excel_content: bytes, filename: str) -> Dict[str, Any]:
    """
    使用大模型识别Excel文件内容（先将Excel转为文字描述）
    """
    import pandas as pd
    import io
    
    try:
        # 读取Excel
        suffix = filename.lower().rsplit(".", 1)[-1]
        buffer = io.BytesIO(excel_content)
        
        if suffix == "csv":
            df = pd.read_csv(buffer)
        elif suffix == "xlsx":
            df = pd.read_excel(buffer, engine="openpyxl")
        elif suffix == "xls":
            df = pd.read_excel(buffer, engine="xlrd")
        else:
            return {"success": False, "error": f"不支持的文件格式: {suffix}"}
        
        # 将DataFrame转为文字描述
        table_text = df.to_markdown(index=False)
        columns = list(df.columns)
        
        # 使用大模型分析
        client = LLMClient()
        
        sp = """你是一个专业的表格数据提取专家。请分析以下表格数据，提取商品信息和连带关系。

输出JSON格式：
{
  "type": "表格类型(products/purchase/sales)",
  "items": [{"sku": "款号", "name": "名称", "category": "类目", "cost_price": 进价, "sale_price": 售价, "stock": 库存}],
  "relations": [{"skus": ["款号1", "款号2"], "relation": "连带关系说明"}],
  "summary": {"total_items": 数量, "notes": "备注"}
}
"""
        
        messages = [
            SystemMessage(content=sp),
            HumanMessage(content=f"表格列名: {columns}\n\n表格数据:\n{table_text}\n\n请提取数据并以JSON格式输出:")
        ]
        
        response = client.invoke(
            messages=messages,
            model="doubao-seed-1-8-251228",
            temperature=0.1
        )
        
        text_content = get_text_content(response.content)
        
        # 解析JSON
        json_start = text_content.find("{")
        json_end = text_content.rfind("}") + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = text_content[json_start:json_end]
            result = json.loads(json_str)
            result["success"] = True
            return result
        else:
            return {"success": False, "error": "无法提取JSON", "raw_response": text_content}
            
    except Exception as e:
        logger.error(f"Excel识别失败: {e}")
        return {"success": False, "error": str(e)}


async def analyze_product_relations(items: List[Dict]) -> List[Dict]:
    """
    分析商品连带关系
    
    Args:
        items: 商品列表
    
    Returns:
        连带关系列表
    """
    if len(items) < 2:
        return []
    
    try:
        client = LLMClient()
        
        # 构建商品信息
        items_text = "\n".join([
            f"- {item.get('sku', 'N/A')}: {item.get('name', 'N/A')} ({item.get('category', '其他')})"
            for item in items[:50]  # 限制数量
        ])
        
        sp = """你是一个服装行业的销售分析专家。请分析以下商品列表，找出可能存在连带关系的商品组合。

连带关系包括：
1. 搭配销售关系（如：上衣+裤子，外套+内搭）
2. 同系列关系（同品牌、同风格）
3. 价格互补关系（高低搭配）
4. 季节搭配关系

输出JSON数组格式：
[
  {"skus": ["SKU1", "SKU2"], "relation": "搭配销售", "reason": "外套搭配内搭", "confidence": 0.9},
  ...
]
"""
        
        messages = [
            SystemMessage(content=sp),
            HumanMessage(content=f"商品列表:\n{items_text}\n\n请分析连带关系，输出JSON:")
        ]
        
        response = client.invoke(
            messages=messages,
            model="doubao-seed-1-8-251228",
            temperature=0.3
        )
        
        text_content = get_text_content(response.content)
        
        # 提取JSON数组
        json_start = text_content.find("[")
        json_end = text_content.rfind("]") + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = text_content[json_start:json_end]
            return json.loads(json_str)
        
        return []
        
    except Exception as e:
        logger.error(f"连带关系分析失败: {e}")
        return []
