"""
NLU数据提取节点
从文本中提取结构化的账目数据，并使用商品知识库增强识别
"""
import os
import json
import re
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient
from graphs.state import NLUInput, NLUOutput
from utils.product_knowledge import get_product_knowledge_base
from utils.run_sync import run_sync


async def nlu_extraction_node(
    state: NLUInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> NLUOutput:
    """
    title: 数据提取
    desc: 使用大语言模型从文本中提取结构化的账目数据，并使用商品知识库增强商品识别
    
    integrations: llm
    """
    ctx = runtime.context
    
    # 根据输入类型选择文本来源
    text_content: str = ""
    if state.input_type == "voice":
        text_content = state.recognized_text
    elif state.input_type == "image":
        text_content = state.ocr_text
    else:
        text_content = state.recognized_text or state.ocr_text
    
    if not text_content:
        return NLUOutput(
            extracted_data={},
            confidence=0.0,
            data_type="sale"
        )
    
    # 读取配置文件
    cfg_path = config.get("metadata", {}).get("llm_cfg", "config/nlu_extraction_cfg.json")
    full_cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH", "."), cfg_path)
    
    with open(full_cfg_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    
    llm_config = cfg.get("config", {})
    sp = cfg.get("sp", "")
    up = cfg.get("up", "")
    
    # 获取商品知识库上下文（用于增强识别）
    org_id = state.org_id or "org_default"
    kb_context = _build_knowledge_context(org_id)
    
    # 渲染用户提示词，加入知识库上下文
    up_tpl = Template(up)
    user_prompt = up_tpl.render({
        "text": text_content,
        "input_source": state.input_type,
        "product_context": kb_context
    })
    
    # 初始化LLM客户端
    llm_client = LLMClient(ctx=ctx)
    
    try:
        # 调用大模型
        messages = [
            SystemMessage(content=sp),
            HumanMessage(content=user_prompt)
        ]
        
        response = await run_sync(
            llm_client.invoke,
            messages=messages,
            model=llm_config.get("model", "doubao-seed-2-0-lite-260215"),
            temperature=llm_config.get("temperature", 0.1)
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
        
        # 解析JSON结果
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            extracted_data = json.loads(json_match.group())
        else:
            extracted_data = {
                "raw_text": text_content,
                "parse_error": "无法解析结构化数据"
            }
        
        data_type = extracted_data.get("data_type") or "sale"
        confidence = extracted_data.get("confidence", 0.85)
        
        # 使用知识库增强商品识别
        extracted_fields = extracted_data.get("extracted_fields")
        if isinstance(extracted_fields, dict):
            items = extracted_fields.get("items", [])
            if items and isinstance(items, list):
                kb = get_product_knowledge_base(org_id)
                enriched_items = kb.enrich_nlu_result(items)
                extracted_fields["items"] = enriched_items
                extracted_data["knowledge_enhanced"] = True
                
                # 重新计算总金额（如果需要）
                total = sum(
                    item.get("amount", 0) or (item.get("quantity", 1) * item.get("unit_price", 0))
                    for item in enriched_items
                    if isinstance(item, dict)
                )
                if total > 0:
                    extracted_fields["total_amount"] = total
        
    except Exception as e:
        extracted_data = {
            "raw_text": text_content,
            "error": str(e)
        }
        data_type = "sale"
        confidence = 0.0
    
    return NLUOutput(
        extracted_data=extracted_data,
        confidence=confidence,
        data_type=data_type
    )


def _build_knowledge_context(org_id: str) -> str:
    """构建商品知识库上下文，用于提示词增强"""
    try:
        kb = get_product_knowledge_base(org_id)
        products = kb.get_all_products()
        
        if not products:
            return ""
        
        # 只取前20个商品作为上下文
        context_lines = ["【商品库参考】以下是一些已知商品，请优先匹配："]
        for p in products[:20]:
            context_lines.append(f"- {p['sku']}: {p['name']} (类目:{p.get('category','-')}, 售价:¥{p.get('sale_price',0)})")
        
        context_lines.append("\n如果用户输入的商品名称与上述商品相似，请使用正确的SKU和价格。")
        
        return "\n".join(context_lines)
    except Exception:
        return ""
