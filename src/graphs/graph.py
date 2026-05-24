"""
服装连锁店AI智能记账助手工作流编排
定义主图结构，编排各节点执行顺序
"""
from typing import Literal

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import (
    GlobalState,
    GraphInput,
    GraphOutput,
    RouteInputTypeInput
)

# 导入节点函数
from graphs.nodes.asr_recognition_node import asr_recognition_node
from graphs.nodes.ocr_recognition_node import ocr_recognition_node
from graphs.nodes.nlu_extraction_node import nlu_extraction_node
from graphs.nodes.data_validation_node import data_validation_node
from graphs.nodes.data_aggregation_node import data_aggregation_node
from graphs.nodes.anomaly_detection_node import anomaly_detection_node
from graphs.nodes.report_generation_node import report_generation_node


# ==================== 条件判断函数 ====================

def route_input_type(state: RouteInputTypeInput) -> Literal["语音报账", "拍照录入", "看板查询"]:
    """
    title: 输入类型路由
    desc: 根据输入类型决定处理分支
    
    Returns:
        "语音报账": 处理语音录入
        "拍照录入": 处理图片录入
        "看板查询": 处理数据查询
    """
    input_type = state.input_type
    
    if input_type == "voice":
        return "语音报账"
    elif input_type == "image":
        return "拍照录入"
    else:
        return "看板查询"


# ==================== 构建主图 ====================

# 创建状态图
builder = StateGraph(
    GlobalState,
    input_schema=GraphInput,
    output_schema=GraphOutput
)

# ==================== 添加节点 ====================

# 语音识别节点
builder.add_node(
    "asr_recognition", 
    asr_recognition_node,
    metadata={"type": "agent", "llm_cfg": "config/asr_recognition_cfg.json"}
)

# 图片识别节点
builder.add_node(
    "ocr_recognition",
    ocr_recognition_node,
    metadata={"type": "agent", "llm_cfg": "config/ocr_recognition_cfg.json"}
)

# NLU提取节点 - 处理语音结果
builder.add_node(
    "nlu_from_asr",
    nlu_extraction_node,
    metadata={"type": "agent", "llm_cfg": "config/nlu_extraction_cfg.json"}
)

# NLU提取节点 - 处理图片结果
builder.add_node(
    "nlu_from_ocr",
    nlu_extraction_node,
    metadata={"type": "agent", "llm_cfg": "config/nlu_extraction_cfg.json"}
)

# 数据校验节点
builder.add_node(
    "data_validation",
    data_validation_node
)

# 数据聚合节点
builder.add_node(
    "data_aggregation",
    data_aggregation_node,
    metadata={"type": "agent", "llm_cfg": "config/data_aggregation_cfg.json"}
)

# 异常检测节点
builder.add_node(
    "anomaly_detection",
    anomaly_detection_node,
    metadata={"type": "agent", "llm_cfg": "config/anomaly_detection_cfg.json"}
)

# 报告生成节点
builder.add_node(
    "report_generation",
    report_generation_node,
    metadata={"type": "agent", "llm_cfg": "config/report_generation_cfg.json"}
)

# ==================== 设置入口点 ====================
builder.set_entry_point("asr_recognition")

# ==================== 添加条件分支 ====================
builder.add_conditional_edges(
    source="asr_recognition",
    path=route_input_type,
    path_map={
        "语音报账": "nlu_from_asr",
        "拍照录入": "ocr_recognition",
        "看板查询": "data_aggregation"
    }
)

# ==================== 添加边 ====================

# OCR分支
builder.add_edge("ocr_recognition", "nlu_from_ocr")

# NLU分支
builder.add_edge("nlu_from_asr", "data_validation")
builder.add_edge("nlu_from_ocr", "data_validation")

# 数据处理流程
builder.add_edge("data_validation", "data_aggregation")
builder.add_edge("data_aggregation", "anomaly_detection")
builder.add_edge("anomaly_detection", "report_generation")
builder.add_edge("report_generation", END)

# ==================== 编译主图 ====================

main_graph = builder.compile()
