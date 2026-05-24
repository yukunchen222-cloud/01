# 服装连锁AI记账助手 - 项目交接文档

## 一、项目概述

**项目名称**：服装连锁AI记账助手  
**核心功能**：通过语音/拍照/文件方式快速录入账目，AI自动识别意图和商品，生成经营报表和异常预警  
**技术栈**：Python 3.12 + LangGraph 1.0 + FastAPI + coze-coding-dev-sdk + Chart.js  

---

## 二、本地开发环境搭建

### 2.1 环境要求
- Python >= 3.12
- uv (Python包管理器)
- Git

### 2.2 克隆项目
```bash
git clone <仓库地址>
cd vibe-coding
```

### 2.3 安装依赖
```bash
# 安装uv (如未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
uv sync
```

### 2.4 启动服务
```bash
# 开发模式启动 (端口5000)
uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload

# 或使用脚本
bash scripts/local_run.sh
```

### 2.5 访问地址
| 页面 | URL | 说明 |
|------|-----|------|
| 登录页 | http://localhost:5000/login.html | 统一入口 |
| 老板端 | http://localhost:5000/ | PC端看板+管理 |
| 店长端 | http://localhost:5000/mobile.html | 移动端录入 |
| 商品管理 | http://localhost:5000/products.html | 商品CRUD |

### 2.6 测试账号
| 用户名 | 密码 | 角色 | 权限 |
|--------|------|------|------|
| boss | 123456 | 老板(owner) | 全部功能+审核权 |
| manager1 | 123456 | 店长(manager) | 单店数据+语音/拍照 |
| accountant | 123456 | 会计(accountant) | 仅查看+报告导出 |

---

## 三、项目结构详解

```
├── config/                    # 大模型配置文件 (JSON)
│   ├── nlu_extraction_cfg.json    # NLU意图识别配置
│   ├── anomaly_detection_cfg.json # 异常检测配置
│   ├── report_generation_cfg.json # 报告生成配置
│   └── report_export_cfg.json     # 报告导出配置
│
├── data/                      # 数据存储 (JSON文件)
│   ├── organizations.json     # 组织数据
│   ├── users.json             # 用户数据
│   ├── stores.json            # 门店数据
│   ├── products.json          # 商品库数据
│   └── records.json           # 交易记录(核心数据)
│
├── assets/                    # 前端静态资源
│   ├── index.html             # 老板端页面
│   ├── mobile.html            # 店长端页面
│   ├── login.html             # 登录页
│   ├── products.html          # 商品管理页
│   ├── app.js                 # 老板端交互脚本
│   └── styles.css             # 全局样式
│
├── src/                       # 后端源码
│   ├── main.py                # FastAPI主应用 (路由+API)
│   ├── utils/
│   │   ├── auth.py            # JWT认证模块
│   │   ├── feishu_notify.py   # 飞书消息推送
│   │   ├── product_knowledge.py # 商品知识库
│   │   └── file/file.py       # 文件处理工具(FileOps)
│   │
│   └── graphs/                # LangGraph工作流
│       ├── state.py           # 全局状态+节点出入参定义
│       ├── graph.py           # 主图编排(DAG)
│       └── nodes/             # 各节点实现
│           ├── asr_recognition_node.py   # ASR语音识别
│           ├── ocr_recognition_node.py   # OCR图片/PDF识别
│           ├── nlu_extraction_node.py    # NLU意图提取(Agent)
│           ├── data_validation_node.py   # 数据校验
│           ├── data_aggregation_node.py  # 数据聚合统计
│           ├── anomaly_detection_node.py # 异常检测(Agent)
│           ├── report_generation_node.py # 报告生成
│           └── report_export_node.py     # 多格式导出
│
└── pyproject.toml             # 项目依赖配置
```

---

## 四、核心数据流

