"""
剪辑策略解析节点
解析爆款Agent生成的剪辑策略JSON，转换为可执行的剪辑操作序列
"""
import os
import json
import re
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import (
    StrategyParseInput,
    StrategyParseOutput
)


class EditOperation(BaseModel):
    """单个剪辑操作"""
    sequence: int = Field(..., description="操作序号")
    operation_type: str = Field(..., description="操作类型: cut/slow_motion/effect/text/audio")
    source_timestamp: str = Field(..., description="源视频时间戳")
    duration: str = Field(..., description="持续时间")
    content: str = Field(..., description="操作内容描述")
    effects: List[str] = Field(default=[], description="特效列表")
    parameters: Dict[str, Any] = Field(default={}, description="操作参数")


class HookConfig(BaseModel):
    """钩子配置"""
    hook_type: str = Field(..., description="钩子类型")
    opening_3_seconds: Dict[str, Any] = Field(..., description="开场3秒配置")
    strength: int = Field(default=8, description="钩子强度1-10")


class TitleConfig(BaseModel):
    """标题配置"""
    title: str = Field(..., description="推荐标题")
    pattern: str = Field(..., description="标题模式")
    expected_ctr: str = Field(default="中", description="预期点击率")


class CoverConfig(BaseModel):
    """封面配置"""
    main_visual: str = Field(..., description="主视觉描述")
    text_overlay: str = Field(..., description="文字叠加")
    color_scheme: str = Field(..., description="配色方案")


def strategy_parse_node(
    state: StrategyParseInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> StrategyParseOutput:
    """
    title: 剪辑策略解析
    desc: 解析爆款Agent生成的剪辑策略JSON，提取可执行的剪辑操作序列、钩子配置、标题和封面设计
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    # 读取模型配置
    cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects"), config.get("metadata", {}).get("llm_cfg", "config/strategy_parse_llm_cfg.json"))
    
    raw_strategy = state.raw_strategy
    
    # 尝试解析JSON策略
    try:
        # 清理可能的markdown代码块标记
        if "```json" in raw_strategy:
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', raw_strategy)
            if json_match:
                raw_strategy = json_match.group(1)
        elif "```" in raw_strategy:
            json_match = re.search(r'```\s*([\s\S]*?)\s*```', raw_strategy)
            if json_match:
                raw_strategy = json_match.group(1)
        
        strategy_data = json.loads(raw_strategy)
    except json.JSONDecodeError:
        # 如果JSON解析失败，使用大模型解析
        strategy_data = _parse_with_llm(raw_strategy, cfg_file, ctx)
    
    # 提取剪辑操作序列
    edit_operations = []
    edit_points = strategy_data.get("edit_points", [])
    for point in edit_points:
        operation = EditOperation(
            sequence=point.get("sequence", 0),
            operation_type=_determine_operation_type(point),
            source_timestamp=point.get("source_timestamp", ""),
            duration=point.get("duration", ""),
            content=point.get("content", ""),
            effects=point.get("suggested_effects", []),
            parameters={
                "edit_reason": point.get("edit_reason", ""),
            }
        )
        edit_operations.append(operation)
    
    # 提取钩子配置
    hook_data = strategy_data.get("hook_strategy", {})
    hook_config = HookConfig(
        hook_type=hook_data.get("type", "悬念式"),
        opening_3_seconds=hook_data.get("opening_3_seconds", {}),
        strength=hook_data.get("hook_strength", 8)
    )
    
    # 提取标题建议
    title_suggestions = []
    for title_data in strategy_data.get("title_suggestions", [])[:3]:  # 取前3个
        title_suggestions.append(TitleConfig(
            title=title_data.get("title", ""),
            pattern=title_data.get("pattern_used", ""),
            expected_ctr=title_data.get("expected_ctr", "中")
        ))
    
    # 提取封面配置
    cover_data = strategy_data.get("cover_design", {})
    cover_config = CoverConfig(
        main_visual=cover_data.get("main_visual", ""),
        text_overlay=cover_data.get("text_overlay", ""),
        color_scheme=cover_data.get("color_scheme", "")
    )
    
    # 提取音频策略
    audio_strategy = strategy_data.get("audio_strategy", {})
    
    # 提取整体策略
    overall_strategy = strategy_data.get("overall_strategy", {})
    
    return StrategyParseOutput(
        edit_operations=[op.model_dump() for op in edit_operations],
        hook_config=hook_config.model_dump(),
        title_suggestions=[t.model_dump() for t in title_suggestions],
        cover_config=cover_config.model_dump(),
        audio_strategy=audio_strategy,
        overall_strategy=overall_strategy,
        parse_success=True,
        error_message=""
    )


def _determine_operation_type(point: Dict[str, Any]) -> str:
    """根据剪辑点内容判断操作类型"""
    effects = point.get("suggested_effects", [])
    content = point.get("content", "").lower()
    
    if "慢动作" in str(effects) or "慢放" in content:
        return "slow_motion"
    elif "音效" in str(effects) or "bgm" in content.lower():
        return "audio"
    elif "文字" in content or "字幕" in content:
        return "text"
    elif "特效" in str(effects):
        return "effect"
    else:
        return "cut"


def _parse_with_llm(raw_strategy: str, cfg_file: str, ctx: Any) -> Dict[str, Any]:
    """使用大模型解析非标准格式的策略文本"""
    from coze_coding_dev_sdk import LLMClient
    from langchain_core.messages import HumanMessage, SystemMessage
    
    # 构建提示词
    prompt = f"""请将以下剪辑策略文本解析为标准的JSON格式，必须包含以下字段：
- overall_strategy: 整体策略
- hook_strategy: 钩子策略
- edit_points: 剪辑点列表
- title_suggestions: 标题建议
- cover_design: 封面设计
- audio_strategy: 音频策略

原始策略文本：
{raw_strategy}

请直接输出JSON，不要包含其他内容。"""

    # 调用大模型
    try:
        client = LLMClient()
        
        # 读取配置获取模型ID
        with open(cfg_file, 'r') as f:
            llm_cfg = json.load(f)
        
        model_id = llm_cfg.get("config", {}).get("model", "deepseek-v3-2-251201")
        
        messages = [
            SystemMessage(content="你是专业的视频剪辑策略解析专家，负责将文本解析为结构化JSON。"),
            HumanMessage(content=prompt)
        ]
        
        response = client.invoke(messages=messages, model=model_id)
        
        result_text = response.content if hasattr(response, 'content') else str(response)
        
        # 如果content是list，转换为字符串
        if isinstance(result_text, list):
            result_text = " ".join([item.get("text", str(item)) if isinstance(item, dict) else str(item) for item in result_text])
        
        # 清理并解析JSON
        if "```json" in result_text:
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', result_text)
            if json_match:
                result_text = json_match.group(1)
        
        return json.loads(result_text)
    except Exception as e:
        # 返回默认结构
        return {
            "overall_strategy": {},
            "hook_strategy": {},
            "edit_points": [],
            "title_suggestions": [],
            "cover_design": {},
            "audio_strategy": {}
        }
