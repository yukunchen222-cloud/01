"""
NLU数据提取节点
从文本中提取结构化的账目数据
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


def nlu_extraction_node(
    state: NLUInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> NLUOutput:
    """
    title: 数据提取
    desc: 使用大语言模型从文本中提取结构化的账目数据
    
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
    
    # 渲染用户提示词
    up_tpl = Template(up)
    user_prompt = up_tpl.render({"text_content": text_content})
    
    # 初始化LLM客户端
    llm_client = LLMClient(ctx=ctx)
    
    try:
        # 调用大模型 - 使用 invoke 方法
        messages = [
            SystemMessage(content=sp),
            HumanMessage(content=user_prompt)
        ]
        
        response = llm_client.invoke(
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
        
        data_type = extracted_data.get("data_type", "sale")
        
    except Exception as e:
        extracted_data = {
            "raw_text": text_content,
            "error": str(e)
        }
        data_type = "sale"
    
    return NLUOutput(
        extracted_data=extracted_data,
        confidence=0.85,
        data_type=data_type
    )
