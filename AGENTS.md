# AI短剧推广自动剪辑工作流

## 项目概述
- **名称**: AI短剧推广自动剪辑工作流
- **功能**: 自动分析短剧素材，搜索同类爆款视频，学习爆款特征，生成剪辑策略，并审核成品质量

## 核心流程

```
素材输入 → 素材分析 → 爆款搜索 → 爆款分析 → 策略生成 → [人工确认] → 剪辑 → 审核 → 发布
```

## 节点清单

| 节点名 | 文件位置 | 类型 | 功能描述 | 分支逻辑 | 配置文件 |
|-------|---------|------|---------|---------|---------|
| material_analyze | `nodes/material_analyze_node.py` | agent | 分析素材视频，提取关键帧、字幕、内容摘要 | - | `config/material_analyze_llm_cfg.json` |
| viral_search | `nodes/viral_search_node.py` | task | 搜索抖音/快手同类爆款视频 | - | - |
| viral_analyze | `nodes/viral_analyze_node.py` | agent | 深度分析爆款视频，提取钩子、标题、封面模式 | - | `config/viral_analyze_llm_cfg.json` |
| edit_strategy | `nodes/edit_strategy_node.py` | agent | 生成详细剪辑策略文档 | - | `config/edit_strategy_llm_cfg.json` |
| review_compare | `nodes/review_compare_node.py` | agent | 审核剪辑成品，对比爆款标准 | 通过/返工 | `config/review_llm_cfg.json` |

**类型说明**: task(任务节点) / agent(大模型节点) / condition(条件分支) / looparray(列表循环) / loopcond(条件循环)

## 技能使用

### 大语言模型 (LLM)
- **素材分析**: 使用 `doubao-seed-1-8-251228` 多模态模型理解视频内容
- **爆款分析**: 使用 `deepseek-v3-2-251201` 深度推理分析爆款特征
- **策略生成**: 使用 `deepseek-v3-2-251201` 生成剪辑策略
- **审核比对**: 使用 `doubao-seed-1-8-251228` 评估视频质量

### Web搜索
- 搜索抖音、快手平台的爆款短剧视频
- 限定站点：douyin.com, kuaishou.com
- 时间范围：最近一周

### 视频处理
- 关键帧提取：提取视频关键帧用于画面分析
- 字幕生成：从视频中提取或生成字幕

## 配置文件

### 大模型配置文件
| 配置文件 | 用途 | 模型 |
|---------|-----|------|
| `config/material_analyze_llm_cfg.json` | 素材视频分析 | doubao-seed-1-8-251228 |
| `config/viral_analyze_llm_cfg.json` | 爆款内容分析 | deepseek-v3-2-251201 |
| `config/edit_strategy_llm_cfg.json` | 剪辑策略生成 | deepseek-v3-2-251201 |
| `config/review_llm_cfg.json` | 审核比对 | doubao-seed-1-8-251228 |

## 数据流

```
GraphInput(material_video, drama_type)
    ↓
MaterialAnalyzeOutput(material_summary, keyframes, subtitle, keywords)
    ↓
ViralSearchOutput(viral_videos, search_summary)
    ↓
ViralAnalyzeOutput(viral_analysis, hook_points, title_patterns, cover_patterns)
    ↓
EditStrategyOutput(edit_strategy, hook_strategy, cut_points, title, cover_desc)
    ↓
[人工确认点] ← 等待用户确认策略
    ↓
GraphOutput(edit_strategy, strategy_confirmed, viral_analysis)
```

## 人工确认点

### 确认点1: 剪辑策略确认
- **位置**: 策略生成之后
- **内容**: 审核生成的剪辑策略文档
- **操作**: 用户确认策略后，工作流继续执行

### 确认点2: 素材输入
- **位置**: 工作流开始
- **内容**: 用户指定要剪辑的素材视频
- **操作**: 将素材放入指定文件夹，工作流自动读取

## 后续开发计划

### 剪辑Agent (待开发)
- 功能：自动操作剪映进行视频剪辑
- 技术栈：pyautogui (GUI自动化)、ffmpeg (视频处理)
- 文件夹：素材库 → 剪辑成品库

### 投放Agent (待开发)
- 功能：爬取投放时间、规划发布计划、自动发布
- 技术栈：Playwright/Selenium (浏览器自动化)、定时任务
- 发布平台：抖音创作者平台（网页版）

## 使用方式

### 启动工作流
```python
from graphs.graph import main_graph
from graphs.state import GraphInput
from utils.file.file import File

# 准备输入
input_data = GraphInput(
    material_video=File(url="视频URL或本地路径"),
    drama_type="都市情感"
)

# 执行工作流
result = main_graph.invoke(input_data)

# 获取剪辑策略
edit_strategy = result.get("edit_strategy", {})
```

### 测试运行
```bash
# 使用测试数据运行
python -m src.main
```
