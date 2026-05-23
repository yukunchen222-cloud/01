# AI短剧推广自动剪辑工作流

## 项目概述
- **名称**: AI短剧推广自动剪辑工作流
- **功能**: 自动分析短剧素材，搜索同类爆款视频，学习爆款特征，生成剪辑策略，执行剪辑操作，并审核成品质量

## 🚀 快速开始

### 1. 在本地电脑桌面创建文件夹
```
桌面/素材库/  ← 放入原始视频
桌面/成品库/  ← 剪辑完成的视频
```

### 2. 配置路径
编辑 `config/workflow_config.yaml`，填入您的实际路径

### 3. 运行
```bash
python run_workflow.py
```

详细说明请查看 [USAGE.md](USAGE.md)

## 核心流程

```
素材输入 → 素材分析 → 爆款搜索 → 爆款分析 → 策略生成 → [人工确认] → 剪辑执行 → 成品输出 → 审核
```

## 素材库设置

- **素材库路径**: `~/Desktop/素材库/` - 放入需要剪辑的原始素材视频
- **成品库路径**: `~/Desktop/成品库/` - 剪辑完成的视频自动输出到这里

## 节点清单

### 爆款Agent节点

| 节点名 | 文件位置 | 类型 | 功能描述 | 配置文件 |
|-------|---------|------|---------|---------|
| video_classify | `nodes/video_classify_node.py` | agent | 自动识别视频内容，判断短剧类型 | `config/video_classify_llm_cfg.json` |
| material_analyze | `nodes/material_analyze_node.py` | agent | 分析素材视频，提取关键帧、字幕、内容摘要 | `config/material_analyze_llm_cfg.json` |
| viral_search | `nodes/viral_search_node.py` | task | 搜索抖音/快手同类爆款视频 | - |
| viral_analyze | `nodes/viral_analyze_node.py` | agent | 深度分析爆款视频，提取钩子、标题、封面模式 | `config/viral_analyze_llm_cfg.json` |
| edit_strategy | `nodes/edit_strategy_node.py` | agent | 生成详细剪辑策略文档 | `config/edit_strategy_llm_cfg.json` |
| review_compare | `nodes/review_compare_node.py` | agent | 审核剪辑成品，对比爆款标准 | `config/review_llm_cfg.json` |

### 剪辑Agent节点

| 节点名 | 文件位置 | 类型 | 功能描述 | 配置文件 |
|-------|---------|------|---------|---------|
| strategy_parse | `nodes/strategy_parse_node.py` | agent | 解析剪辑策略JSON，提取可执行操作序列 | `config/strategy_parse_llm_cfg.json` |
| material_load | `nodes/material_load_node.py` | task | 从素材库加载视频文件 | - |
| edit_execute | `nodes/edit_execute_node.py` | task | 执行剪辑操作（剪切、慢动作、特效等） | - |
| output_export | `nodes/output_export_node.py` | task | 输出成品到成品库，生成元数据 | - |
| error_record | `nodes/error_record_node.py` | task | 记录错误用于优化和返工决策 | - |

**类型说明**: task(任务节点) / agent(大模型节点) / condition(条件分支)

## 子图清单

| 子图名 | 文件位置 | 功能描述 | 被调用节点 |
|-------|---------|------|---------|
| edit_graph | `graphs/edit_graph.py` | 剪辑Agent工作流 | 独立运行 |

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
- FFmpeg剪辑：执行视频剪切、慢动作、特效等操作

## 配置文件

| 配置文件 | 用途 | 模型 |
|---------|-----|------|
| `config/material_analyze_llm_cfg.json` | 素材视频分析 | doubao-seed-1-8-251228 |
| `config/viral_analyze_llm_cfg.json` | 爆款内容分析 | deepseek-v3-2-251201 |
| `config/edit_strategy_llm_cfg.json` | 剪辑策略生成 | deepseek-v3-2-251201 |
| `config/review_llm_cfg.json` | 审核比对 | doubao-seed-1-8-251228 |
| `config/strategy_parse_llm_cfg.json` | 策略解析 | deepseek-v3-2-251201 |

## 数据流

### 爆款Agent数据流
```
GraphInput(material_video, drama_type)
    ↓
MaterialAnalyzeOutput(material_summary, keyframes, subtitle, keywords)
    ↓
ViralSearchOutput(viral_videos, search_summary)
    ↓
ViralAnalyzeOutput(viral_analysis, hook_points, title_patterns, cover_patterns)
    ↓
EditStrategyOutput(edit_strategy, hook_strategy, cut_points)
    ↓
[人工确认点] ← 等待用户确认策略
    ↓
GraphOutput(edit_strategy, strategy_confirmed, viral_analysis)
```

### 剪辑Agent数据流
```
EditGraphInput(raw_strategy, material_library, material_filename, output_library)
    ↓
StrategyParseOutput(edit_operations, hook_config, title_suggestions, cover_config)
    ↓
MaterialLoadOutput(material_path, material_info)
    ↓
EditExecuteOutput(output_path, edit_log, success_count, failed_count)
    ↓
OutputExportOutput(final_output_path, metadata)
    ↓
ErrorRecordOutput(need_rework, error_patterns, optimization_suggestions)
    ↓
EditGraphOutput(final_output_path, export_success, metadata)
```

## 人工确认点

### 确认点1: 剪辑策略确认
- **位置**: 爆款Agent策略生成之后
- **内容**: 审核生成的剪辑策略文档
- **操作**: 用户确认策略后，工作流继续执行剪辑

### 确认点2: 素材输入
- **位置**: 工作流开始
- **内容**: 用户指定要剪辑的素材视频
- **操作**: 将素材放入素材库文件夹，工作流自动读取

## 返工机制

当剪辑出现错误时：
1. 错误记录节点自动记录错误类型和模式
2. 分析错误模式，生成优化建议
3. 决定是否需要返工（最多3次）
4. 返工时跳转到剪辑执行节点重新执行

## 使用方式

### 1. 准备素材
```bash
# 将视频素材放入素材库
cp your_video.mp4 ~/Desktop/素材库/
```

### 2. 运行爆款Agent（获取剪辑策略）
```python
from graphs.graph import main_graph
from graphs.state import GraphInput
from utils.file.file import File

result = main_graph.invoke({
    "material_video": {"url": "your_video_url", "file_type": "video"},
    "drama_type": "都市情感"
})

print(result["edit_strategy"])
```

### 3. 运行剪辑Agent
```python
from graphs.edit_graph import edit_graph

result = edit_graph.invoke({
    "raw_strategy": strategy_json_string,
    "material_library": "~/Desktop/素材库",
    "material_filename": "your_video.mp4",
    "output_library": "~/Desktop/成品库"
})

print(f"输出文件: {result['final_output_path']}")
```

## 后续开发计划

### 投放Agent (待开发)
- 功能：爬取投放时间、规划发布计划、自动发布
- 技术栈：Playwright/Selenium (浏览器自动化)、定时任务
- 发布平台：抖音创作者平台（网页版）

### 剪映桌面版集成 (待完善)
- 当前使用FFmpeg进行视频处理
- 可扩展为使用pyautogui控制剪映桌面版
- 支持更丰富的特效和转场

## 测试记录

### 2026-05-23 测试结果
- ✓ 爆款Agent编译通过
- ✓ 剪辑Agent编译通过
- ✓ 剪辑执行成功
- ✓ 成品输出到 `~/Desktop/成品库/edited_20260523_163820.mp4`
- ✓ 元数据和审核报告生成成功
