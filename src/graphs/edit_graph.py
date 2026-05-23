"""
剪辑Agent工作流编排
将策略解析、素材加载、剪辑执行、成品输出等节点编排为完整的剪辑工作流
"""
import os
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime

from graphs.state import (
    EditGlobalState,
    EditGraphInput,
    EditGraphOutput,
    ReworkDecisionInput
)

# 导入剪辑节点
from graphs.nodes.strategy_parse_node import strategy_parse_node
from graphs.nodes.material_load_node import material_load_node
from graphs.nodes.edit_execute_node import edit_execute_node
from graphs.nodes.output_export_node import output_export_node
from graphs.nodes.error_record_node import error_record_node


# ==================== 条件判断函数 ====================
def should_rework(state: ReworkDecisionInput) -> str:
    """
    title: 返工决策
    desc: 根据错误数量和返工次数决定是否需要返工
    """
    # 最多返工3次
    max_revisions = 3
    
    # 如果已达到最大返工次数，直接结束
    if state.revision_count >= max_revisions:
        return "达到上限，结束"
    
    # 如果需要返工且有错误，进行返工
    if state.need_rework and (state.error_count > 0 or state.failed_count > 0):
        return "需要返工"
    
    # 否则通过
    return "通过，结束"


# ==================== 构建剪辑工作流 ====================
def build_edit_graph():
    """构建剪辑Agent工作流"""
    
    builder = StateGraph(
        EditGlobalState,
        input_schema=EditGraphInput,
        output_schema=EditGraphOutput
    )
    
    # 添加节点
    builder.add_node(
        "strategy_parse",
        strategy_parse_node,
        metadata={"type": "agent", "llm_cfg": "config/strategy_parse_llm_cfg.json"}
    )
    
    builder.add_node("material_load", material_load_node)
    builder.add_node("edit_execute", edit_execute_node)
    builder.add_node("output_export", output_export_node)
    builder.add_node("error_record", error_record_node)
    
    # 设置入口点
    builder.set_entry_point("strategy_parse")
    
    # 添加边
    builder.add_edge("strategy_parse", "material_load")
    builder.add_edge("material_load", "edit_execute")
    builder.add_edge("edit_execute", "output_export")
    builder.add_edge("output_export", "error_record")
    
    # 添加条件分支（返工判断）
    builder.add_conditional_edges(
        source="error_record",
        path=should_rework,
        path_map={
            "需要返工": "edit_execute",  # 返工重新剪辑
            "通过，结束": END,
            "达到上限，结束": END
        }
    )
    
    return builder.compile()


# 编译图
edit_graph = build_edit_graph()
