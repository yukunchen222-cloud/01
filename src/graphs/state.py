"""
爆款Agent状态定义
定义工作流的全局状态、图的输入输出、各节点的输入输出
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from utils.file.file import File


# ==================== 全局状态定义 ====================
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
