"""
素材加载节点
从素材库文件夹加载视频文件，准备剪辑
"""
import os
import shutil
import subprocess
from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import (
    MaterialLoadInput,
    MaterialLoadOutput
)

# 默认素材库路径
DEFAULT_MATERIAL_LIBRARY = os.path.expanduser("~/Desktop/素材库")


def material_load_node(
    state: MaterialLoadInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MaterialLoadOutput:
    """
    title: 素材加载
    desc: 从素材库加载视频文件，支持指定文件名或自动选择最新素材
    integrations: 无
    """
    ctx = runtime.context
    
    material_library = state.material_library or DEFAULT_MATERIAL_LIBRARY
    
    # 确保素材库存在
    if not os.path.exists(material_library):
        os.makedirs(material_library, exist_ok=True)
    
    # 获取素材文件
    if state.material_filename:
        # 指定了具体文件名
        material_path = os.path.join(material_library, state.material_filename)
        if not os.path.exists(material_path):
            return MaterialLoadOutput(
                load_success=False,
                error_message=f"指定的素材文件不存在: {state.material_filename}",
                material_path="",
                material_info={}
            )
    else:
        # 自动选择最新的素材文件
        material_path = _get_latest_material(material_library)
        if not material_path:
            return MaterialLoadOutput(
                load_success=False,
                error_message="素材库中没有找到视频文件，请先添加素材",
                material_path="",
                material_info={}
            )
    
    # 获取视频信息
    material_info = _get_video_info(material_path)
    
    # 复制到工作目录
    work_dir = "/tmp/edit_work"
    os.makedirs(work_dir, exist_ok=True)
    
    work_material_path = os.path.join(work_dir, os.path.basename(material_path))
    shutil.copy(material_path, work_material_path)
    
    return MaterialLoadOutput(
        load_success=True,
        error_message="",
        material_path=work_material_path,
        original_material_path=material_path,
        material_info=material_info
    )


def _get_latest_material(material_library: str) -> Optional[str]:
    """获取素材库中最新的视频文件"""
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv']
    
    video_files = []
    for f in os.listdir(material_library):
        ext = os.path.splitext(f)[1].lower()
        if ext in video_extensions:
            full_path = os.path.join(material_library, f)
            video_files.append((full_path, os.path.getmtime(full_path)))
    
    if not video_files:
        return None
    
    # 按修改时间排序，返回最新的
    video_files.sort(key=lambda x: x[1], reverse=True)
    return video_files[0][0]


def _get_video_info(video_path: str) -> dict:
    """使用ffprobe获取视频信息"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        import json
        info = json.loads(result.stdout)
        
        # 提取关键信息
        format_info = info.get('format', {})
        video_stream = None
        audio_stream = None
        
        for stream in info.get('streams', []):
            if stream.get('codec_type') == 'video' and not video_stream:
                video_stream = stream
            elif stream.get('codec_type') == 'audio' and not audio_stream:
                audio_stream = stream
        
        return {
            'duration': float(format_info.get('duration', 0)),
            'size': int(format_info.get('size', 0)),
            'format': format_info.get('format_name', ''),
            'width': video_stream.get('width', 0) if video_stream else 0,
            'height': video_stream.get('height', 0) if video_stream else 0,
            'fps': eval(video_stream.get('r_frame_rate', '0/1')) if video_stream else 0,
            'video_codec': video_stream.get('codec_name', '') if video_stream else '',
            'audio_codec': audio_stream.get('codec_name', '') if audio_stream else '',
            'has_audio': audio_stream is not None
        }
    except Exception as e:
        return {
            'error': str(e),
            'duration': 0
        }
