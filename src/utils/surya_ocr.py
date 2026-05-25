"""
Surya OCR 工具模块 - 专业表格识别
GitHub: https://github.com/datalab-to/surya

Surya 是一个专门的 OCR 工具，擅长：
- 文档 OCR（支持 90+ 语言）
- 表格识别和结构化
- 布局分析
- PDF/图片处理
"""

import os
import logging
import tempfile
import asyncio
from typing import List, Dict, Any, Optional
from io import BytesIO

logger = logging.getLogger(__name__)

# 设置 Surya 日志级别
os.environ.setdefault("SURYA_LOG_LEVEL", "ERROR")


def _download_image(url: str) -> bytes:
    """下载图片"""
    import requests
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


def _surya_ocr_sync(image_input, languages: List[str] = None) -> List[Dict]:
    """
    同步执行 Surya OCR
    
    Args:
        image_input: 图片路径或 PIL Image 或 bytes
        languages: 语言列表，如 ['zh', 'en']
    
    Returns:
        识别结果列表
    """
    from PIL import Image
    from surya.ocr import run_ocr
    from surya.model.detection.model import load_model as load_det_model
    from surya.model.detection.processor import load_processor as load_det_processor
    from surya.model.recognition.model import load_model as load_rec_model
    from surya.model.recognition.processor import load_processor as load_rec_processor
    from surya.settings import settings
    
    # 默认中英文
    if not languages:
        languages = ["zh", "en"]
    
    # 加载模型（首次会下载，后续使用缓存）
    det_processor = load_det_processor()
    det_model = load_det_model()
    rec_processor = load_rec_processor()
    rec_model = load_rec_model()
    
    # 处理输入
    if isinstance(image_input, str):
        # URL 或文件路径
        if image_input.startswith("http"):
            image_bytes = _download_image(image_input)
            image = Image.open(BytesIO(image_bytes))
        else:
            image = Image.open(image_input)
    elif isinstance(image_input, bytes):
        image = Image.open(BytesIO(image_input))
    elif isinstance(image_input, Image.Image):
        image = image_input
    else:
        raise ValueError(f"不支持的输入类型: {type(image_input)}")
    
    # 执行 OCR
    results = run_ocr(
        [image],
        [languages],
        det_model,
        det_processor,
        rec_model,
        rec_processor,
    )
    
    return results


def _surya_table_detect_sync(image_input) -> Dict[str, Any]:
    """
    同步执行 Surya 表格检测
    
    Returns:
        包含表格边界框和单元格信息的字典
    """
    from PIL import Image
    from surya.table_rec import run_table_recognition
    from surya.model.table_rec.model import load_model as load_table_model
    from surya.model.table_rec.processor import load_processor as load_table_processor
    from surya.model.detection.model import load_model as load_det_model
    from surya.model.detection.processor import load_processor as load_det_processor
    
    # 加载模型
    det_processor = load_det_processor()
    det_model = load_det_model()
    table_processor = load_table_processor()
    table_model = load_table_model()
    
    # 处理输入
    if isinstance(image_input, str):
        if image_input.startswith("http"):
            image_bytes = _download_image(image_input)
            image = Image.open(BytesIO(image_bytes))
        else:
            image = Image.open(image_input)
    elif isinstance(image_input, bytes):
        image = Image.open(BytesIO(image_input))
    elif isinstance(image_input, Image.Image):
        image = image_input
    else:
        raise ValueError(f"不支持的输入类型: {type(image_input)}")
    
    # 执行表格识别
    results = run_table_recognition(
        [image],
        det_model,
        det_processor,
        table_model,
        table_processor,
    )
    
    return results


def surya_ocr_image(image_input, languages: List[str] = None) -> Dict[str, Any]:
    """
    对图片执行 OCR，返回结构化文本
    
    Args:
        image_input: 图片URL、文件路径、bytes或PIL Image
        languages: 语言列表
    
    Returns:
        {
            "text": "完整文本",
            "lines": [{"text": "行文本", "bbox": [x1,y1,x2,y2]}, ...],
            "success": True
        }
    """
    try:
        results = _surya_ocr_sync(image_input, languages)
        
        lines = []
        full_text_parts = []
        
        for page_result in results:
            if hasattr(page_result, 'text_lines'):
                for line in page_result.text_lines:
                    line_text = line.text if hasattr(line, 'text') else str(line)
                    bbox = line.bbox if hasattr(line, 'bbox') else [0,0,0,0]
                    lines.append({
                        "text": line_text,
                        "bbox": list(bbox) if bbox else [0,0,0,0]
                    })
                    full_text_parts.append(line_text)
            elif isinstance(page_result, dict):
                # 字典格式
                for line in page_result.get('text_lines', []):
                    line_text = line.get('text', '') if isinstance(line, dict) else str(line)
                    bbox = line.get('bbox', [0,0,0,0]) if isinstance(line, dict) else [0,0,0,0]
                    lines.append({"text": line_text, "bbox": bbox})
                    full_text_parts.append(line_text)
        
        return {
            "success": True,
            "text": "\n".join(full_text_parts),
            "lines": lines
        }
        
    except Exception as e:
        logger.error(f"Surya OCR 失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "text": "",
            "lines": []
        }


def surya_table_to_markdown(image_input) -> Dict[str, Any]:
    """
    识别图片中的表格并转换为 Markdown 格式
    
    Args:
        image_input: 图片URL、文件路径、bytes或PIL Image
    
    Returns:
        {
            "success": True,
            "markdown": "| 列1 | 列2 | ...",
            "tables": [{"rows": 5, "cols": 4, "cells": [...]}, ...]
        }
    """
    try:
        from PIL import Image
        
        # 先执行 OCR 获取文本
        ocr_result = surya_ocr_image(image_input)
        if not ocr_result["success"]:
            return ocr_result
        
        lines = ocr_result["lines"]
        if not lines:
            return {
                "success": False,
                "error": "未识别到文本",
                "markdown": ""
            }
        
        # 将文本行转换为 Markdown 表格格式
        # 假设每行是一个表格行，用空格或制表符分隔
        markdown_lines = []
        for i, line in enumerate(lines):
            text = line["text"].strip()
            if not text:
                continue
            
            # 尝试按空白分割
            cells = text.split()
            if len(cells) >= 2:
                # 可能是表格行
                row = "| " + " | ".join(cells) + " |"
                markdown_lines.append(row)
                
                # 第一行后添加分隔符
                if i == 0:
                    separator = "| " + " | ".join(["---"] * len(cells)) + " |"
                    markdown_lines.append(separator)
        
        return {
            "success": True,
            "markdown": "\n".join(markdown_lines),
            "text": ocr_result["text"],
            "line_count": len(markdown_lines)
        }
        
    except Exception as e:
        logger.error(f"Surya 表格识别失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "markdown": ""
        }


async def surya_ocr_async(image_input, languages: List[str] = None) -> Dict[str, Any]:
    """异步执行 OCR"""
    from utils.run_sync import run_sync
    return await run_sync(surya_ocr_image, image_input, languages)


async def surya_table_async(image_input) -> Dict[str, Any]:
    """异步执行表格识别"""
    from utils.run_sync import run_sync
    return await run_sync(surya_table_to_markdown, image_input)


# 导出
__all__ = [
    "surya_ocr_image",
    "surya_table_to_markdown",
    "surya_ocr_async",
    "surya_table_async",
]
