"""
审核比对节点
审核剪辑成品，与爆款标准对比，评估爆款潜力
"""
import os
import json
import logging
from typing import Dict, Any, List
from jinja2 import Template

from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from langchain_core.messages import HumanMessage, SystemMessage

from coze_coding_dev_sdk import LLMClient

from graphs.state import ReviewCompareInput, ReviewCompareOutput
from utils.file.file import File

# 配置日志
logger = logging.getLogger(__name__)


def review_compare_node(
    state: ReviewCompareInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ReviewCompareOutput:
    """
    title: 审核比对
    desc: 审核剪辑成品，与爆款标准进行对比，给出通过/返工的决定和改进建议
    
    Process:
    1. 分析剪辑成品的钩子执行情况
    2. 评估剪辑节奏和内容完整性
    3. 对比爆款特征，计算相似度得分
    4. 识别问题并给出改进建议
    5. 做出通过/不通过决策
    
    integrations: 大语言模型
    """
    ctx = runtime.context
    edited_video = state.edited_video
    viral_analysis = state.viral_analysis
    edit_strategy = state.edit_strategy
    revision_count = state.revision_count
    
    logger.info(f"开始审核剪辑成品，返工次数: {revision_count}")
    
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
            "config/review_llm_cfg.json"
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
        system_prompt = "你是质量审核专家。"
        user_prompt_template = "请审核以下剪辑成品。"
    
    # 准备编辑视频信息
    edited_video_info = ""
    if edited_video:
        edited_video_info = f"视频URL: {edited_video.url}"
    
    # 渲染用户提示词
    user_prompt = Template(user_prompt_template).render(
        edited_video_info=edited_video_info,
        edit_strategy=json.dumps(edit_strategy, ensure_ascii=False, indent=2),
        viral_analysis=json.dumps(viral_analysis, ensure_ascii=False, indent=2),
        revision_count=str(revision_count)
    )
    
    try:
        llm_client = LLMClient(ctx=ctx)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = llm_client.invoke(
            messages=messages,
            model=model_config.get("model", "doubao-seed-1-8-251228"),
            temperature=model_config.get("temperature", 0.3),
            max_completion_tokens=model_config.get("max_completion_tokens", 4096)
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
        review_result: Dict[str, Any] = {}
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                review_result = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("无法解析JSON，使用原始文本")
            review_result = {"raw_review": response_text}
        
        # 提取审核结果
        overall_result = review_result.get("overall_result", {})
        passed = overall_result.get("passed", False)
        total_score = float(overall_result.get("total_score", 0))
        
        # 提取改进建议
        improvement_suggestions: List[str] = []
        for suggestion in review_result.get("improvement_suggestions", []):
            if isinstance(suggestion, dict):
                improvement_suggestions.append(suggestion.get("suggestion", ""))
            elif isinstance(suggestion, str):
                improvement_suggestions.append(suggestion)
        
        logger.info(f"审核完成，通过: {passed}, 得分: {total_score}")
        
        return ReviewCompareOutput(
            review_passed=passed,
            review_result=review_result,
            improvement_suggestions=improvement_suggestions,
            score=total_score
        )
        
    except Exception as e:
        logger.error(f"审核失败: {e}")
        return ReviewCompareOutput(
            review_passed=False,
            review_result={"error": str(e)},
            improvement_suggestions=[f"审核过程出错: {e}"],
            score=0.0
        )
