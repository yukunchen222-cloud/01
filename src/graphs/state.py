"""
AI短剧推广自动剪辑工作流状态定义
定义爆款Agent和剪辑Agent的全局状态、图的输入输出、各节点的输入输出
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from utils.file.file import File


# ==================== 视频分类节点输入输出 ====================
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


# ==================== 爆款Agent全局状态 ====================
class GlobalState(BaseModel):
    """爆款Agent全局状态"""
    # 素材相关
    material_video: Optional[File] = Field(default=None, description="原始素材视频")
    material_summary: str = Field(default="", description="素材视频内容摘要")
    material_keyframes: List[str] = Field(default_factory=list, description="素材关键帧URL列表")
    material_subtitle: str = Field(default="", description="素材视频字幕文本")
    
    # 爆款视频相关
    viral_videos: List[Dict[str, Any]] = Field(default_factory=list, description="搜索到的爆款视频列表")
    viral_analysis: Dict[str, Any] = Field(default_factory=dict, description="爆款视频分析结果")
    
    # 剪辑策略
    edit_strategy: Dict[str, Any] = Field(default_factory=dict, description="生成的剪辑策略")
    strategy_confirmed: bool = Field(default=False, description="策略是否已人工确认")
    
    # 审核相关
    edited_video: Optional[File] = Field(default=None, description="剪辑后的视频")
    review_result: Dict[str, Any] = Field(default_factory=dict, description="审核结果")
    review_passed: bool = Field(default=False, description="审核是否通过")
    revision_count: int = Field(default=0, description="返工次数")
    revision_history: List[Dict[str, Any]] = Field(default_factory=list, description="返工历史记录")


# ==================== 剪辑Agent全局状态 ====================
class EditGlobalState(BaseModel):
    """剪辑Agent全局状态"""
    # 策略相关
    raw_strategy: str = Field(default="", description="原始剪辑策略JSON字符串")
    edit_operations: List[Dict[str, Any]] = Field(default_factory=list, description="解析后的剪辑操作列表")
    hook_config: Dict[str, Any] = Field(default_factory=dict, description="钩子配置")
    audio_strategy: Dict[str, Any] = Field(default_factory=dict, description="音频策略")
    
    # 素材相关
    material_path: str = Field(default="", description="素材文件路径")
    material_info: Dict[str, Any] = Field(default_factory=dict, description="素材信息")
    
    # 剪辑执行
    output_path: str = Field(default="", description="剪辑输出路径")
    edit_log: List[str] = Field(default_factory=list, description="剪辑操作日志")
    success_count: int = Field(default=0, description="成功操作数")
    failed_count: int = Field(default=0, description="失败操作数")
    
    # 成品输出
    final_output_path: str = Field(default="", description="最终成品路径")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="视频元数据")
    title_suggestions: List[Dict[str, Any]] = Field(default_factory=list, description="标题建议")
    cover_config: Dict[str, Any] = Field(default_factory=dict, description="封面配置")
    
    # 错误记录
    error_count: int = Field(default=0, description="错误数量")
    need_rework: bool = Field(default=False, description="是否需要返工")
    revision_count: int = Field(default=0, description="已返工次数")
    error_patterns: Dict[str, Any] = Field(default_factory=dict, description="错误模式分析")
    optimization_suggestions: List[str] = Field(default_factory=list, description="优化建议")


# ==================== 图的输入输出定义 ====================
class GraphInput(BaseModel):
    """爆款Agent工作流输入"""
    material_video: File = Field(..., description="原始素材视频文件")
    drama_type: str = Field(default="都市情感", description="短剧类型，如都市情感、古装玄幻等")


class GraphOutput(BaseModel):
    """爆款Agent工作流输出"""
    edit_strategy: Dict[str, Any] = Field(default_factory=dict, description="剪辑策略文档")
    strategy_confirmed: bool = Field(default=False, description="策略是否已确认")
    viral_analysis: Dict[str, Any] = Field(default_factory=dict, description="爆款分析结果")


# ==================== 素材视频分析节点 ====================
class MaterialAnalyzeInput(BaseModel):
    """素材视频分析节点输入"""
    material_video: File = Field(..., description="原始素材视频")


class MaterialAnalyzeOutput(BaseModel):
    """素材视频分析节点输出"""
    material_summary: str = Field(..., description="素材视频内容摘要")
    material_keyframes: List[str] = Field(default_factory=list, description="关键帧URL列表")
    material_subtitle: str = Field(default="", description="视频字幕文本")
    drama_keywords: List[str] = Field(default_factory=list, description="短剧关键词标签")


# ==================== 爆款视频搜索节点 ====================
class ViralSearchInput(BaseModel):
    """爆款视频搜索节点输入"""
    drama_keywords: List[str] = Field(..., description="短剧关键词标签")
    drama_type: str = Field(default="都市情感", description="短剧类型")


class ViralSearchOutput(BaseModel):
    """爆款视频搜索节点输出"""
    viral_videos: List[Dict[str, Any]] = Field(default_factory=list, description="爆款视频列表")
    search_summary: str = Field(default="", description="搜索结果摘要")


# ==================== 爆款内容分析节点 ====================
class ViralAnalyzeInput(BaseModel):
    """爆款内容分析节点输入"""
    viral_videos: List[Dict[str, Any]] = Field(..., description="爆款视频列表")
    material_summary: str = Field(..., description="素材视频摘要")


class ViralAnalyzeOutput(BaseModel):
    """爆款内容分析节点输出"""
    viral_analysis: Dict[str, Any] = Field(default_factory=dict, description="爆款分析结果")
    hook_points: List[Dict[str, Any]] = Field(default_factory=list, description="提取的钩子点列表")
    title_patterns: List[str] = Field(default_factory=list, description="爆款标题模式")
    cover_patterns: List[str] = Field(default_factory=list, description="爆款封面模式")


# ==================== 剪辑策略生成节点 ====================
class EditStrategyInput(BaseModel):
    """剪辑策略生成节点输入"""
    material_summary: str = Field(..., description="素材视频摘要")
    viral_analysis: Dict[str, Any] = Field(..., description="爆款分析结果")
    hook_points: List[Dict[str, Any]] = Field(default_factory=list, description="钩子点列表")
    title_patterns: List[str] = Field(default_factory=list, description="标题模式")
    cover_patterns: List[str] = Field(default_factory=list, description="封面模式")


class EditStrategyOutput(BaseModel):
    """剪辑策略生成节点输出"""
    edit_strategy: Dict[str, Any] = Field(default_factory=dict, description="剪辑策略文档")
    hook_strategy: List[Dict[str, Any]] = Field(default_factory=list, description="钩子运用策略")
    cut_points: List[Dict[str, Any]] = Field(default_factory=list, description="建议剪辑点")
    suggested_title: str = Field(default="", description="建议标题")
    suggested_cover_desc: str = Field(default="", description="建议封面描述")


# ==================== 策略确认条件节点 ====================
class StrategyConfirmInput(BaseModel):
    """策略确认条件节点输入"""
    edit_strategy: Dict[str, Any] = Field(..., description="剪辑策略")


class StrategyConfirmOutput(BaseModel):
    """策略确认条件节点输出"""
    confirmed: bool = Field(default=False, description="是否已确认")


# ==================== 审核比对节点 ====================
class ReviewCompareInput(BaseModel):
    """审核比对节点输入"""
    edited_video: File = Field(..., description="剪辑后的视频")
    viral_analysis: Dict[str, Any] = Field(..., description="爆款分析结果")
    edit_strategy: Dict[str, Any] = Field(..., description="剪辑策略")
    revision_count: int = Field(default=0, description="返工次数")


class ReviewCompareOutput(BaseModel):
    """审核比对节点输出"""
    review_passed: bool = Field(default=False, description="审核是否通过")
    review_result: Dict[str, Any] = Field(default_factory=dict, description="审核详细结果")
    improvement_suggestions: List[str] = Field(default_factory=list, description="改进建议")
    score: float = Field(default=0.0, description="相似度得分(0-100)")


# =====================================================
#             剪辑Agent 节点状态定义
# =====================================================

# ==================== 剪辑图输入输出 ====================
class EditGraphInput(BaseModel):
    """剪辑Agent工作流输入"""
    raw_strategy: str = Field(..., description="原始剪辑策略JSON字符串")
    material_library: str = Field(default="~/Desktop/素材库", description="素材库路径")
    material_filename: Optional[str] = Field(default=None, description="指定素材文件名，为空则自动选择最新")
    output_library: str = Field(default="~/Desktop/成品库", description="成品库路径")


class EditGraphOutput(BaseModel):
    """剪辑Agent工作流输出"""
    final_output_path: str = Field(default="", description="最终成品路径")
    export_success: bool = Field(default=False, description="导出是否成功")
    need_rework: bool = Field(default=False, description="是否需要返工")
    error_message: str = Field(default="", description="错误信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="视频元数据")


# ==================== 策略解析节点 ====================
class StrategyParseInput(BaseModel):
    """策略解析节点输入"""
    raw_strategy: str = Field(..., description="原始剪辑策略JSON字符串")


class StrategyParseOutput(BaseModel):
    """策略解析节点输出"""
    edit_operations: List[Dict[str, Any]] = Field(default_factory=list, description="剪辑操作列表")
    hook_config: Dict[str, Any] = Field(default_factory=dict, description="钩子配置")
    title_suggestions: List[Dict[str, Any]] = Field(default_factory=list, description="标题建议")
    cover_config: Dict[str, Any] = Field(default_factory=dict, description="封面配置")
    audio_strategy: Dict[str, Any] = Field(default_factory=dict, description="音频策略")
    overall_strategy: Dict[str, Any] = Field(default_factory=dict, description="整体策略")
    parse_success: bool = Field(default=False, description="解析是否成功")
    error_message: str = Field(default="", description="错误信息")


# ==================== 素材加载节点 ====================
class MaterialLoadInput(BaseModel):
    """素材加载节点输入"""
    material_library: str = Field(default="~/Desktop/素材库", description="素材库路径")
    material_filename: Optional[str] = Field(default=None, description="指定素材文件名")


class MaterialLoadOutput(BaseModel):
    """素材加载节点输出"""
    load_success: bool = Field(default=False, description="加载是否成功")
    error_message: str = Field(default="", description="错误信息")
    material_path: str = Field(default="", description="素材文件路径（工作目录）")
    original_material_path: str = Field(default="", description="原始素材路径")
    material_info: Dict[str, Any] = Field(default_factory=dict, description="素材信息")


# ==================== 剪辑执行节点 ====================
class EditExecuteInput(BaseModel):
    """剪辑执行节点输入"""
    material_path: str = Field(..., description="素材文件路径")
    edit_operations: List[Dict[str, Any]] = Field(..., description="剪辑操作列表")
    hook_config: Dict[str, Any] = Field(default_factory=dict, description="钩子配置")
    audio_strategy: Dict[str, Any] = Field(default_factory=dict, description="音频策略")


class EditExecuteOutput(BaseModel):
    """剪辑执行节点输出"""
    output_path: str = Field(default="", description="输出文件路径")
    edit_log: List[str] = Field(default_factory=list, description="剪辑操作日志")
    success_operations: List[int] = Field(default_factory=list, description="成功的操作序号")
    failed_operations: List[int] = Field(default_factory=list, description="失败的操作序号")
    total_operations: int = Field(default=0, description="总操作数")
    error: str = Field(default="", description="错误信息")
    used_engine: str = Field(default="FFmpeg", description="使用的剪辑引擎: 剪映桌面版 或 FFmpeg")


# ==================== 成品输出节点 ====================
class OutputExportInput(BaseModel):
    """成品输出节点输入"""
    output_path: str = Field(..., description="剪辑输出路径")
    output_library: str = Field(default="~/Desktop/成品库", description="成品库路径")
    title_suggestions: List[Dict[str, Any]] = Field(default_factory=list, description="标题建议")
    cover_config: Dict[str, Any] = Field(default_factory=dict, description="封面配置")
    edit_log: List[str] = Field(default_factory=list, description="剪辑日志")
    success_count: int = Field(default=0, description="成功操作数")
    failed_count: int = Field(default=0, description="失败操作数")


class OutputExportOutput(BaseModel):
    """成品输出节点输出"""
    export_success: bool = Field(default=False, description="导出是否成功")
    error_message: str = Field(default="", description="错误信息")
    final_output_path: str = Field(default="", description="最终成品路径")
    metadata_path: str = Field(default="", description="元数据文件路径")
    report_path: str = Field(default="", description="审核报告路径")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="视频元数据")


# ==================== 错误记录节点 ====================
class ErrorRecordInput(BaseModel):
    """错误记录节点输入"""
    edit_log: List[str] = Field(default_factory=list, description="剪辑操作日志")
    material_path: str = Field(default="", description="素材路径")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    operation_types: Optional[List[str]] = Field(default=None, description="操作类型列表")
    revision_count: int = Field(default=0, description="当前返工次数")


class ErrorRecordOutput(BaseModel):
    """错误记录节点输出"""
    recorded: bool = Field(default=False, description="是否已记录")
    error_count: int = Field(default=0, description="错误数量")
    error_patterns: Dict[str, Any] = Field(default_factory=dict, description="错误模式分析")
    optimization_suggestions: List[str] = Field(default_factory=list, description="优化建议")
    need_rework: bool = Field(default=False, description="是否需要返工")
    rework_reason: str = Field(default="", description="返工原因")
    revision_count: int = Field(default=0, description="更新后的返工次数")


# ==================== 返工条件节点 ====================
class ReworkDecisionInput(BaseModel):
    """返工决策节点输入"""
    need_rework: bool = Field(..., description="是否需要返工")
    failed_count: int = Field(default=0, description="失败操作数")
    revision_count: int = Field(default=0, description="已返工次数")
    error_count: int = Field(default=0, description="错误数量")


class ReworkDecisionOutput(BaseModel):
    """返工决策节点输出"""
    should_rework: bool = Field(default=False, description="是否应该返工")
    max_revisions_reached: bool = Field(default=False, description="是否达到最大返工次数")
