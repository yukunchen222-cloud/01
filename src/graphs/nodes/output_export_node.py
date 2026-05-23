"""
成品输出节点
将剪辑好的视频输出到成品库，生成发布所需的元数据
"""
import os
import json
import shutil
import hashlib
from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import (
    OutputExportInput,
    OutputExportOutput
)

# 默认成品库路径
DEFAULT_OUTPUT_LIBRARY = os.path.expanduser("~/Desktop/成品库")


def output_export_node(
    state: OutputExportInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> OutputExportOutput:
    """
    title: 成品输出
    desc: 将剪辑好的视频输出到成品库，生成发布所需的元数据和审核报告
    integrations: 对象存储
    """
    ctx = runtime.context
    
    output_library = state.output_library or DEFAULT_OUTPUT_LIBRARY
    
    # 确保成品库存在
    if not os.path.exists(output_library):
        os.makedirs(output_library, exist_ok=True)
    
    # 生成输出文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"edited_{timestamp}"
    
    # 检查输入文件是否存在
    if not os.path.exists(state.output_path):
        return OutputExportOutput(
            export_success=False,
            error_message=f"剪辑输出文件不存在: {state.output_path}",
            final_output_path="",
            metadata={}
        )
    
    # 复制视频到成品库
    video_output_path = os.path.join(output_library, f"{base_filename}.mp4")
    try:
        shutil.copy(state.output_path, video_output_path)
    except Exception as e:
        return OutputExportOutput(
            export_success=False,
            error_message=f"复制文件失败: {str(e)}",
            final_output_path="",
            metadata={}
        )
    
    # 生成元数据
    metadata = _generate_metadata(
        video_path=video_output_path,
        title_suggestions=state.title_suggestions,
        cover_config=state.cover_config,
        edit_log=state.edit_log
    )
    
    # 保存元数据JSON
    metadata_path = os.path.join(output_library, f"{base_filename}_metadata.json")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    # 生成审核报告
    review_report = _generate_review_report(
        success_count=state.success_count,
        failed_count=state.failed_count,
        edit_log=state.edit_log,
        metadata=metadata
    )
    
    # 保存审核报告
    report_path = os.path.join(output_library, f"{base_filename}_review.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(review_report)
    
    return OutputExportOutput(
        export_success=True,
        error_message="",
        final_output_path=video_output_path,
        metadata_path=metadata_path,
        report_path=report_path,
        metadata=metadata
    )


def _generate_metadata(
    video_path: str,
    title_suggestions: list,
    cover_config: dict,
    edit_log: list
) -> Dict[str, Any]:
    """生成视频元数据"""
    # 计算文件哈希
    file_hash = _calculate_file_hash(video_path)
    
    # 获取文件大小
    file_size = os.path.getsize(video_path)
    
    # 获取视频时长（使用ffprobe）
    duration = _get_video_duration(video_path)
    
    # 选择最佳标题
    best_title = ""
    if title_suggestions:
        # 选择预期点击率最高的标题
        sorted_titles = sorted(
            title_suggestions,
            key=lambda x: {"高": 3, "中高": 2, "中": 1, "低": 0}.get(x.get("expected_ctr", "中"), 1),
            reverse=True
        )
        best_title = sorted_titles[0].get("title", "")
    
    metadata = {
        "video_info": {
            "filename": os.path.basename(video_path),
            "file_path": video_path,
            "file_size": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "file_hash": file_hash,
            "duration": duration,
            "duration_str": _format_duration(duration),
            "created_at": datetime.now().isoformat()
        },
        "publish_info": {
            "recommended_title": best_title,
            "title_options": title_suggestions[:3] if title_suggestions else [],
            "cover_design": cover_config,
            "recommended_tags": ["短剧", "推荐", "热门"],
            "recommended_publish_time": _get_recommended_publish_time()
        },
        "edit_info": {
            "operation_count": len(edit_log),
            "operations": edit_log[-20:] if len(edit_log) > 20 else edit_log  # 保留最近20条
        }
    }
    
    return metadata


def _generate_review_report(
    success_count: int,
    failed_count: int,
    edit_log: list,
    metadata: dict
) -> str:
    """生成审核报告"""
    total = success_count + failed_count
    success_rate = (success_count / total * 100) if total > 0 else 0
    
    report = f"""
════════════════════════════════════════════════════════════
                    剪辑审核报告
════════════════════════════════════════════════════════════

生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

一、剪辑统计
────────────────────────────────────────────────────────
• 成功操作: {success_count} 个
• 失败操作: {failed_count} 个
• 成功率: {success_rate:.1f}%
• 状态: {'✓ 通过' if failed_count == 0 else '⚠ 需要返工'}

二、视频信息
────────────────────────────────────────────────────────
• 文件名: {metadata.get('video_info', {}).get('filename', '')}
• 时长: {metadata.get('video_info', {}).get('duration_str', '')}
• 大小: {metadata.get('video_info', {}).get('file_size_mb', 0)} MB

三、发布建议
────────────────────────────────────────────────────────
• 推荐标题: {metadata.get('publish_info', {}).get('recommended_title', '')}
• 推荐发布时间: {metadata.get('publish_info', {}).get('recommended_publish_time', '')}

四、操作日志
────────────────────────────────────────────────────────
"""
    
    for log in edit_log[-10:]:
        report += f"  {log}\n"
    
    report += f"""
════════════════════════════════════════════════════════════
                    审核结论
════════════════════════════════════════════════════════════

{'✓ 视频剪辑完成，符合发布要求，可以进入成品库。' if failed_count == 0 else '⚠ 存在失败操作，建议检查后重新剪辑或手动修复。'}

"""
    
    return report


def _calculate_file_hash(file_path: str) -> str:
    """计算文件MD5哈希"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _get_video_duration(video_path: str) -> float:
    """获取视频时长（秒）"""
    import subprocess
    
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except:
        return 0.0


def _format_duration(seconds: float) -> str:
    """格式化时长"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def _get_recommended_publish_time() -> str:
    """获取推荐发布时间（基于黄金时间段）"""
    # 黄金时间段：12:00-13:00, 18:00-20:00, 21:00-23:00
    now = datetime.now()
    
    # 简单逻辑：返回下一个黄金时间段
    hour = now.hour
    
    if hour < 12:
        return "今日 12:00-13:00"
    elif hour < 18:
        return "今日 18:00-20:00"
    elif hour < 21:
        return "今日 21:00-23:00"
    else:
        return "明日 12:00-13:00"
