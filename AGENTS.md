# AI短剧推广自动剪辑工作流

## 项目概述
- **名称**: AI短剧推广自动剪辑工作流
- **功能**: 自动扫描素材库，识别所有视频内容，批量处理剪辑

## 🚀 快速开始

### 1. 在本地电脑桌面创建文件夹
```
C:\Users\你的用户名\Desktop\素材库\  ← 放入原始视频（支持多个）
C:\Users\你的用户名\Desktop\成品库\  ← 剪辑完成的视频
```

### 2. 配置路径
编辑 `config/workflow_config.yaml`，填入您的实际路径

### 3. 运行
```bash
python run_workflow.py
```

### 4. 选择处理模式
- **模式1: 全部自动处理** - 自动扫描素材库所有视频，自动识别+剪辑，无需人工确认
- **模式2: 逐个处理** - 每个视频需要人工确认类型和剪辑
- **模式3: 选择单个视频** - 选择一个视频处理
- **模式4: 测试模式** - 使用在线测试视频

详细说明请查看 [USAGE.md](USAGE.md)

## 核心流程

```
扫描素材库 → 自动识别类型 → 爆款搜索 → 策略生成 → 【连接剪映执行剪辑】 → 成品输出
```

## ⭐ 剪映网页版自动化剪辑（核心功能）

剪辑Agent支持**自动连接剪映网页版**进行真实剪辑操作：

### 剪映网页版优势
- ✅ 无需安装桌面版软件
- ✅ 自动登录抖音账号（首次需手动登录）
- ✅ 剪辑完成后可直接发布到抖音
- ✅ 跨平台支持（Windows/Mac/Linux）

### 支持的剪辑操作

| 操作 | 说明 | 实现方式 |
|------|------|---------|
| 导入素材 | 上传视频到剪映 | 点击上传按钮 |
| 分割片段 | 在指定时间点切分视频 | 点击分割按钮 |
| 变速处理 | 慢动作/快进效果 | 右键菜单→变速 |
| 添加字幕 | 自动生成文字层 | 字幕工具 |
| 导出视频 | 指定格式和路径 | 点击导出按钮 |

### 剪辑引擎选择

| 引擎 | 优先级 | 条件 | 说明 |
|------|--------|------|------|
| **剪映桌面版** | 优先 | 已安装剪映 | 自动打开剪映，执行剪辑操作 |
| FFmpeg | 备用 | 剪映未安装 | 命令行处理视频 |

### 剪映安装检测

工作流会自动检测以下路径：
- `C:\Program Files\JianyingPro\JianyingPro.exe`
- `C:\Program Files (x86)\JianyingPro\JianyingPro.exe`
- `%LOCALAPPDATA%\JianyingPro\JianyingPro.exe`
- 或自定义路径

### 使用剪映自动化

1. **确保剪映已安装**在上述路径之一
2. **安装自动化依赖**：
```bash
pip install pyautogui pywinauto
```
3. **运行工作流**时会自动检测并连接剪映

## 批量处理功能

工作流会自动：
1. **扫描** - 递归扫描素材库内所有视频文件
2. **识别** - 自动识别每个视频的短剧类型
3. **处理** - 批量生成剪辑策略并执行剪辑
4. **输出** - 所有成品输出到成品库

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

---

# 服装连锁AI记账助手工作流

## 项目概述
- **名称**: 服装连锁AI记账助手
- **功能**: 智能记账助手，支持语音报账、拍照录入、看板查询、异常预警、报告生成

## 核心功能

### 店长端
- **语音报账**: 通过语音描述交易信息，自动识别并录入
- **拍照录入**: 拍摄单据照片，OCR识别后自动提取数据
- **历史记录**: 查看本店历史账目记录

### 老板端
- **数据看板**: 实时查看各门店经营数据
- **门店对比**: 多门店业绩对比分析
- **款式分析**: 畅销/滞销款式分析
- **异常预警**: 自动检测异常数据并预警
- **月报导出**: 自动生成月度经营报告

## 工作流架构

```
                    ┌─────────────────┐
                    │   GraphInput    │
                    │ (input_type,    │
                    │  audio_file/    │
                    │  image_file/    │
                    │  query_type)    │
                    └────────┬────────┘
                             │
                  ┌──────────┴──────────┐
                  │ route_input_type    │
                  │   (条件分支)         │
                  └──────────┬──────────┘
                             │
    ┌────────────────────────┼────────────────────────┐
    │                        │                        │
    ▼                        ▼                        ▼
┌─────────┐           ┌─────────┐             ┌──────────┐
│ 语音报账 │           │ 拍照录入 │             │看板查询  │
│ 分支    │           │ 分支    │             │  分支    │
└────┬────┘           └────┬────┘             └────┬─────┘
     │                     │                       │
     ▼                     ▼                       │
┌─────────┐           ┌─────────┐                 │
│ ASR识别 │           │ OCR识别 │                 │
└────┬────┘           └────┬────┘                 │
     │                     │                       │
     └─────────┬───────────┘                       │
               │                                   │
               ▼                                   │
        ┌────────────┐                             │
        │ NLU数据提取│                             │
        └─────┬──────┘                             │
              │                                    │
              ▼                                    │
        ┌────────────┐                             │
        │ 数据校验   │                             │
        └─────┬──────┘                             │
              │                                    │
              └────────────────────────────────────┘
                                                   │
                                                   ▼
                                            ┌──────────┐
                                            │ 数据聚合 │
                                            └────┬─────┘
                                                 │
                                                 ▼
                                            ┌──────────┐
                                            │ 异常检测 │
                                            └────┬─────┘
                                                 │
                                                 ▼
                                            ┌──────────┐
                                            │ 报告生成 │
                                            └────┬─────┘
                                                 │
                                                 ▼
                                            ┌──────────┐
                                            │GraphOutput│
                                            └──────────┘
```

