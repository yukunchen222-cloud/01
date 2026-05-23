"""
剪辑策略生成节点
基于素材分析和爆款研究，生成详细的剪辑策略文档
"""
import os
import json
import logging
from typing import Dict, Any
from jinja2 import Template

from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from langchain_core.messages import HumanMessage, SystemMessage

from coze_coding_dev_sdk import LLMClient

from graphs.state import EditStrategyInput, EditStrategyOutput

# 配置日志
logger = logging.getLogger(__name__)


def edit_strategy_node(
    state: EditStrategyInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> EditStrategyOutput:
    """
    title: 剪辑策略生成
    desc: 基于素材分析和爆款研究，生成详细的剪辑策略文档，包含钩子设计、剪辑点、标题封面建议等
    
    Process:
    1. 分析素材与爆款的匹配度
    2. 选择最适合的钩子类型
    3. 规划剪辑节奏和镜头选择
    4. 生成标题和封面建议
    5. 制定音频策略
    
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    logger.info("开始生成剪辑策略")
    
    # 读取大模型配置
    llm_cfg_path = ""
    if config and "metadata" in config and "llm_cfg" in config["metadata"]:
        llm_cfg_path = os.path.join(
            os.getenv("COZE_WORKSPACE_PATH", ""),
            config["metadata"]["llm_cfg"]
        )
    
    if not llm_cfg_path:
        llm_cfg_path = os.path.join(
            os.getenv("COZE_WORKSPACE_PATH", ""),
            "config/edit_strategy_llm_cfg.json"
        )
    
    system_prompt = ""
    user_prompt_template = ""
    model_config: Dict[str, Any] = {}
    
    try:
        with open(llm_cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            system_prompt = cfg.get("sp", "")
            user_prompt_template = cfg.get("up", "")
            model_config = cfg.get("config", {})
    except Exception as e:
        logger.warning(f"读取配置文件失败: {e}")
        system_prompt = "你是剪辑策略专家。"
        user_prompt_template = "请基于以下信息生成剪辑策略。"
    
    # 渲染用户提示词
    user_prompt = Template(user_prompt_template).render(
        material_summary=state.material_summary,
        viral_analysis=json.dumps(state.viral_analysis, ensure_ascii=False, indent=2),
        hook_points=json.dumps(state.hook_points, ensure_ascii=False, indent=2),
        title_patterns=json.dumps(state.title_patterns, ensure_ascii=False, indent=2),
        cover_patterns=json.dumps(state.cover_patterns, ensure_ascii=False, indent=2)
    )
    
    try:
        llm_client = LLMClient(ctx=ctx)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = llm_client.invoke(
            messages=messages,
            model=model_config.get("model", "deepseek-v3-2-251201"),
            temperature=model_config.get("temperature", 0.6),
            max_completion_tokens=model_config.get("max_completion_tokens", 8192),
            thinking=model_config.get("thinking", "enabled")
        )
        
        # 解析响应
        response_text = ""
        if isinstance(response.content, str):
            response_text = response.content
        elif isinstance(response.content, list):
            text_parts = [
                item.get("text", "")
                for item in response.content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            response_text = " ".join(text_parts)
        
        # 尝试解析JSON
        strategy_result: Dict[str, Any] = {}
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                strategy_result = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("无法解析JSON，使用原始文本")
            strategy_result = {"raw_strategy": response_text}
        
        # 提取关键信息
        hook_strategy = strategy_result.get("hook_strategy", [])
        if isinstance(hook_strategy, dict):
            hook_strategy = [hook_strategy]
        
        cut_points = strategy_result.get("edit_points", [])
        
        title_suggestions = strategy_result.get("title_suggestions", [])
        suggested_title = ""
        if title_suggestions and isinstance(title_suggestions, list) and len(title_suggestions) > 0:
            suggested_title = title_suggestions[0].get("title", "")
        
        cover_design = strategy_result.get("cover_design", {})
        suggested_cover_desc = json.dumps(cover_design, ensure_ascii=False) if cover_design else ""
        
        logger.info("剪辑策略生成完成")
        
        return EditStrategyOutput(
            edit_strategy=strategy_result,
            hook_strategy=hook_strategy,
            cut_points=cut_points,
            suggested_title=suggested_title,
            suggested_cover_desc=suggested_cover_desc
        )
        
    except Exception as e:
        logger.error(f"策略生成失败: {e}")
        return EditStrategyOutput(
            edit_strategy={"error": str(e)},
            hook_strategy=[],
            cut_points=[],
            suggested_title="",
            suggested_cover_desc=""
        )
