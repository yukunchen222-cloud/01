"""
OCR图片/PDF识别节点
识别图片或PDF文档中的账目信息
"""
import os
from typing import Optional
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient
from graphs.state import OCRInput, OCROutput
from utils.file.file import File, FileOps


def ocr_recognition_node(
    state: OCRInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> OCROutput:
    """
    title: 文件识别
    desc: 识别图片或PDF文档中的文字和账目信息，支持JPG/PNG/PDF等格式
    
    integrations: llm
    """
    ctx = runtime.context
    
    image_file = state.image_file
    
    # 如果是查询模式而不是图片录入，保留已有的ocr_text
    input_type = state.input_type
    if input_type != "image" or image_file is None:
        # 如果外部已传入ocr_text，保留它
        if state.ocr_text:
            return OCROutput(
                ocr_text=state.ocr_text,
                confidence=0.9,
                input_type=input_type
            )
        return OCROutput(
            ocr_text="",
            confidence=0.0,
            input_type=input_type
        )
    
    # 获取文件URL
    file_url: str = ""
    if image_file.url:
        file_url = image_file.url
    else:
        raise ValueError("文件URL不能为空")
    
    # 判断文件类型：PDF走文本提取，图片走多模态识别
    is_pdf: bool = file_url.lower().endswith(".pdf") or (
        hasattr(image_file, 'file_type') and image_file.file_type == 'document'
    )
    
    ocr_text: str = ""
    confidence: float = 0.85
    
    if is_pdf:
        # PDF文件：使用FileOps提取文本（同步调用，LangGraph def节点在线程池运行）
        ocr_text = _extract_pdf_text(image_file)
        confidence = 0.90
    else:
        # 图片文件：使用多模态LLM识别
        ocr_text = _recognize_image(ctx, file_url)
    
    return OCROutput(
        ocr_text=ocr_text,
        confidence=confidence,
        input_type=input_type
    )


def _extract_pdf_text(file_obj: File) -> str:
    """从PDF文件中提取文本内容"""
    try:
        extracted_text: str = FileOps.extract_text(file_obj)
        
        if not extracted_text or extracted_text.startswith("[FileOps Error]") or extracted_text.startswith("[解析"):
            raise RuntimeError(f"PDF文本提取失败: {extracted_text}")
        
        # 如果提取的文本太短，可能PDF是扫描件，尝试用多模态模型
        if len(extracted_text.strip()) < 20:
            return f"[PDF提取文本较少，可能为扫描件] {extracted_text}"
        
        return extracted_text
        
    except Exception as e:
        raise RuntimeError(f"PDF文件处理失败: {str(e)}")


def _recognize_image(ctx: Context, image_url: str) -> str:
    """使用多模态LLM识别图片中的文字"""
    llm_client = LLMClient(ctx=ctx)
    
    prompt: str = """请识别这张图片中的所有文字内容，特别关注以下账目相关信息：
1. 商品名称和数量
2. 价格和金额
3. 日期
4. 交易类型（销售/进货/支出）

请直接输出识别的文字，按原始格式排列。"""
    
    try:
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
        result_text: str = ""
        if isinstance(response.content, str):
            result_text = response.content
        elif isinstance(response.content, list):
            text_parts: list = []
            for item in response.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            result_text = " ".join(text_parts)
        else:
            result_text = str(response.content)
        
        return result_text
        
    except Exception as e:
        raise RuntimeError(f"图片识别失败: {str(e)}")