```
用户输入(语音/图片/PDF/文本)
    ↓
前端 → API接口 → LangGraph工作流
    ↓
[ASR/OCR] → 文本 → [NLU] → 结构化数据
    ↓
[数据校验] → [数据聚合] → [异常检测] → [报告生成]
    ↓
结果返回前端 → 确认提交 → 保存到records.json
```

### 4.1 API端点清单

| 分类 | 端点 | 方法 | 说明 |
|------|------|------|------|
| 认证 | `/api/auth/login` | POST | 登录获取Token |
| 认证 | `/api/auth/verify` | POST | 验证Token |
| 录入 | `/api/voice/base64` | POST | 语音报账(base64→ASR→NLU) |
| 录入 | `/api/image` | POST | 图片识别(file_url→OCR→NLU) |
| 录入 | `/api/document` | POST | PDF识别(file_url→提取文本→NLU) |
| 录入 | `/api/upload` | POST | 文件上传到对象存储 |
| 看板 | `/api/dashboard` | GET | 经营数据统计(period/store_id) |
| 记录 | `/api/records` | GET | 历史记录(分页+筛选) |
| 记录 | `/api/records` | POST | 创建记录 |
| 记录 | `/api/records/{id}` | PUT | 编辑记录 |
| 审核 | `/api/records/{id}/approve` | PUT | 审核通过 |
| 审核 | `/api/records/{id}/reject` | PUT | 审核驳回 |
| 审核 | `/api/reviews` | GET | 待审核列表 |
| 报告 | `/api/report` | POST | 生成Markdown报告 |
| 报告 | `/api/report/export` | POST | 导出PDF/Word/Excel |
| 推送 | `/api/notify/feishu` | POST | 飞书消息推送 |
| 商品 | `/api/products` | GET/POST | 商品CRUD |
| 知识库 | `/api/knowledge/search` | POST | 商品知识库搜索 |
| 门店 | `/api/stores` | GET | 门店列表 |

---

## 五、当前已知问题与待完善清单

> ✅ = 已修复 | ⚠️ = 需要注意 | ❌ = 待修复

### 🔴 P0 - 核心功能不可用

| 编号 | 状态 | 问题 | 修复说明 |
|------|------|------|---------|
| P0-1 | ⚠️ | 语音录音后base64上传到`/api/voice/base64`，ASR SDK可能对webm格式兼容不佳 | 前端已优先使用`audio/mp4`格式录制，后端可根据需要转码 |
| P0-2 | ✅ | 数据看板数据聚合 | `/api/dashboard`已直接从`data/records.json`读取真实数据；`data_aggregation_node`也已修复字段名匹配records.json格式 |
| P0-3 | ✅ | 前端看板图表(Chart.js)不显示 | 已添加Chart.js CDN、营收趋势柱状图、品类占比饼图，空数据时Canvas显示提示文字 |

### 🟡 P1 - 功能不完整

| 编号 | 状态 | 问题 | 修复说明 |
|------|------|------|---------|
| P1-1 | ✅ | 审核通过/驳回后列表不刷新 | `approveReview()`/`rejectReview()`已调用`loadReviewData()`刷新列表 |
| P1-2 | ✅ | 日期筛选默认值为当月 | `initDateFilter()`已设置`#dateFilter`默认值为当月第一天 |
| P1-3 | ✅ | 报告导出按钮对接API | `exportReport()`已调用`POST /api/report/export`并触发下载 |
| P1-4 | ✅ | 飞书推送按钮对接API | `sendReportToFeishu()`已调用`POST /api/notify/feishu` |
| P1-5 | ✅ | 商品管理CRUD对接后端 | `products.html`已通过PUT/DELETE调用后端API |
| P1-6 | ✅ | 多租户数据隔离 | `/api/records`和`/api/dashboard`已根据JWT中的org_id过滤 |
| P1-7 | ✅ | 会计端显示过滤 | `checkAuth()`已根据role=accountant隐藏审核/录入导航项 |

### 🟢 P2 - 体验优化

