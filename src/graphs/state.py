"""
服装连锁店AI智能记账助手工作流状态定义
定义全局状态、图的输入输出、各节点的输入输出
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from utils.file.file import File


# ==================== 短剧推广自动剪辑工作流状态定义 ====================
# 注意：保留原有的短剧推广工作流状态定义，新增记账助手状态定义

class VideoClassifyInput(BaseModel):
    """视频分类节点输入"""
    video_path: str = Field(..., description="视频文件路径")
    video_url: str = Field(default="", description="视频URL（如果有）")


class VideoClassifyOutput(BaseModel):
    """视频分类节点输出"""
    drama_type: str = Field(..., description="识别出的短剧类型")
    drama_type_confidence: float = Field(default=0.0, description="类型置信度")
    content_summary: str = Field(default="", description="视频内容摘要")
    key_elements: List[str] = Field(default=[], description="关键元素列表")
    emotion_tone: str = Field(default="", description="情感基调")
    suggested_style: str = Field(default="", description="建议剪辑风格")


class GlobalState(BaseModel):
    """全局状态 - 支持多工作流"""
    # ===== 记账助手状态 =====
    input_type: str = Field(default="", description="输入类型")
    audio_file: Optional[File] = Field(default=None, description="语音文件")
    image_file: Optional[File] = Field(default=None, description="图片文件")
    query_type: Optional[str] = Field(default=None, description="查询类型")
    store_id: Optional[str] = Field(default=None, description="门店ID")
    store_name: Optional[str] = Field(default=None, description="门店名称")
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
    
    # ===== 短剧推广工作流状态 =====
    material_video: Optional[File] = Field(default=None, description="原始素材视频")
    material_summary: str = Field(default="", description="素材视频内容摘要")
    material_keyframes: List[str] = Field(default_factory=list, description="素材关键帧URL列表")
    material_subtitle: str = Field(default="", description="素材视频字幕文本")
    viral_videos: List[Dict[str, Any]] = Field(default_factory=list, description="搜索到的爆款视频列表")
    viral_analysis: Dict[str, Any] = Field(default_factory=dict, description="爆款视频分析结果")
    edit_strategy: Dict[str, Any] = Field(default_factory=dict, description="生成的剪辑策略")
    strategy_confirmed: bool = Field(default=False, description="策略是否已人工确认")
    edited_video: Optional[File] = Field(default=None, description="剪辑后的视频")
    review_result: Dict[str, Any] = Field(default_factory=dict, description="审核结果")
    review_passed: bool = Field(default=False, description="审核是否通过")
    revision_count: int = Field(default=0, description="返工次数")
    revision_history: List[Dict[str, Any]] = Field(default_factory=list, description="返工历史记录")


class EditGlobalState(BaseModel):
    """剪辑Agent全局状态"""
    raw_strategy: str = Field(default="", description="原始剪辑策略JSON字符串")
    edit_operations: List[Dict[str, Any]] = Field(default_factory=list, description="解析后的剪辑操作列表")
    hook_config: Dict[str, Any] = Field(default_factory=dict, description="钩子配置")
    audio_strategy: Dict[str, Any] = Field(default_factory=dict, description="音频策略")
    material_path: str = Field(default="", description="素材文件路径")
    material_info: Dict[str, Any] = Field(default_factory=dict, description="素材信息")
    output_path: str = Field(default="", description="剪辑输出路径")
    edit_log: List[str] = Field(default_factory=list, description="剪辑操作日志")
    success_count: int = Field(default=0, description="成功操作数")
    failed_count: int = Field(default=0, description="失败操作数")
    final_output_path: str = Field(default="", description="最终成品路径")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="视频元数据")
    title_suggestions: List[Dict[str, Any]] = Field(default_factory=list, description="标题建议")
    cover_config: Dict[str, Any] = Field(default_factory=dict, description="封面配置")
    error_count: int = Field(default=0, description="错误数量")
    need_rework: bool = Field(default=False, description="是否需要返工")
    revision_count: int = Field(default=0, description="已返工次数")
    error_patterns: Dict[str, Any] = Field(default_factory=dict, description="错误模式分析")
    optimization_suggestions: List[str] = Field(default_factory=list, description="优化建议")


# ===== 短剧推广工作流图的输入输出 =====
class MaterialAnalyzeInput(BaseModel):
    """素材分析节点输入"""
    material_video: File = Field(..., description="原始素材视频文件")


class MaterialAnalyzeOutput(BaseModel):
    """素材分析节点输出"""
    summary: str = Field(default="", description="视频内容摘要")
    keyframes: List[str] = Field(default_factory=list, description="关键帧URL列表")
    subtitle: str = Field(default="", description="字幕文本")


class ViralSearchInput(BaseModel):
    """爆款搜索节点输入"""
    drama_keywords: List[str] = Field(default_factory=list, description="短剧关键词")
    drama_type: str = Field(default="", description="短剧类型")


class ViralSearchOutput(BaseModel):
    """爆款搜索节点输出"""
    viral_videos: List[Dict[str, Any]] = Field(default_factory=list, description="爆款视频列表")


class ViralAnalyzeInput(BaseModel):
    """爆款分析节点输入"""
    viral_videos: List[Dict[str, Any]] = Field(default_factory=list, description="爆款视频列表")
    material_summary: str = Field(default="", description="素材摘要")


class ViralAnalyzeOutput(BaseModel):
    """爆款分析节点输出"""
    viral_analysis: Dict[str, Any] = Field(default_factory=dict, description="分析结果")


class EditStrategyInput(BaseModel):
    """剪辑策略节点输入"""
    viral_analysis: Dict[str, Any] = Field(default_factory=dict, description="爆款分析结果")
    hook_points: List[str] = Field(default_factory=list, description="钩子点")
    title_patterns: List[str] = Field(default_factory=list, description="标题模式")
    cover_patterns: List[str] = Field(default_factory=list, description="封面模式")
    material_summary: str = Field(default="", description="素材摘要")


class EditStrategyOutput(BaseModel):
    """剪辑策略节点输出"""
    edit_strategy: Dict[str, Any] = Field(default_factory=dict, description="剪辑策略")


class ReviewCompareInput(BaseModel):
    """审核对比节点输入"""
    edited_video: File = Field(..., description="剪辑后的视频")
    edit_strategy: Dict[str, Any] = Field(default_factory=dict, description="剪辑策略")
    viral_analysis: Dict[str, Any] = Field(default_factory=dict, description="爆款分析结果")
    revision_count: int = Field(default=0, description="返工次数")


class ReviewCompareOutput(BaseModel):
    """审核对比节点输出"""
    review_passed: bool = Field(default=False, description="审核是否通过")
    review_result: Dict[str, Any] = Field(default_factory=dict, description="审核结果")


class StrategyConfirmInput(BaseModel):
    """策略确认检查输入"""
    edit_strategy: Dict[str, Any] = Field(default_factory=dict, description="剪辑策略")


# ===== 编辑工作流节点输入输出 =====
class EditExecuteInput(BaseModel):
    """剪辑执行节点输入"""
    edit_operations: List[Dict[str, Any]] = Field(default_factory=list, description="剪辑操作列表")
    material_path: str = Field(default="", description="素材路径")
    hook_config: Dict[str, Any] = Field(default_factory=dict, description="钩子配置")
    audio_strategy: Dict[str, Any] = Field(default_factory=dict, description="音频策略")


class EditExecuteOutput(BaseModel):
    """剪辑执行节点输出"""
    output_path: str = Field(default="", description="输出路径")
    edit_log: List[str] = Field(default_factory=list, description="操作日志")


class ErrorRecordInput(BaseModel):
    """错误记录节点输入"""
    error_count: int = Field(default=0, description="错误数量")
    edit_log: List[str] = Field(default_factory=list, description="操作日志")
    session_id: str = Field(default="", description="会话ID")
    material_path: str = Field(default="", description="素材路径")
    operation_types: List[str] = Field(default_factory=list, description="操作类型列表")


class ErrorRecordOutput(BaseModel):
    """错误记录节点输出"""
    error_patterns: Dict[str, Any] = Field(default_factory=dict, description="错误模式")
    optimization_suggestions: List[str] = Field(default_factory=list, description="优化建议")


class MaterialLoadInput(BaseModel):
    """素材加载节点输入"""
    material_path: str = Field(default="", description="素材路径")
    material_library: str = Field(default="", description="素材库路径")
    material_filename: str = Field(default="", description="素材文件名")


class MaterialLoadOutput(BaseModel):
    """素材加载节点输出"""
    material_info: Dict[str, Any] = Field(default_factory=dict, description="素材信息")


class OutputExportInput(BaseModel):
    """成品输出节点输入"""
    output_path: str = Field(default="", description="输出路径")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    output_library: str = Field(default="", description="输出库路径")
    title_suggestions: List[Dict[str, Any]] = Field(default_factory=list, description="标题建议")
    cover_config: Dict[str, Any] = Field(default_factory=dict, description="封面配置")
    edit_log: List[str] = Field(default_factory=list, description="剪辑日志")
    success_count: int = Field(default=0, description="成功操作数")
    failed_count: int = Field(default=0, description="失败操作数")


class OutputExportOutput(BaseModel):
    """成品输出节点输出"""
    final_output_path: str = Field(default="", description="最终输出路径")


class StrategyParseInput(BaseModel):
    """策略解析节点输入"""
    raw_strategy: str = Field(default="", description="原始策略JSON")


class StrategyParseOutput(BaseModel):
    """策略解析节点输出"""
    edit_operations: List[Dict[str, Any]] = Field(default_factory=list, description="解析后的操作")


class ReworkDecisionInput(BaseModel):
    """返工决策输入"""
    need_rework: bool = Field(default=False, description="是否需要返工")
    revision_count: int = Field(default=0, description="返工次数")
    error_count: int = Field(default=0, description="错误数量")
    failed_count: int = Field(default=0, description="失败操作数")


class EditGraphInput(BaseModel):
    """编辑工作流输入"""
    raw_strategy: str = Field(default="", description="原始剪辑策略")
    material_path: str = Field(default="", description="素材路径")


class EditGraphOutput(BaseModel):
    """编辑工作流输出"""
    final_output_path: str = Field(default="", description="最终输出路径")
    need_rework: bool = Field(default=False, description="是否需要返工")


# ==================== 记账助手工作流状态定义 ====================

class GraphInput(BaseModel):
    """记账助手工作流输入"""
    input_type: Literal["voice", "image", "query"] = Field(
        ..., 
        description="输入类型：voice(语音报账)、image(拍照录入)、query(看板查询)"
    )
    audio_file: Optional[File] = Field(
        default=None, 
        description="语音文件（当input_type为voice时必填）"
    )
    image_file: Optional[File] = Field(
        default=None, 
        description="图片文件（当input_type为image时必填）"
    )
    recognized_text: str = Field(
        default="",
        description="已识别的语音文本（外部ASR完成后直接传入，跳过ASR节点）"
    )
    ocr_text: str = Field(
        default="",
        description="已识别的OCR文本（外部OCR完成后直接传入）"
    )
    query_type: Optional[Literal["today", "week", "month", "anomaly", "report"]] = Field(
        default=None, 
        description="查询类型：today(今日看板)、week(本周报表)、month(月报)、anomaly(异常预警)、report(导出报告)"
    )
    store_id: Optional[str] = Field(
        default=None, 
        description="门店ID（用于语音/图片录入时标识门店）"
    )
    store_name: Optional[str] = Field(
        default=None, 
        description="门店名称"
    )
    records: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        description="模拟的历史账目记录数据"
    )


class GraphOutput(BaseModel):
    """记账助手工作流输出"""
    success: bool = Field(default=False, description="处理是否成功")
    message: str = Field(default="", description="处理结果消息")
    extracted_data: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="提取的账目数据（语音/图片录入时）"
    )
    confidence: float = Field(default=0.0, description="AI识别置信度")
    dashboard_data: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="看板数据（查询时）"
    )
    anomaly_alerts: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        description="异常预警列表"
    )
    report_url: Optional[str] = Field(
        default=None, 
        description="生成的报告文件URL"
    )


# ==================== 条件分支输入 ====================

class RouteInputTypeInput(BaseModel):
    """路由输入类型判断的输入"""
    input_type: str = Field(..., description="输入类型")


class RouteAfterProcessInput(BaseModel):
    """处理后路由判断的输入"""
    validation_passed: bool = Field(default=False, description="数据校验是否通过")


# ==================== 节点独立输入输出定义 ====================
# 每个节点的 Input 包含该节点可能需要的所有字段（从 GlobalState 中获取）
# 使用 Optional 和默认值处理条件分支情况

# 1. ASR 语音识别节点
class ASRInput(BaseModel):
    """ASR语音识别节点输入 - 从 GlobalState 获取"""
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
    """OCR图片识别节点输入 - 从 GlobalState 获取"""
    image_file: Optional[File] = Field(default=None, description="图片文件")
    input_type: str = Field(default="image", description="输入类型")
    ocr_text: str = Field(default="", description="已有的OCR识别文本（外部传入时保留）")


class OCROutput(BaseModel):
    """OCR图片识别节点输出"""
    ocr_text: str = Field(..., description="识别的文字内容")
    confidence: float = Field(default=0.0, description="识别置信度")
    input_type: str = Field(default="image", description="输入类型，用于后续节点判断")


# 3. NLU 数据提取节点
class NLUInput(BaseModel):
    """NLU数据提取节点输入 - 从 GlobalState 获取"""
    recognized_text: str = Field(default="", description="ASR识别的文字")
    ocr_text: str = Field(default="", description="OCR识别的文字")
    input_type: str = Field(default="voice", description="输入类型，用于判断使用哪个文本")
    org_id: str = Field(default="org_default", description="组织ID，用于知识库查询")


class NLUOutput(BaseModel):
    """NLU数据提取节点输出"""
    extracted_data: Dict[str, Any] = Field(default_factory=dict, description="提取的结构化数据")
    confidence: float = Field(default=0.0, description="提取置信度")
    data_type: str = Field(default="sale", description="数据类型：sale/purchase/expense")


# 4. 数据校验节点
class ValidationInput(BaseModel):
    """数据校验节点输入 - 从 GlobalState 获取"""
    extracted_data: Dict[str, Any] = Field(default_factory=dict, description="提取的数据")
    data_type: str = Field(default="sale", description="数据类型")


class ValidationOutput(BaseModel):
    """数据校验节点输出"""
    validation_passed: bool = Field(..., description="校验是否通过")
    validated_data: Dict[str, Any] = Field(default_factory=dict, description="校验后的数据")
    errors: List[str] = Field(default_factory=list, description="错误信息")


# 5. 数据聚合节点
class AggregationInput(BaseModel):
    """数据聚合节点输入 - 从 GlobalState 获取"""
    query_type: str = Field(default="month", description="查询类型：day/month/year")
    store_id: Optional[str] = Field(default=None, description="门店ID（可选，不传则聚合所有门店）")
    validated_data: Dict[str, Any] = Field(default_factory=dict, description="校验后的数据")
    records: List[Dict[str, Any]] = Field(default_factory=list, description="历史账目记录")
    fixed_expenses: Dict[str, Any] = Field(default_factory=dict, description="固定费用配置")
    last_period_data: Dict[str, Any] = Field(default_factory=dict, description="上一周期数据")


class AggregationOutput(BaseModel):
    """数据聚合节点输出"""
    dashboard_data: Dict[str, Any] = Field(..., description="聚合的看板数据")
    summary: str = Field(default="", description="数据摘要")


# 6. 异常检测节点
class AnomalyInput(BaseModel):
    """异常检测节点输入 - 从 GlobalState 获取"""
    dashboard_data: Dict[str, Any] = Field(default_factory=dict, description="看板数据")
    records: List[Dict[str, Any]] = Field(default_factory=list, description="历史账目记录")


class AnomalyOutput(BaseModel):
    """异常检测节点输出"""
    has_anomaly: bool = Field(..., description="是否存在异常")
    anomaly_alerts: List[Dict[str, Any]] = Field(default_factory=list, description="异常预警列表")


# 7. 报告生成节点
class ReportInput(BaseModel):
    """报告生成节点输入 - 从 GlobalState 获取"""
    dashboard_data: Dict[str, Any] = Field(default_factory=dict, description="看板数据")
    anomaly_alerts: List[Dict[str, Any]] = Field(default_factory=list, description="异常预警")
    query_type: str = Field(default="month", description="报告类型")


class ReportOutput(BaseModel):
    """报告生成节点输出"""
    report_url: str = Field(..., description="生成的报告URL")
    report_summary: str = Field(default="", description="报告摘要")
