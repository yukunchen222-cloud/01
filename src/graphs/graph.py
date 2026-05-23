"""
爆款Agent工作流编排
定义主图结构，编排各节点执行顺序
"""
from typing import Literal

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime

from graphs.state import (
    GlobalState,
    GraphInput,
    GraphOutput,
    MaterialAnalyzeInput,
    ViralSearchInput,
    ViralAnalyzeInput,
    EditStrategyInput,
    ReviewCompareInput,
    StrategyConfirmInput
)

# 导入节点函数
from graphs.nodes.material_analyze_node import material_analyze_node
from graphs.nodes.viral_search_node import viral_search_node
from graphs.nodes.viral_analyze_node import viral_analyze_node
from graphs.nodes.edit_strategy_node import edit_strategy_node
from graphs.nodes.review_compare_node import review_compare_node


# ==================== 条件判断函数 ====================

def check_strategy_confirmed(state: StrategyConfirmInput) -> Literal["已确认", "待确认"]:
    """
    title: 策略确认检查
    desc: 检查剪辑策略是否已被人工确认
    
    Returns:
        "已确认": 策略已确认，可继续后续流程
        "待确认": 策略需要人工确认
    """
    # 检查状态中的确认标志
    # 注意：这里简化处理，实际应该有更复杂的确认机制
    # 比如等待外部输入或者人工审核
    edit_strategy = state.edit_strategy
    
    if edit_strategy and len(edit_strategy) > 0:
        # 如果策略已生成，返回"待确认"等待人工确认
        # 在实际使用中，这里应该暂停等待人工输入
        return "待确认"
    
    return "待确认"


def check_review_result(state: GlobalState) -> Literal["审核通过", "需要返工"]:
    """
    title: 审核结果检查
    desc: 检查审核结果，决定是否需要返工
    
    Returns:
        "审核通过": 视频质量达标
        "需要返工": 需要重新剪辑
    """
    if state.review_passed:
        return "审核通过"
    else:
        return "需要返工"


# ==================== 数据转换函数 ====================

def prepare_material_analyze_input(state: GlobalState) -> MaterialAnalyzeInput:
    """准备素材分析节点输入"""
    return MaterialAnalyzeInput(material_video=state.material_video)


def prepare_viral_search_input(state: GlobalState) -> ViralSearchInput:
    """准备爆款搜索节点输入"""
    # 从素材摘要中提取关键词（简化处理）
    keywords = ["短剧", "都市情感"]
    return ViralSearchInput(
        drama_keywords=keywords,
        drama_type="都市情感"
    )


def prepare_viral_analyze_input(state: GlobalState) -> ViralAnalyzeInput:
    """准备爆款分析节点输入"""
    return ViralAnalyzeInput(
        viral_videos=state.viral_videos,
        material_summary=state.material_summary
    )


def prepare_edit_strategy_input(state: GlobalState) -> EditStrategyInput:
    """准备剪辑策略节点输入"""
    viral_analysis = state.viral_analysis
    hook_points = []
    title_patterns = []
    cover_patterns = []
    
    if viral_analysis:
        viral_formulas = viral_analysis.get("viral_formulas", {})
        hook_points = viral_formulas.get("hook_templates", [])
        title_patterns = [f.get("pattern", "") for f in viral_formulas.get("title_formulas", [])]
        cover_patterns = [str(f) for f in viral_formulas.get("cover_formulas", [])]
    
    return EditStrategyInput(
        material_summary=state.material_summary,
        viral_analysis=viral_analysis,
        hook_points=hook_points,
        title_patterns=title_patterns,
        cover_patterns=cover_patterns
    )


def prepare_review_input(state: GlobalState) -> ReviewCompareInput:
    """准备审核节点输入"""
    return ReviewCompareInput(
        edited_video=state.edited_video,
        viral_analysis=state.viral_analysis,
        edit_strategy=state.edit_strategy,
        revision_count=state.revision_count
    )


# ==================== 状态更新函数 ====================

def update_from_material_analyze(state: GlobalState, result: MaterialAnalyzeInput) -> dict:
    """从素材分析结果更新状态"""
    # 注意：这里result实际是MaterialAnalyzeOutput
    return {
        "material_summary": getattr(result, 'material_summary', ''),
        "material_keyframes": getattr(result, 'material_keyframes', []),
        "material_subtitle": getattr(result, 'material_subtitle', '')
    }


# ==================== 主图编排 ====================

def build_viral_agent_graph():
    """构建爆款Agent工作流图"""
    
    # 创建状态图
    builder = StateGraph(
        GlobalState,
        input_schema=GraphInput,
        output_schema=GraphOutput
    )
    
    # 添加节点
    # 1. 素材视频分析节点
    builder.add_node(
        "material_analyze",
        material_analyze_node,
        metadata={
            "type": "agent",
            "llm_cfg": "config/material_analyze_llm_cfg.json"
        }
    )
    
    # 2. 爆款视频搜索节点
    builder.add_node(
        "viral_search",
        viral_search_node
    )
    
    # 3. 爆款内容分析节点
    builder.add_node(
        "viral_analyze",
        viral_analyze_node,
        metadata={
            "type": "agent",
            "llm_cfg": "config/viral_analyze_llm_cfg.json"
        }
    )
    
    # 4. 剪辑策略生成节点
    builder.add_node(
        "edit_strategy",
        edit_strategy_node,
        metadata={
            "type": "agent",
            "llm_cfg": "config/edit_strategy_llm_cfg.json"
        }
    )
    
    # 5. 审核比对节点
    builder.add_node(
        "review_compare",
        review_compare_node,
        metadata={
            "type": "agent",
            "llm_cfg": "config/review_llm_cfg.json"
        }
    )
    
    # 设置入口点
    builder.set_entry_point("material_analyze")
    
    # 添加边
    # 素材分析 -> 爆款搜索
    builder.add_edge("material_analyze", "viral_search")
    
    # 爆款搜索 -> 爆款分析
    builder.add_edge("viral_search", "viral_analyze")
    
    # 爆款分析 -> 剪辑策略生成
    builder.add_edge("viral_analyze", "edit_strategy")
    
    # 剪辑策略 -> 策略确认（条件分支）
    # 注意：实际使用中，这里应该有人工确认环节
    # 简化处理：策略生成后直接结束，等待人工确认后继续
    builder.add_edge("edit_strategy", END)
    
    # 编译图
    graph = builder.compile()
    
    return graph


# 创建全局图实例
main_graph = build_viral_agent_graph()
