"""
爆款内容分析节点
深度分析搜索到的爆款视频，提取钩子、标题模式、封面策略等爆款要素
"""
import os
import json
import logging
from typing import List, Dict, Any
from jinja2 import Template

from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from langchain_core.messages import HumanMessage, SystemMessage

from coze_coding_dev_sdk import LLMClient

from graphs.state import ViralAnalyzeInput, ViralAnalyzeOutput

# 配置日志
logger = logging.getLogger(__name__)


def viral_analyze_node(
    state: ViralAnalyzeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ViralAnalyzeOutput:
    """
    title: 爆款内容分析
    desc: 深度分析爆款视频的成功要素，提取钩子模式、标题公式、封面策略等可复制的爆款特征
    
    Process:
    1. 筛选数据表现最好的视频
    2. 分析视频钩子设计
    3. 解构标题技巧
    4. 研究封面策略
    5. 总结可复制的爆款公式
    
    integrations: 大语言模型
    """
    ctx = runtime.context
    viral_videos = state.viral_videos
    material_summary = state.material_summary
    
    logger.info(f"开始分析 {len(viral_videos)} 个爆款视频")
    
    if not viral_videos:
        logger.warning("没有可分析的爆款视频")
        return ViralAnalyzeOutput(
            viral_analysis={},
            hook_points=[],
            title_patterns=[],
            cover_patterns=[]
        )
    
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
            "config/viral_analyze_llm_cfg.json"
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
        system_prompt = "你是爆款分析专家。"
        user_prompt_template = "请分析以下爆款视频数据。"
    
    # 准备视频数据
    viral_data_str = json.dumps(viral_videos[:10], ensure_ascii=False, indent=2)
    
    # 渲染用户提示词
    user_prompt = Template(user_prompt_template).render(
        drama_type="都市情感",
        material_summary=material_summary,
        viral_videos_data=viral_data_str
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
            temperature=model_config.get("temperature", 0.5),
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
        analysis_result: Dict[str, Any] = {}
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                analysis_result = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("无法解析JSON，使用原始文本")
            analysis_result = {"raw_analysis": response_text}
        
        # 提取关键信息
        viral_formulas = analysis_result.get("viral_formulas", {})
        
        hook_points = []
        for template in viral_formulas.get("hook_templates", []):
            hook_points.append({
                "name": template.get("name", ""),
                "structure": template.get("structure", ""),
                "example": template.get("example", ""),
                "applicable_scenarios": template.get("applicable_scenarios", "")
            })
        
        title_patterns = []
        for formula in viral_formulas.get("title_formulas", []):
            title_patterns.append(formula.get("pattern", ""))
        
        cover_patterns = []
        for formula in viral_formulas.get("cover_formulas", []):
            cover_patterns.append(json.dumps(formula, ensure_ascii=False))
        
        logger.info(f"爆款分析完成，提取 {len(hook_points)} 个钩子模式")
        
        return ViralAnalyzeOutput(
            viral_analysis=analysis_result,
            hook_points=hook_points,
            title_patterns=title_patterns,
            cover_patterns=cover_patterns
        )
        
    except Exception as e:
        logger.error(f"爆款分析失败: {e}")
        return ViralAnalyzeOutput(
            viral_analysis={"error": str(e)},
            hook_points=[],
            title_patterns=[],
            cover_patterns=[]
        )
