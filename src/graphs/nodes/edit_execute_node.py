"""
视频剪辑执行节点
根据解析的策略执行视频剪辑操作，使用ffmpeg作为核心引擎
支持：剪切、慢动作、特效、字幕、音频合成
"""
import os
import json
import subprocess
import tempfile
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import (
    EditExecuteInput,
    EditExecuteOutput
)


def edit_execute_node(
    state: EditExecuteInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> EditExecuteOutput:
    """
    title: 视频剪辑执行
    desc: 根据剪辑策略执行视频剪辑操作，包括剪切、慢动作、特效、字幕、音频合成等
    integrations: FFmpeg
    """
    ctx = runtime.context
    
    material_path = state.material_path
    edit_operations = state.edit_operations
    hook_config = state.hook_config
    audio_strategy = state.audio_strategy
    
    # 工作目录
    work_dir = "/tmp/edit_work"
    os.makedirs(work_dir, exist_ok=True)
    
    # 创建剪辑日志
    edit_log = []
    success_operations = []
    failed_operations = []
    
    # 输出文件路径
    output_path = os.path.join(work_dir, "edited_output.mp4")
    
    try:
        # 1. 解析剪辑操作
        operations = _parse_operations(edit_operations)
        
        # 2. 按序列执行剪辑操作
        current_input = material_path
        temp_files = []
        
        for i, op in enumerate(operations):
            op_type = op.get('operation_type', 'cut')
            op_log = f"执行操作 {i+1}: {op_type} - {op.get('content', '')}"
            edit_log.append(op_log)
            
            temp_output = os.path.join(work_dir, f"step_{i+1}.mp4")
            
            try:
                if op_type == 'cut':
                    result = _execute_cut(current_input, temp_output, op)
                elif op_type == 'slow_motion':
                    result = _execute_slow_motion(current_input, temp_output, op)
                elif op_type == 'effect':
                    result = _execute_effect(current_input, temp_output, op)
                elif op_type == 'text':
                    result = _execute_text(current_input, temp_output, op)
                elif op_type == 'audio':
                    result = _execute_audio(current_input, temp_output, op, audio_strategy)
                else:
                    result = _execute_cut(current_input, temp_output, op)
                
                if result['success']:
                    temp_files.append(temp_output)
                    current_input = temp_output
                    success_operations.append(i+1)
                    edit_log.append(f"  ✓ 操作成功")
                else:
                    failed_operations.append(i+1)
                    edit_log.append(f"  ✗ 操作失败: {result.get('error', '未知错误')}")
                    
            except Exception as e:
                failed_operations.append(i+1)
                edit_log.append(f"  ✗ 操作异常: {str(e)}")
        
        # 3. 应用钩子效果（开场3秒特殊处理）
        if hook_config and hook_config.get('opening_3_seconds'):
            hook_output = os.path.join(work_dir, "hook_applied.mp4")
            hook_result = _apply_hook(current_input, hook_output, hook_config)
            if hook_result['success']:
                current_input = hook_output
                edit_log.append("✓ 钩子效果应用成功")
            else:
                edit_log.append(f"⚠ 钩子效果应用失败: {hook_result.get('error', '')}")
        
        # 4. 最终输出
        final_output = os.path.join(work_dir, "final_output.mp4")
        shutil_copy_result = _finalize_output(current_input, final_output)
        
        if shutil_copy_result['success']:
            output_path = final_output
            edit_log.append(f"✓ 剪辑完成，输出文件: {output_path}")
        else:
            # 如果最终处理失败，使用当前输入
            output_path = current_input
            edit_log.append(f"⚠ 最终处理失败，使用中间结果")
        
        # 清理临时文件（保留最终输出）
        # _cleanup_temp_files(temp_files)
        
        return EditExecuteOutput(
            edit_success=len(failed_operations) == 0,
            output_path=output_path,
            edit_log=edit_log,
            success_count=len(success_operations),
            failed_count=len(failed_operations),
            error_message="" if len(failed_operations) == 0 else f"有 {len(failed_operations)} 个操作失败"
        )
        
    except Exception as e:
        return EditExecuteOutput(
            edit_success=False,
            output_path="",
            edit_log=edit_log,
            success_count=0,
            failed_count=len(edit_operations),
            error_message=f"剪辑执行异常: {str(e)}"
        )


def _parse_operations(edit_operations: List[Dict]) -> List[Dict]:
    """解析并排序剪辑操作"""
    if isinstance(edit_operations, str):
        try:
            edit_operations = json.loads(edit_operations)
        except:
            return []
    
    # 按序列号排序
    return sorted(edit_operations, key=lambda x: x.get('sequence', 0))


def _parse_timestamp(timestamp: str) -> tuple:
    """解析时间戳字符串，返回开始和结束时间（秒）"""
    # 格式: "00:00-00:03" 或 "00:00:00-00:00:03"
    parts = timestamp.split('-')
    if len(parts) != 2:
        return 0, 0
    
    start = _time_to_seconds(parts[0])
    end = _time_to_seconds(parts[1])
    return start, end


def _time_to_seconds(time_str: str) -> float:
    """将时间字符串转换为秒数"""
    time_str = time_str.strip()
    parts = time_str.split(':')
    
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    else:
        return float(time_str)


def _execute_cut(input_path: str, output_path: str, operation: Dict) -> Dict:
    """执行剪切操作"""
    start, end = _parse_timestamp(operation.get('source_timestamp', '0-0'))
    duration = end - start
    
    if duration <= 0:
        duration = _parse_duration(operation.get('duration', '3秒'))
    
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start),
        '-i', input_path,
        '-t', str(duration),
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-preset', 'fast',
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return {'success': True}
        else:
            return {'success': False, 'error': result.stderr[:200]}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _execute_slow_motion(input_path: str, output_path: str, operation: Dict) -> Dict:
    """执行慢动作效果"""
    # 默认0.5倍速
    speed = 0.5
    params = operation.get('parameters', {})
    if 'speed' in params:
        speed = float(params['speed'])
    
    # 计算视频滤镜
    video_filter = f"setpts={1/speed}*PTSa"
    audio_filter = f"atempo={speed}" if speed >= 0.5 else f"atempo=0.5,atempo={speed*2}"
    
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-filter_complex', f"[0:v]{video_filter}[v];[0:a]{audio_filter}[a]",
        '-map', '[v]',
        '-map', '[a]',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-preset', 'fast',
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return {'success': True}
        else:
            # 如果音频处理失败，尝试只处理视频
            cmd_simple = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-filter:v', video_filter,
                '-c:v', 'libx264',
                '-c:a', 'copy',
                '-preset', 'fast',
                output_path
            ]
            result = subprocess.run(cmd_simple, capture_output=True, text=True, timeout=300)
            return {'success': result.returncode == 0, 'error': result.stderr[:200] if result.returncode != 0 else ''}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _execute_effect(input_path: str, output_path: str, operation: Dict) -> Dict:
    """执行特效效果"""
    effects = operation.get('effects', [])
    
    # 构建滤镜链
    filters = []
    for effect in effects:
        if '震动' in effect or '震动' in str(effects):
            filters.append("crop=iw-4:ih-4:2:2,overlay=2:2")
        elif '闪烁' in effect:
            filters.append("eq=brightness=0.1")
    
    if not filters:
        # 没有特效，直接复制
        cmd = ['ffmpeg', '-y', '-i', input_path, '-c', 'copy', output_path]
    else:
        filter_str = ','.join(filters)
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', filter_str,
            '-c:v', 'libx264',
            '-c:a', 'copy',
            '-preset', 'fast',
            output_path
        ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return {'success': result.returncode == 0, 'error': result.stderr[:200] if result.returncode != 0 else ''}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _execute_text(input_path: str, output_path: str, operation: Dict) -> Dict:
    """执行字幕/文字添加"""
    content = operation.get('content', '')
    params = operation.get('parameters', {})
    
    # 使用drawtext滤镜
    text = content.replace("'", "").replace('"', '')[:50]  # 限制长度
    
    filter_str = f"drawtext=text='{text}':fontsize=24:fontcolor=white:x=(w-text_w)/2:y=h-50:box=1:boxcolor=black@0.5"
    
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-vf', filter_str,
        '-c:v', 'libx264',
        '-c:a', 'copy',
        '-preset', 'fast',
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return {'success': result.returncode == 0, 'error': result.stderr[:200] if result.returncode != 0 else ''}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _execute_audio(input_path: str, output_path: str, operation: Dict, audio_strategy: Dict) -> Dict:
    """执行音频处理"""
    # 默认保持原音频
    cmd = ['ffmpeg', '-y', '-i', input_path, '-c', 'copy', output_path]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return {'success': result.returncode == 0, 'error': result.stderr[:200] if result.returncode != 0 else ''}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _apply_hook(input_path: str, output_path: str, hook_config: Dict) -> Dict:
    """应用钩子效果（开场3秒特殊处理）"""
    opening = hook_config.get('opening_3_seconds', {})
    
    # 检查是否需要慢动作
    technique = opening.get('technique', '')
    if '慢放' in technique or '慢动作' in technique:
        # 对开场3秒应用慢动作
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-filter_complex',
            '[0:v]trim=0:3,setpts=2*PTS[v1];[0:v]trim=3,setpts=PTS[v2];[v1][v2]concat=n=2:v=1:a=0[v];'
            '[0:a]atempo=0.5[a1];[0:a]atrim=3,asetpts=PTS[a2];[a1][a2]concat=n=2:v=0:a=1[a]',
            '-map', '[v]', '-map', '[a]',
            '-c:v', 'libx264', '-c:a', 'aac',
            '-preset', 'fast',
            output_path
        ]
    else:
        # 直接复制
        cmd = ['ffmpeg', '-y', '-i', input_path, '-c', 'copy', output_path]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return {'success': result.returncode == 0, 'error': result.stderr[:200] if result.returncode != 0 else ''}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _parse_duration(duration_str: str) -> float:
    """解析时长字符串"""
    duration_str = str(duration_str).lower()
    
    # 提取数字
    import re
    match = re.search(r'(\d+(?:\.\d+)?)', duration_str)
    if match:
        return float(match.group(1))
    return 3.0


def _finalize_output(input_path: str, output_path: str) -> Dict:
    """最终输出处理"""
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-preset', 'medium',
        '-movflags', '+faststart',
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return {'success': result.returncode == 0, 'error': result.stderr[:200] if result.returncode != 0 else ''}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _cleanup_temp_files(temp_files: List[str]):
    """清理临时文件"""
    for f in temp_files:
        try:
            if os.path.exists(f):
                os.remove(f)
        except:
            pass
