"""
ASR语音识别节点
将语音转换为文字
"""
import os
from typing import Tuple
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import ASRClient
from graphs.state import ASRInput, ASROutput


def asr_recognition_node(
    state: ASRInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ASROutput:
    """
    title: 语音识别
    desc: 使用ASR将语音转换为文字，支持多种音频格式
    
    integrations: audio
    """
    ctx = runtime.context
    
    audio_file = state.audio_file
    
    # 如果是查询模式而不是语音录入，直接返回空结果
    if state.input_type != "voice" or audio_file is None:
        return ASROutput(
            recognized_text="",
            confidence=0.0
        )
    
    # 获取音频URL
    audio_url: str = ""
    if audio_file.url:
        audio_url = audio_file.url
    else:
        raise ValueError("语音文件URL不能为空")
    
    # 初始化ASR客户端
    asr_client = ASRClient(ctx=ctx)
    
    # 调用ASR识别
    recognized_text: str = ""
    
    try:
        text, data = asr_client.recognize(
            uid="accounting_assistant",
            url=audio_url
        )
        recognized_text = text
        
    except Exception as e:
        raise RuntimeError(f"语音识别失败: {str(e)}")
    
    return ASROutput(
        recognized_text=recognized_text,
        confidence=0.9
    )
