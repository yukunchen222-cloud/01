"""
视频剪辑执行节点
支持两种剪辑引擎：
1. 剪映桌面版自动化（优先）- 真正连接剪映进行剪辑
2. FFmpeg命令行（备用）- 直接处理视频文件
"""

import os
import json
import subprocess
import tempfile
import shutil
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
    desc: 自动连接剪映桌面版执行剪辑操作，如果剪映未安装则使用FFmpeg备用方案
    integrations: 剪映桌面版, FFmpeg
    """
    ctx = runtime.context
    
    material_path = state.material_path
    edit_operations = state.edit_operations
    hook_config = state.hook_config or {}
    audio_strategy = state.audio_strategy or {}
    
    # 工作目录
    work_dir = "/tmp/edit_work"
    os.makedirs(work_dir, exist_ok=True)
    
    # 创建剪辑日志
    edit_log = []
    success_operations = []
    failed_operations = []
    used_engine = "unknown"
    
    # 输出文件路径
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(work_dir, f"edited_output_{timestamp}.mp4")
    
    try:
        # ========================================
        # 优先尝试使用剪映自动化
        # ========================================
        jianying_result = _try_jianying_automation(
            material_path, 
            edit_operations, 
            hook_config,
            audio_strategy,
            output_path,
            edit_log
        )
        
        if jianying_result['success']:
            used_engine = "剪映桌面版"
            success_operations = jianying_result.get('success_operations', [])
            failed_operations = jianying_result.get('failed_operations', [])
        else:
            # 剪映失败，使用FFmpeg备用方案
            edit_log.append(f"⚠️ 剪映自动化不可用: {jianying_result.get('error', '未知原因')}")
            edit_log.append("📌 切换到FFmpeg备用方案...")
            
            ffmpeg_result = _execute_with_ffmpeg(
                material_path,
                edit_operations,
                hook_config,
                audio_strategy,
                output_path,
                work_dir,
                edit_log
            )
            
            used_engine = "FFmpeg"
            success_operations = ffmpeg_result.get('success_operations', [])
            failed_operations = ffmpeg_result.get('failed_operations', [])
            
            if not ffmpeg_result['success']:
                return EditExecuteOutput(
                    output_path="",
                    edit_log=edit_log,
                    success_operations=success_operations,
                    failed_operations=failed_operations,
                    total_operations=len(edit_operations) if edit_operations else 0,
                    error=ffmpeg_result.get('error', '剪辑执行失败')
                )
        
        # 检查输出文件
        if not os.path.exists(output_path):
            # 尝试从工作目录找最新文件
            output_path = _find_latest_output(work_dir)
        
        if output_path and os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
            edit_log.append(f"✅ 剪辑完成，输出文件: {output_path}")
            edit_log.append(f"   文件大小: {file_size:.2f} MB")
        else:
            edit_log.append("⚠️ 输出文件未找到，但操作已执行")
        
    except Exception as e:
        edit_log.append(f"❌ 执行异常: {str(e)}")
        return EditExecuteOutput(
            output_path="",
            edit_log=edit_log,
            success_operations=success_operations,
            failed_operations=failed_operations,
            total_operations=len(edit_operations) if edit_operations else 0,
            error=str(e)
        )
    
    return EditExecuteOutput(
        output_path=output_path if os.path.exists(output_path) else "",
        edit_log=edit_log,
        success_operations=success_operations,
        failed_operations=failed_operations,
        total_operations=len(edit_operations) if edit_operations else 0,
        used_engine=used_engine
    )


def _try_jianying_automation(
    material_path: str,
    edit_operations: List[Dict],
    hook_config: Dict,
    audio_strategy: Dict,
    output_path: str,
    edit_log: List[str]
) -> Dict[str, Any]:
    """
    尝试使用剪映自动化进行剪辑
    优先使用剪映网页版，失败则尝试桌面版
    
    Returns:
        包含success和error的字典
    """
    result = {
        'success': False,
        'error': None,
        'success_operations': [],
        'failed_operations': []
    }
    
    # ========================================
    # 优先尝试剪映网页版
    # ========================================
    edit_log.append("🌐 尝试使用剪映网页版...")
    
    try:
        from tools.jianying_web_controller import JianyingWebController, check_playwright_installed
        
        # 检查 Playwright 是否安装
        if check_playwright_installed():
            # 创建控制器
            jianying_web = JianyingWebController(headless=False)
            
            # 构建剪辑计划
            edit_plan = {
                'edit_points': edit_operations or [],
                'hook_config': hook_config,
                'audio_strategy': audio_strategy
            }
            
            # 执行剪辑
            exec_result = jianying_web.execute_edit_plan(
                edit_plan=edit_plan,
                video_path=material_path,
                output_path=output_path
            )
            
            if exec_result.get('success'):
                result['success'] = True
                result['success_operations'] = exec_result.get('operations', [])
                edit_log.append("✅ 剪映网页版剪辑完成")
                return result
            else:
                edit_log.append(f"⚠️ 剪映网页版失败: {exec_result.get('errors', [])}")
                jianying_web.close()
        else:
            edit_log.append("⚠️ Playwright 未安装，跳过剪映网页版")
            
    except ImportError as e:
        edit_log.append(f"⚠️ 剪映网页版控制器不可用: {e}")
    except Exception as e:
        edit_log.append(f"⚠️ 剪映网页版执行出错: {e}")
    
    # ========================================
    # 尝试剪映桌面版
    # ========================================
    edit_log.append("🖥️ 尝试使用剪映桌面版...")
    
    try:
        # 导入剪映控制器
        from tools.jianying_controller import JianyingController, check_jianying_installed
        
        # 检查剪映是否安装
        if not check_jianying_installed():
            result['error'] = "剪映未安装或未找到安装路径"
            return result
        
        edit_log.append("🎬 检测到剪映已安装，正在启动...")
        
        # 创建控制器
        controller = JianyingController()
        
        # 构建剪辑计划
        edit_plan = {
            'edit_points': edit_operations or [],
            'hook_config': hook_config,
            'audio_strategy': audio_strategy
        }
        
        # 执行剪辑
        exec_result = controller.execute_edit_plan(
            edit_plan=edit_plan,
            material_path=material_path,
            output_path=output_path
        )
        
        if exec_result.get('success'):
            result['success'] = True
            result['success_operations'] = exec_result.get('operations', [])
            edit_log.append("✅ 剪映桌面版剪辑完成")
        else:
            result['error'] = "; ".join(exec_result.get('errors', ['未知错误']))
            result['failed_operations'] = exec_result.get('failed_operations', [])
            edit_log.append(f"❌ 剪映桌面版失败: {result['error']}")
        
    except ImportError as e:
        result['error'] = f"剪映控制器导入失败: {str(e)}"
        edit_log.append(f"⚠️ {result['error']}")
        
    except Exception as e:
        result['error'] = f"剪映自动化异常: {str(e)}"
        edit_log.append(f"❌ {result['error']}")
    
    return result


def _execute_with_ffmpeg(
    material_path: str,
    edit_operations: List[Dict],
    hook_config: Dict,
    audio_strategy: Dict,
    output_path: str,
    work_dir: str,
    edit_log: List[str]
) -> Dict[str, Any]:
    """
    使用FFmpeg执行剪辑操作（备用方案）
    """
    result = {
        'success': False,
        'error': None,
        'success_operations': [],
        'failed_operations': []
    }
    
    try:
        edit_log.append("📦 使用FFmpeg执行剪辑...")
        
        # 解析剪辑操作
        operations = _parse_operations(edit_operations)
        
        if not operations:
            # 如果没有操作，直接复制文件
            shutil.copy(material_path, output_path)
            result['success'] = True
            edit_log.append("✓ 无剪辑操作，直接复制文件")
            return result
        
        # 按序列执行剪辑操作
        current_input = material_path
        temp_files = []
        
        for i, op in enumerate(operations):
            op_type = op.get('operation_type', 'cut')
            op_log = f"执行操作 {i+1}: {op_type} - {op.get('content', '')}"
            edit_log.append(op_log)
            
            temp_output = os.path.join(work_dir, f"step_{i+1}.mp4")
            
            try:
                if op_type == 'cut':
                    exec_result = _execute_cut(current_input, temp_output, op)
                elif op_type == 'slow_motion':
                    exec_result = _execute_slow_motion(current_input, temp_output, op)
                elif op_type == 'effect':
                    exec_result = _execute_effect(current_input, temp_output, op)
                elif op_type == 'text':
                    exec_result = _execute_text(current_input, temp_output, op)
                elif op_type == 'audio':
                    exec_result = _execute_audio(current_input, temp_output, op, audio_strategy)
                else:
                    exec_result = _execute_cut(current_input, temp_output, op)
                
                if exec_result['success']:
                    temp_files.append(temp_output)
                    current_input = temp_output
                    result['success_operations'].append(i+1)
                    edit_log.append(f"  ✓ 操作成功")
                else:
                    result['failed_operations'].append(i+1)
                    edit_log.append(f"  ✗ 操作失败: {exec_result.get('error', '未知错误')}")
                    
            except Exception as e:
                result['failed_operations'].append(i+1)
                edit_log.append(f"  ✗ 操作异常: {str(e)}")
        
        # 应用钩子效果（开场3秒特殊处理）
        if hook_config and hook_config.get('opening_3_seconds'):
            hook_output = os.path.join(work_dir, "hook_applied.mp4")
            hook_result = _apply_hook(current_input, hook_output, hook_config)
            if hook_result['success']:
                current_input = hook_output
                edit_log.append("✓ 钩子效果应用成功")
            else:
                edit_log.append(f"⚠️ 钩子效果应用失败: {hook_result.get('error')}")
        
        # 最终输出
        if os.path.exists(current_input):
            shutil.copy(current_input, output_path)
            result['success'] = True
        else:
            result['error'] = "最终输出文件不存在"
            
    except Exception as e:
        result['error'] = str(e)
        edit_log.append(f"❌ FFmpeg执行异常: {str(e)}")
    
    return result


def _parse_operations(edit_operations: List[Dict]) -> List[Dict]:
    """解析剪辑操作列表"""
    if not edit_operations:
        return []
    
    operations = []
    for op in edit_operations:
        # 解析时间戳
        timestamp = op.get('source_timestamp', '')
        times = timestamp.split('-') if '-' in timestamp else ['0', '0']
        
        start_time = _parse_time(times[0]) if len(times) > 0 else 0
        end_time = _parse_time(times[1]) if len(times) > 1 else 0
        
        # 确定操作类型
        effects = op.get('suggested_effects', [])
        op_type = 'cut'
        if effects:
            effect = effects[0] if isinstance(effects, list) else effects
            if 'slow' in effect.lower() or '慢' in effect:
                op_type = 'slow_motion'
            elif 'effect' in effect.lower() or '特效' in effect:
                op_type = 'effect'
            elif 'text' in effect.lower() or '字幕' in effect:
                op_type = 'text'
        
        operations.append({
            'operation_type': op_type,
            'start_time': start_time,
            'end_time': end_time,
            'duration': op.get('duration', 3),
            'content': op.get('content', ''),
            'effects': effects
        })
    
    return operations


def _parse_time(time_str: str) -> float:
    """解析时间字符串为秒数"""
    try:
        time_str = time_str.strip()
        if ':' in time_str:
            parts = time_str.split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return float(time_str)
    except:
        return 0.0


def _execute_cut(input_path: str, output_path: str, op: Dict) -> Dict:
    """执行剪切操作"""
    try:
        start = op.get('start_time', 0)
        duration = op.get('duration', 3)
        
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-i', input_path,
            '-t', str(duration),
            '-c:v', 'libx264',
            '-c:a', 'aac',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0 and os.path.exists(output_path):
            return {'success': True}
        else:
            return {'success': False, 'error': result.stderr[:200]}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _execute_slow_motion(input_path: str, output_path: str, op: Dict) -> Dict:
    """执行慢动作效果"""
    try:
        speed = op.get('speed', 0.5)  # 默认0.5倍速
        start = op.get('start_time', 0)
        duration = op.get('duration', 3)
        
        # FFmpeg慢动作命令
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-i', input_path,
            '-t', str(duration),
            '-filter:v', f'setpts={1/speed}*PTS',
            '-filter:a', f'atempo={speed}',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0 and os.path.exists(output_path):
            return {'success': True}
        else:
            return {'success': False, 'error': result.stderr[:200]}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _execute_effect(input_path: str, output_path: str, op: Dict) -> Dict:
    """执行特效（简化版，使用滤镜）"""
    try:
        effect = op.get('effects', [''])[0] if op.get('effects') else ''
        
        # 根据特效类型选择滤镜
        if '黑白' in effect or 'bw' in effect.lower():
            filter_str = 'colorchannelmixer=.3:.4:.3:0:.3:.4:.3:0:.3:.4:.3'
        elif '模糊' in effect or 'blur' in effect.lower():
            filter_str = 'boxblur=2:1'
        else:
            # 默认增强对比度
            filter_str = 'eq=contrast=1.2:brightness=0.05'
        
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', filter_str,
            '-c:v', 'libx264',
            '-c:a', 'copy',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0 and os.path.exists(output_path):
            return {'success': True}
        else:
            return {'success': False, 'error': result.stderr[:200]}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _execute_text(input_path: str, output_path: str, op: Dict) -> Dict:
    """执行添加字幕（简化版）"""
    try:
        text = op.get('content', '字幕')
        
        # FFmpeg添加字幕
        filter_str = f"drawtext=text='{text}':fontsize=24:fontcolor=white:x=(w-text_w)/2:y=h-50"
        
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', filter_str,
            '-c:v', 'libx264',
            '-c:a', 'copy',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0 and os.path.exists(output_path):
            return {'success': True}
        else:
            return {'success': False, 'error': result.stderr[:200]}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _execute_audio(input_path: str, output_path: str, op: Dict, audio_strategy: Dict) -> Dict:
    """执行音频处理"""
    try:
        # 简化：保持原音频
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0 and os.path.exists(output_path):
            return {'success': True}
        else:
            return {'success': False, 'error': result.stderr[:200]}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _apply_hook(input_path: str, output_path: str, hook_config: Dict) -> Dict:
    """应用钩子效果（开场特殊处理）"""
    try:
        opening = hook_config.get('opening_3_seconds', {})
        technique = opening.get('technique', '')
        
        if '慢' in technique or 'slow' in technique.lower():
            # 开场3秒慢动作
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-filter:v', 'setpts=1.5*PTS',
                '-filter:a', 'atempo=0.67',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                output_path
            ]
        else:
            # 默认：增加对比度和亮度
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-vf', 'eq=contrast=1.1:brightness=0.02',
                '-c:v', 'libx264',
                '-c:a', 'copy',
                output_path
            ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0 and os.path.exists(output_path):
            return {'success': True}
        else:
            return {'success': False, 'error': result.stderr[:200]}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _find_latest_output(work_dir: str) -> Optional[str]:
    """在工作目录中找到最新的输出文件"""
    try:
        files = [os.path.join(work_dir, f) for f in os.listdir(work_dir) 
                 if f.endswith('.mp4')]
        if files:
            return max(files, key=os.path.getmtime)
    except:
        pass
    return None