## 节点清单

| 节点名 | 文件位置 | 类型 | 功能描述 | 配置文件 |
|-------|---------|------|---------|---------|
| asr_recognition | `nodes/asr_recognition_node.py` | task | 语音识别，将语音转换为文字 | - |
| ocr_recognition | `nodes/ocr_recognition_node.py` | agent | 图片OCR识别，提取账目信息 | - |
| nlu_extraction | `nodes/nlu_extraction_node.py` | agent | NLU数据提取，从文本提取结构化数据 | `config/nlu_extraction_cfg.json` |
| data_validation | `nodes/data_validation_node.py` | task | 数据校验，验证数据完整性 | - |
| data_aggregation | `nodes/data_aggregation_node.py` | task | 数据聚合，生成看板统计 | - |
| anomaly_detection | `nodes/anomaly_detection_node.py` | agent | 异常检测，识别异常数据 | `config/anomaly_detection_cfg.json` |
| report_generation | `nodes/report_generation_node.py` | agent | 报告生成，生成经营分析报告 | `config/report_generation_cfg.json` |
| route_input_type | `graph.py` | condition | 路由输入类型 | - |

**类型说明**: task(任务节点) / agent(大模型节点) / condition(条件分支)

## 技能使用

### 大语言模型 (LLM)
- **OCR识别**: 使用多模态模型 `doubao-seed-2-0-lite-260215` 识别图片中的文字
- **NLU提取**: 使用 `doubao-seed-2-0-lite-260215` 从文本提取结构化数据
- **异常检测**: 使用 `doubao-seed-2-0-mini-260215` 智能分析异常
- **报告生成**: 使用 `doubao-seed-2-0-lite-260215` 生成经营报告

### 语音识别 (ASR)
- 将语音文件转换为文字，支持多种音频格式

### 对象存储
- 生成的报告文件可上传到对象存储

## 配置文件

| 配置文件 | 用途 | 模型 |
|---------|-----|------|
| `config/nlu_extraction_cfg.json` | NLU数据提取 | doubao-seed-2-0-lite-260215 |
| `config/anomaly_detection_cfg.json` | 异常检测 | doubao-seed-2-0-mini-260215 |
| `config/report_generation_cfg.json` | 报告生成 | doubao-seed-2-0-lite-260215 |

## 使用示例

### 1. 看板查询
```python
from graphs.graph import main_graph

result = main_graph.invoke({
    "input_type": "query",
    "query_type": "month"  # day/month/year
})

print(result["dashboard_data"])
print(result["report_url"])
```

### 2. 语音报账
```python
from graphs.graph import main_graph
from utils.file.file import File

result = main_graph.invoke({
    "input_type": "voice",
    "audio_file": {"url": "audio_url", "file_type": "audio"},
    "store_id": "store_001",
    "store_name": "中山路店"
})

print(result["report_summary"])
```

### 3. 拍照录入
```python
from graphs.graph import main_graph
from utils.file.file import File

result = main_graph.invoke({
    "input_type": "image",
    "image_file": {"url": "image_url", "file_type": "image"},
    "store_id": "store_001",
    "store_name": "中山路店"
})

print(result["dashboard_data"])
```

## 数据结构

### GraphInput
```python
{
    "input_type": "voice" | "image" | "query",  # 输入类型
    "audio_file": File,  # 语音文件（voice模式）
    "image_file": File,  # 图片文件（image模式）
    "query_type": "day" | "month" | "year",  # 查询类型
    "store_id": str,  # 门店ID
    "store_name": str  # 门店名称
}
```

### GraphOutput
```python
{
    "dashboard_data": dict,  # 看板数据
    "anomaly_alerts": list,  # 异常预警列表
    "report_url": str,  # 生成的报告URL
    "report_summary": str  # 报告摘要
}
```

## 后续开发计划

- [ ] 接入真实数据库存储账目记录
- [ ] 添加用户认证和权限管理
- [ ] 支持更多图表类型的数据看板
- [ ] 集成消息推送（飞书/企业微信）通知异常预警

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
