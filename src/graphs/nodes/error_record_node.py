"""
错误记录节点
记录剪辑过程中的错误，用于后续优化和返工
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import (
    ErrorRecordInput,
    ErrorRecordOutput
)

# 错误记录文件路径
ERROR_LOG_PATH = "/tmp/edit_work/error_history.json"


def error_record_node(
    state: ErrorRecordInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ErrorRecordOutput:
    """
    title: 错误记录
    desc: 记录剪辑过程中的错误，用于后续优化和返工决策
    integrations: 无
    """
    ctx = runtime.context
    
    # 加载历史错误记录
    history = _load_error_history()
    
    # 记录本次错误
    current_errors = _extract_errors(state.edit_log)
    
    if current_errors:
        error_record = {
            "timestamp": datetime.now().isoformat(),
            "session_id": state.session_id or datetime.now().strftime("%Y%m%d_%H%M%S"),
            "material_path": state.material_path,
            "error_count": len(current_errors),
            "errors": current_errors,
            "edit_log": state.edit_log,
            "operation_types": state.operation_types or []
        }
        
        history.append(error_record)
        
        # 保存更新后的历史
        _save_error_history(history)
    
    # 分析错误模式
    error_patterns = _analyze_error_patterns(history)
    
    # 生成优化建议
    optimization_suggestions = _generate_optimization_suggestions(error_patterns, current_errors)
    
    # 决定是否需要返工
    need_rework = len(current_errors) > 0
    rework_reason = ""
    
    if need_rework:
        rework_reason = _generate_rework_reason(current_errors, error_patterns)
    
    return ErrorRecordOutput(
        recorded=True,
        error_count=len(current_errors),
        error_patterns=error_patterns,
        optimization_suggestions=optimization_suggestions,
        need_rework=need_rework,
        rework_reason=rework_reason
    )


def _load_error_history() -> List[Dict]:
    """加载历史错误记录"""
    if os.path.exists(ERROR_LOG_PATH):
        try:
            with open(ERROR_LOG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []


def _save_error_history(history: List[Dict]):
    """保存错误记录"""
    os.makedirs(os.path.dirname(ERROR_LOG_PATH), exist_ok=True)
    with open(ERROR_LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _extract_errors(edit_log: List[str]) -> List[Dict]:
    """从编辑日志中提取错误"""
    errors = []
    
    for i, log in enumerate(edit_log):
        if '✗' in log or '失败' in log or '异常' in log or '错误' in log:
            errors.append({
                "log_index": i,
                "error_message": log,
                "timestamp": datetime.now().isoformat()
            })
    
    return errors


def _analyze_error_patterns(history: List[Dict]) -> Dict[str, Any]:
    """分析错误模式"""
    if not history:
        return {"patterns": [], "common_errors": []}
    
    # 统计错误类型
    error_types = {}
    
    for record in history:
        for error in record.get("errors", []):
            msg = error.get("error_message", "")
            
            # 分类错误类型
            if "慢动作" in msg or "slow" in msg.lower():
                error_type = "slow_motion_error"
            elif "剪切" in msg or "cut" in msg.lower():
                error_type = "cut_error"
            elif "音频" in msg or "audio" in msg.lower():
                error_type = "audio_error"
            elif "特效" in msg or "effect" in msg.lower():
                error_type = "effect_error"
            else:
                error_type = "unknown_error"
            
            error_types[error_type] = error_types.get(error_type, 0) + 1
    
    # 找出最常见的错误
    common_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:3]
    
    return {
        "total_sessions": len(history),
        "error_type_counts": error_types,
        "common_errors": common_errors
    }


def _generate_optimization_suggestions(patterns: Dict, current_errors: List[Dict]) -> List[str]:
    """生成优化建议"""
    suggestions = []
    
    if not current_errors:
        suggestions.append("本次剪辑无错误，继续保持！")
        return suggestions
    
    # 基于错误类型提供建议
    error_types = patterns.get("error_type_counts", {})
    
    if error_types.get("slow_motion_error", 0) > 0:
        suggestions.append("建议：慢动作处理时先确保原视频帧率足够高（≥30fps）")
    
    if error_types.get("audio_error", 0) > 0:
        suggestions.append("建议：音频处理前先检查视频是否包含音轨")
    
    if error_types.get("cut_error", 0) > 0:
        suggestions.append("建议：剪切操作的时间戳要确保在视频时长范围内")
    
    if error_types.get("effect_error", 0) > 0:
        suggestions.append("建议：特效处理时检查滤镜参数是否兼容")
    
    if len(current_errors) > 2:
        suggestions.append("建议：多个操作失败时，考虑简化剪辑策略或分步执行")
    
    return suggestions


def _generate_rework_reason(errors: List[Dict], patterns: Dict) -> str:
    """生成返工原因"""
    if not errors:
        return ""
    
    reasons = []
    for error in errors[:3]:
        reasons.append(error.get("error_message", "未知错误"))
    
    return " | ".join(reasons)
