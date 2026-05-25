"""
ASR语音识别节点
将语音转换为文字
"""
import os
import logging
from typing import Tuple
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import ASRClient
from graphs.state import ASRInput, ASROutput
from utils.run_sync import run_sync

logger = logging.getLogger(__name__)


async def asr_recognition_node(
    state: ASRInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ASROutput:
    """
    title: 语音识别
    desc: 使用ASR将语音转换为文字，支持多种音频格式。如果已有识别文本则直接透传
    
    integrations: audio
    """
    ctx = runtime.context
    
    audio_file = state.audio_file
    input_type = state.input_type
    
    # 如果不是语音模式，直接返回空结果
    if input_type != "voice":
        return ASROutput(
            recognized_text="",
            confidence=0.0,
            input_type=input_type
        )
    
    # 如果没有音频文件（外部已完成ASR），透传已有的识别文本
    if audio_file is None or not audio_file.url:
        existing_text = state.recognized_text
        if existing_text:
            logger.info(f"透传外部ASR识别结果: {existing_text[:50]}...")
            return ASROutput(
                recognized_text=existing_text,
                confidence=0.9,
                input_type=input_type
            )
        return ASROutput(
            recognized_text="",
            confidence=0.0,
            input_type=input_type
        )
    
    # 获取音频URL
    audio_url: str = audio_file.url
    
    # 初始化ASR客户端
    asr_client = ASRClient(ctx=ctx)
    
    # 调用ASR识别
    recognized_text: str = ""
    
    try:
        text, data = await run_sync(
            asr_client.recognize,
            uid="accounting_assistant",
            url=audio_url
        )
        recognized_text = text
        
    except Exception as e:
        raise RuntimeError(f"语音识别失败: {str(e)}")
    
    return ASROutput(
        recognized_text=recognized_text,
        confidence=0.9,
        input_type=input_type
    )
