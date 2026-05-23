#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
视频内容识别与分类节点
自动识别视频内容，判断短剧类型，为剪辑提供分类依据
"""

import os
import json
import re
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from langchain_core.messages import SystemMessage, HumanMessage

from utils.file.file import File, FileOps


class VideoClassifyInput(BaseModel):
    """视频分类节点输入"""
    video_path: str = Field(..., description="视频文件路径")
    video_url: str = Field(default="", description="视频URL（如果有）")


class VideoClassifyOutput(BaseModel):
    """视频分类节点输出"""
    drama_type: str = Field(..., description="识别出的短剧类型")
    drama_type_confidence: float = Field(default=0.0, description="类型置信度")
    content_summary: str = Field(default="", description="视频内容摘要")
    key_elements: List[str] = Field(default=[], description="关键元素列表")
    emotion_tone: str = Field(default="", description="情感基调")
    suggested_style: str = Field(default="", description="建议剪辑风格")
    characters: List[Dict[str, str]] = Field(default=[], description="识别出的人物")
    scenes: List[str] = Field(default=[], description="场景列表")


def video_classify_node(
    state: VideoClassifyInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> VideoClassifyOutput:
    """
    title: 视频内容识别与分类
    desc: 自动识别视频内容，分析关键帧，判断短剧类型，提取人物和场景信息
    integrations: 大语言模型, 多模态理解
    """
    # 加载模型配置
    cfg_file = os.path.join(
        os.getenv("COZE_WORKSPACE_PATH", ""),
        "config/video_classify_llm_cfg.json"
    )
    
    try:
        with open(cfg_file, 'r', encoding='utf-8') as f:
            llm_cfg = json.load(f)
    except Exception:
        llm_cfg = {"config": {"model": "doubao-seed-1-8-251228"}}
    
    print(f"🎬 正在分析视频: {state.video_path or state.video_url}")
    
    # 使用多模态模型分析视频
    from coze_coding_dev_sdk import LLMClient
    
    client = LLMClient()
    model = llm_cfg.get("config", {}).get("model", "doubao-seed-1-8-251228")
    
    # 分析提示
    analyze_prompt = """你是一个专业的短剧内容分析师。请分析这个视频片段，识别以下信息：

1. **短剧类型**：从以下类型中选择最匹配的一个
   - 都市情感：现代都市背景的爱情、职场故事
   - 古装穿越：古代背景或穿越题材
   - 悬疑推理：悬疑、破案、推理题材
   - 甜宠恋爱：甜蜜恋爱、霸道总裁等
   - 家庭伦理：家庭、亲情、婆媳关系等
   - 青春校园：学生时代、校园恋爱
   - 动作冒险：打斗、冒险、特工等

2. **内容摘要**：用1-2句话描述视频主要内容

3. **关键元素**：列出3-5个关键视觉元素

4. **情感基调**：判断整体情感基调

5. **建议剪辑风格**：根据内容推荐剪辑风格

请以JSON格式返回结果：
{
    "drama_type": "类型名称",
    "confidence": 0.85,
    "content_summary": "内容摘要",
    "key_elements": ["元素1", "元素2"],
    "emotion_tone": "情感基调",
    "suggested_style": "剪辑风格建议"
}"""

    try:
        # 获取视频输入
        video_input = state.video_url if state.video_url else state.video_path
        
        # 构建消息
        messages = [
            SystemMessage(content="你是一个专业的短剧内容分析师，擅长通过视频画面识别短剧类型、情感基调和关键元素。"),
            HumanMessage(content=[
                {"type": "text", "text": analyze_prompt},
                {"type": "video_url", "video_url": {"url": video_input}}
            ])
        ]
        
        # 调用模型
        response = client.invoke(
            messages=messages,
            model=model,
            temperature=0.3
        )
        
        # 解析结果
        result_text = ""
        if isinstance(response.content, str):
            result_text = response.content
        elif isinstance(response.content, list):
            for item in response.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    result_text += item.get("text", "")
                elif isinstance(item, str):
                    result_text += item
        
        # 提取JSON
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            result = json.loads(json_match.group())
        else:
            # 使用默认值
            result = {
                "drama_type": "都市情感",
                "confidence": 0.5,
                "content_summary": result_text[:200] if result_text else "无法识别",
                "key_elements": [],
                "emotion_tone": "未知",
                "suggested_style": "标准剪辑"
            }
        
        print(f"✅ 视频分类完成: {result.get('drama_type', '未知')}")
        
        return VideoClassifyOutput(
            drama_type=result.get("drama_type", "都市情感"),
            drama_type_confidence=result.get("confidence", 0.5),
            content_summary=result.get("content_summary", ""),
            key_elements=result.get("key_elements", []),
            emotion_tone=result.get("emotion_tone", ""),
            suggested_style=result.get("suggested_style", "")
        )
        
    except Exception as e:
        print(f"⚠️ 视频分析出错: {e}")
        # 返回默认分类
        return VideoClassifyOutput(
            drama_type="都市情感",
            drama_type_confidence=0.5,
            content_summary=f"分析失败: {str(e)}",
            key_elements=[],
            emotion_tone="未知",
            suggested_style="标准剪辑"
        )
