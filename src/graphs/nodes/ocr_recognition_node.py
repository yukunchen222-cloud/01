"""
OCR图片识别节点
识别图片中的账目信息
"""
import os
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient
from graphs.state import OCRInput, OCROutput
from utils.file.file import File


def ocr_recognition_node(
    state: OCRInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> OCROutput:
    """
    title: 图片识别
    desc: 使用多模态大模型识别图片中的文字和账目信息
    
    integrations: llm
    """
    ctx = runtime.context
    
    image_file = state.image_file
    
    # 如果是查询模式而不是图片录入，直接返回空结果
    input_type = state.input_type
    if input_type != "image" or image_file is None:
        return OCROutput(
            ocr_text="",
            confidence=0.0,
            input_type=input_type
        )
    
    # 获取图片URL
    image_url: str = ""
    if image_file.url:
        image_url = image_file.url
    else:
        raise ValueError("图片文件URL不能为空")
    
    # 初始化多模态LLM客户端
    llm_client = LLMClient(ctx=ctx)
    
    # 使用多模态模型识别图片
    prompt = """请识别这张图片中的所有文字内容，特别关注以下账目相关信息：
1. 商品名称和数量
2. 价格和金额
3. 日期
4. 交易类型（销售/进货/支出）

请直接输出识别的文字，按原始格式排列。"""
    
    ocr_text: str = ""
    
    try:
        # 调用多模态模型 - 使用 invoke 方法和正确的消息格式
        messages = [
            SystemMessage(content="你是一个专业的OCR识别助手，擅长识别各类票据和账单。"),
            HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ])
        ]
        
        response = llm_client.invoke(
            messages=messages,
            model="doubao-seed-2-0-lite-260215"
        )
        
        # 安全地提取文本内容
        if isinstance(response.content, str):
            ocr_text = response.content
        elif isinstance(response.content, list):
            # 从多模态响应中提取文本
            text_parts = []
            for item in response.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            ocr_text = " ".join(text_parts)
        else:
            ocr_text = str(response.content)
        
    except Exception as e:
        raise RuntimeError(f"图片识别失败: {str(e)}")
    
    return OCROutput(
        ocr_text=ocr_text,
        confidence=0.85,
        input_type=input_type
    )