| 编号 | 状态 | 问题 | 修复说明 |
|------|------|------|---------|
| P2-1 | ✅ | 录音和拍照无实时反馈 | mobile.html已添加波形动画(waveform)、加载spinner、图片预览 |
| P2-2 | ✅ | 看板无数据时无提示 | 图表Canvas在空数据时绘制"暂无数据"文字 |
| P2-3 | ⚠️ | 门店对比柱状图颜色区分 | Chart.js已使用多种区分色，可根据需要调整 |
| P2-4 | ⚠️ | 确认提交模态框商品详情 | 可展示SKU、品类、成本价，按需增强 |
| P2-5 | ✅ | 搜索/筛选无loading状态 | 已使用`showLoading()`/`hideLoading()`覆盖层，移动端有spinner动画 |

### 本次更新 (2026-05-24) 额外修复

| 修复项 | 说明 |
|--------|------|
| `/api/stores`真实数据 | 从硬编码5个门店改为读取`stores.json`，支持org_id权限过滤 |
| 文件路径修复 | `auth.py`和`main.py`现在自动检测项目根目录，不再依赖`COZE_WORKSPACE_PATH`环境变量 |
| Windows兼容 | `pyproject.toml`移除仅Linux可用的桌面自动化依赖(pyautogui/pywinauto/playwright/PyGObject) |
| Chart.js集成 | index.html引入Chart.js CDN，app.js添加trendChart和categoryChart渲染

---

## 六、关键代码逻辑说明

### 6.1 语音录入流程
```
前端录音(MediaRecorder) → base64编码 → POST /api/voice/base64
→ 后端用coze-coding-dev-sdk的AudioClient做ASR → 得到文本
→ 调用LangGraph工作流(NLU→聚合→检测→报告) → 返回结果
→ 前端弹窗确认 → POST /api/records 保存记录
```

### 6.2 NLU意图识别
NLU节点从`config/nlu_extraction_cfg.json`读取模型配置，使用Jinja2渲染prompt。
支持的意图类型：`revenue`(销售)、`expense`(支出)、`purchase`(进货)、`return`(退货)、`inventory`(盘点)、`query`(查询)

### 6.3 数据存储
当前使用JSON文件存储(`data/`目录)，适合MVP阶段。生产环境建议迁移到PostgreSQL。
- `records.json`：核心交易记录，每条记录包含id、type、items、total_amount、status、store_id等
- `products.json`：商品库，含SKU、成本价、品类
- `users.json`：用户信息，含角色和所属门店

### 6.4 权限控制
- JWT Token认证，24小时有效期
- 角色权限：owner(全部)、manager(单店)、accountant(只读)
- 前端通过localStorage中的user.role控制UI显示
- 后端`/api/reviews`根据角色返回can_review字段

---

## 七、外部SDK依赖

| SDK | 用途 | 文档 |
|-----|------|------|
| coze-coding-dev-sdk | LLM/ASR/TTS/文件上传/文档生成 | 项目内置 |
| langchain + langgraph | 工作流编排 | https://python.langchain.com/ |
| fastapi | Web框架 | https://fastapi.tiangolo.com/ |
| chart.js | 前端图表 | https://www.chartjs.org/ |

---

## 八、快速上手任务

### 新开发者建议从以下任务入手：

1. **了解数据看板** (`/api/dashboard`): 阅读该API的实现，理解数据聚合逻辑
2. **增强图表** (P2-3): 在`app.js`的`renderTrendChart`中调整Chart.js配置(颜色、动画、交互)
3. **增强确认模态框** (P2-4): 在`app.js`的`showRecognitionResult`中展示更多商品详情(SKU、品类)
4. **添加移动端历史页**: 在`mobile.html`添加完整的历史记录查看功能
5. **迁移数据库**: 将`data/*.json`迁移到PostgreSQL（生产环境建议）

---

*文档生成时间：2025-05-24 | 最后更新：2026-05-24*
