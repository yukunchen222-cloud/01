"""
服装连锁店AI智能记账助手 - 工作流状态定义
定义全局状态、图的输入输出、各节点的输入输出
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from utils.file.file import File


# ==================== 全局状态 ====================

class GlobalState(BaseModel):
    """全局状态"""
    input_type: str = Field(default="", description="输入类型")
    audio_file: Optional[File] = Field(default=None, description="语音文件")
    image_file: Optional[File] = Field(default=None, description="图片文件")
    query_type: Optional[str] = Field(default=None, description="查询类型")
    store_id: Optional[str] = Field(default=None, description="门店ID")
    store_name: Optional[str] = Field(default=None, description="门店名称")
    org_id: str = Field(default="org_default", description="组织ID")
    recognized_text: str = Field(default="", description="语音识别后的文字")
    ocr_text: str = Field(default="", description="图片识别后的文字")
    extracted_data: Dict[str, Any] = Field(default_factory=dict, description="提取的结构化数据")
    confidence: float = Field(default=0.0, description="AI识别置信度")
    validation_passed: bool = Field(default=False, description="数据校验是否通过")
    validation_errors: List[str] = Field(default_factory=list, description="校验错误信息")
    dashboard_data: Dict[str, Any] = Field(default_factory=dict, description="聚合的看板数据")
    anomaly_alerts: List[Dict[str, Any]] = Field(default_factory=list, description="异常预警列表")
    report_url: str = Field(default="", description="生成的报告URL")
    records: List[Dict[str, Any]] = Field(default_factory=list, description="历史账目记录")


# ==================== 图输入输出 ====================

class GraphInput(BaseModel):
    """工作流输入"""
    input_type: Literal["voice", "image", "query"] = Field(
        ..., 
        description="输入类型：voice(语音报账)、image(拍照录入)、query(看板查询)"
    )
    audio_file: Optional[File] = Field(default=None, description="语音文件")
    image_file: Optional[File] = Field(default=None, description="图片文件")
    recognized_text: str = Field(default="", description="已识别的语音文本（外部ASR完成后直接传入）")
    ocr_text: str = Field(default="", description="已识别的OCR文本（外部OCR完成后直接传入）")
    query_type: Optional[Literal["today", "week", "month", "anomaly", "report"]] = Field(
        default=None, 
        description="查询类型：today/week/month/anomaly/report"
    )
    store_id: Optional[str] = Field(default=None, description="门店ID")
    store_name: Optional[str] = Field(default=None, description="门店名称")
    org_id: str = Field(default="org_default", description="组织ID")
    records: Optional[List[Dict[str, Any]]] = Field(default=None, description="历史账目记录")


class GraphOutput(BaseModel):
    """工作流输出"""
    success: bool = Field(default=False, description="处理是否成功")
    message: str = Field(default="", description="处理结果消息")
    extracted_data: Optional[Dict[str, Any]] = Field(default=None, description="提取的账目数据")
    confidence: float = Field(default=0.0, description="AI识别置信度")
    dashboard_data: Optional[Dict[str, Any]] = Field(default=None, description="看板数据")
    anomaly_alerts: Optional[List[Dict[str, Any]]] = Field(default=None, description="异常预警列表")
    report_url: Optional[str] = Field(default=None, description="报告文件URL")


# ==================== 条件分支输入 ====================

class RouteInputTypeInput(BaseModel):
    """路由输入类型判断的输入"""
    input_type: str = Field(..., description="输入类型")


class RouteAfterProcessInput(BaseModel):
    """处理后路由判断的输入"""
    validation_passed: bool = Field(default=False, description="数据校验是否通过")


# ==================== 入口路由节点 ====================

class EntryRouterInput(BaseModel):
    """入口路由节点输入"""
    input_type: str = Field(..., description="输入类型")
    audio_file: Optional[File] = Field(default=None, description="语音文件")
    image_file: Optional[File] = Field(default=None, description="图片文件")
    recognized_text: str = Field(default="", description="已识别文本")
    ocr_text: str = Field(default="", description="OCR文本")
    store_id: Optional[str] = Field(default=None, description="门店ID")
    store_name: Optional[str] = Field(default=None, description="门店名称")
    org_id: str = Field(default="org_default", description="组织ID")
    query_type: Optional[str] = Field(default=None, description="查询类型")
    records: Optional[List[Dict[str, Any]]] = Field(default=None, description="历史记录")


class EntryRouterOutput(BaseModel):
    """入口路由节点输出（透传所有字段）"""
    input_type: str = Field(..., description="输入类型")
    audio_file: Optional[File] = Field(default=None, description="语音文件")
    image_file: Optional[File] = Field(default=None, description="图片文件")
    recognized_text: str = Field(default="", description="已识别文本")
    ocr_text: str = Field(default="", description="OCR文本")
    store_id: Optional[str] = Field(default=None, description="门店ID")
    store_name: Optional[str] = Field(default=None, description="门店名称")
    org_id: str = Field(default="org_default", description="组织ID")
    query_type: Optional[str] = Field(default=None, description="查询类型")
    records: Optional[List[Dict[str, Any]]] = Field(default=None, description="历史记录")


# ==================== 节点独立输入输出定义 ====================

# 1. ASR 语音识别节点
class ASRInput(BaseModel):
    """ASR语音识别节点输入"""
    audio_file: Optional[File] = Field(default=None, description="语音文件")
    input_type: str = Field(default="voice", description="输入类型")
    recognized_text: str = Field(default="", description="已识别的文本（外部ASR完成后直接传入）")


class ASROutput(BaseModel):
    """ASR语音识别节点输出"""
    recognized_text: str = Field(..., description="识别的文字内容")
    confidence: float = Field(default=0.0, description="识别置信度")
    input_type: str = Field(default="voice", description="输入类型，用于路由判断")


# 2. OCR 图片识别节点
class OCRInput(BaseModel):
    """OCR图片识别节点输入"""
    image_file: Optional[File] = Field(default=None, description="图片文件")
    input_type: str = Field(default="image", description="输入类型")
    ocr_text: str = Field(default="", description="已有的OCR识别文本（外部传入时保留）")


class OCROutput(BaseModel):
    """OCR图片识别节点输出"""
    ocr_text: str = Field(..., description="识别的文字内容")
    confidence: float = Field(default=0.0, description="识别置信度")
    input_type: str = Field(default="image", description="输入类型")


# 3. NLU 数据提取节点
class NLUInput(BaseModel):
    """NLU数据提取节点输入"""
    recognized_text: str = Field(default="", description="ASR识别的文字")
    ocr_text: str = Field(default="", description="OCR识别的文字")
    input_type: str = Field(default="voice", description="输入类型")
    org_id: str = Field(default="org_default", description="组织ID")


class NLUOutput(BaseModel):
    """NLU数据提取节点输出"""
    extracted_data: Dict[str, Any] = Field(default_factory=dict, description="提取的结构化数据")
    confidence: float = Field(default=0.0, description="提取置信度")
    data_type: str = Field(default="sale", description="数据类型：revenue/purchase/expense/return/inventory")


# 4. 数据校验节点
class ValidationInput(BaseModel):
    """数据校验节点输入"""
    extracted_data: Dict[str, Any] = Field(default_factory=dict, description="提取的数据")
    data_type: str = Field(default="sale", description="数据类型")


class ValidationOutput(BaseModel):
    """数据校验节点输出"""
    validation_passed: bool = Field(..., description="校验是否通过")
    validated_data: Dict[str, Any] = Field(default_factory=dict, description="校验后的数据")
    errors: List[str] = Field(default_factory=list, description="错误信息")


# 5. 数据聚合节点
class AggregationInput(BaseModel):
    """数据聚合节点输入"""
    query_type: Optional[str] = Field(default="month", description="查询类型")
    store_id: Optional[str] = Field(default=None, description="门店ID")
    validated_data: Dict[str, Any] = Field(default_factory=dict, description="校验后的数据")
    records: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="历史记录")
    fixed_expenses: Dict[str, Any] = Field(default_factory=dict, description="固定费用配置")
    last_period_data: Dict[str, Any] = Field(default_factory=dict, description="上一周期数据")


class AggregationOutput(BaseModel):
    """数据聚合节点输出"""
    dashboard_data: Dict[str, Any] = Field(..., description="聚合的看板数据")
    summary: str = Field(default="", description="数据摘要")


# 6. 异常检测节点
class AnomalyInput(BaseModel):
    """异常检测节点输入"""
    dashboard_data: Dict[str, Any] = Field(default_factory=dict, description="看板数据")
    records: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="历史记录")


class AnomalyOutput(BaseModel):
    """异常检测节点输出"""
    has_anomaly: bool = Field(..., description="是否存在异常")
    anomaly_alerts: List[Dict[str, Any]] = Field(default_factory=list, description="异常预警列表")


# 7. 报告生成节点
class ReportInput(BaseModel):
    """报告生成节点输入"""
    dashboard_data: Dict[str, Any] = Field(default_factory=dict, description="看板数据")
    anomaly_alerts: List[Dict[str, Any]] = Field(default_factory=list, description="异常预警")
    query_type: Optional[str] = Field(default="month", description="报告类型")


class ReportOutput(BaseModel):
    """报告生成节点输出"""
    report_url: str = Field(..., description="生成的报告URL")
    report_summary: str = Field(default="", description="报告摘要")
