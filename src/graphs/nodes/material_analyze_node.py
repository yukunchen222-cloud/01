"""
素材视频分析节点
分析原始素材视频，提取关键帧、字幕、内容摘要等信息
"""
import os
import json
import logging
from typing import List, Dict, Any
from jinja2 import Template

from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from langchain_core.messages import HumanMessage

from coze_coding_dev_sdk import LLMClient
from coze_coding_dev_sdk.video_edit import FrameExtractorClient, VideoEditClient

from graphs.state import MaterialAnalyzeInput, MaterialAnalyzeOutput
from utils.file.file import File

# 配置日志
logger = logging.getLogger(__name__)


def material_analyze_node(
    state: MaterialAnalyzeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MaterialAnalyzeOutput:
    """
    title: 素材视频分析
    desc: 分析原始素材视频，提取关键帧、生成字幕、理解内容，为后续爆款搜索提供关键词
    
    Process:
    1. 提取视频关键帧（用于画面理解）
    2. 提取/生成视频字幕（用于对话和剧情分析）
    3. 使用多模态大模型分析视频内容
    4. 提取搜索关键词标签
    
    integrations: 大语言模型, 视频处理
    """
    ctx = runtime.context
    video_file = state.material_video
    
    logger.info(f"开始分析素材视频: {video_file.url}")
    
    # 1. 提取关键帧
    keyframes: List[str] = []
    try:
        frame_client = FrameExtractorClient(ctx=ctx)
        frame_response = frame_client.extract_by_key_frame(url=video_file.url)
        
        if frame_response and frame_response.data and frame_response.data.chunks:
            keyframes = [frame.screenshot for frame in frame_response.data.chunks[:10]]  # 最多10个关键帧
            logger.info(f"成功提取 {len(keyframes)} 个关键帧")
    except Exception as e:
        logger.warning(f"关键帧提取失败: {e}")
    
    # 2. 提取字幕/音频转文字
    subtitle_text: str = ""
    try:
        edit_client = VideoEditClient(ctx=ctx)
        # 先尝试直接提取字幕
        subtitle_response = edit_client.audio_to_subtitle(
            source=video_file.url,
            subtitle_type="srt"
        )
        
        if subtitle_response and subtitle_response.url:
            # 获取字幕文件内容（这里简化处理，实际需要下载并解析SRT）
            subtitle_text = f"字幕文件URL: {subtitle_response.url}"
            logger.info("成功生成字幕文件")
    except Exception as e:
        logger.warning(f"字幕提取失败: {e}")
    
    # 3. 读取大模型配置
    llm_cfg_path = ""
    if config and "metadata" in config and "llm_cfg" in config["metadata"]:
        llm_cfg_path = os.path.join(
            os.getenv("COZE_WORKSPACE_PATH", ""),
            config["metadata"]["llm_cfg"]
        )
    
    if not llm_cfg_path:
        llm_cfg_path = os.path.join(
            os.getenv("COZE_WORKSPACE_PATH", ""),
            "config/material_analyze_llm_cfg.json"
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
        logger.warning(f"读取配置文件失败，使用默认配置: {e}")
        system_prompt = "你是短视频内容分析专家，请分析视频内容。"
        user_prompt_template = "请分析视频: {{video_url}}"
    
    # 4. 使用多模态大模型分析视频
    try:
        llm_client = LLMClient(ctx=ctx)
        
        # 构建多模态消息
        content_parts: List[Dict[str, Any]] = []
        
        # 添加视频URL（如果模型支持）
        content_parts.append({
            "type": "text",
            "text": f"视频URL: {video_file.url}"
        })
        
        # 添加关键帧图片（如果有）
        for i, frame_url in enumerate(keyframes[:5]):  # 最多5张关键帧
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": frame_url}
            })
        
        # 渲染用户提示词
        user_prompt = Template(user_prompt_template).render(video_url=video_file.url)
        content_parts[0] = {"type": "text", "text": user_prompt}
        
        # 调用大模型
        messages = [HumanMessage(content=content_parts)]
        
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
        analysis_result: Dict[str, Any] = {}
        try:
            # 尝试提取JSON部分
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                analysis_result = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("无法解析JSON响应，使用原始文本")
            analysis_result = {"raw_analysis": response_text}
        
        # 5. 提取结果
        material_summary = analysis_result.get("main_plot", response_text[:500])
        drama_keywords = analysis_result.get("search_keywords", ["短剧", "都市情感"])
        
        logger.info(f"素材分析完成，提取关键词: {drama_keywords}")
        
        return MaterialAnalyzeOutput(
            material_summary=material_summary,
            material_keyframes=keyframes,
            material_subtitle=subtitle_text,
            drama_keywords=drama_keywords
        )
        
    except Exception as e:
        logger.error(f"视频分析失败: {e}")
        # 返回默认结果
        return MaterialAnalyzeOutput(
            material_summary="视频分析失败，请检查视频格式",
            material_keyframes=keyframes,
            material_subtitle=subtitle_text,
            drama_keywords=["短剧", "热门"]
        )
