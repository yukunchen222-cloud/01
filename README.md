# 服装连锁AI记账助手

基于多Agent协作的服装连锁店智能记账系统，支持语音报账、拍照录入、数据看板、异常预警、报告导出。

## 核心功能

### 🎤 语音报账（店长端）
- 语音识别(ASR) → NLU意图提取 → 自动归类（销售/进货/退货/支出/盘点）
- 商品知识库增强，自动匹配SKU和成本价

### 📷 拍照录入
- 支持JPG/PNG图片OCR识别
- 支持PDF文件文本提取
- 多模态LLM提取结构化数据

### 📊 数据看板（老板端）
- 营收/成本/毛利/净利润实时统计
- 门店对比、品类分布、日趋势图表
- 日期筛选（日/周/月/自定义）

### ⚠️ 异常预警
- 毛利率异常检测
- 营收偏离预警
- LLM语义分析生成洞察建议

### 📋 审核中心
- 低置信度记录自动标记待审核
- 老板审核通过/驳回
- 审核状态追踪

### 📄 报告导出
- 支持PDF/Word/Excel多格式导出
- 飞书消息推送（日报/预警）
- 邮件报告发送

## 用户角色

| 角色 | 权限 |
|------|------|
| 老板(owner) | 全部功能 + 审核 + 全店数据 |
| 店长(manager) | 单店数据 + 语音/拍照录入 |
| 会计(accountant) | 查看数据 + 报告导出 |

## 快速开始

```bash
# 安装依赖
uv sync

# 启动服务
uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload
```

## 测试账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| boss | 123456 | 老板 |
| manager1 | 123456 | 店长 |
| accountant | 123456 | 会计 |

## 技术栈

- **后端**: FastAPI + LangGraph 1.0
- **AI**: 豆包大模型(NLU/异常检测) + ASR语音识别 + 多模态OCR
- **前端**: 原生HTML/CSS/JS + Chart.js
- **数据**: JSON文件存储（MVP阶段）
- **鉴权**: JWT Token

## 项目结构

```
src/
├── main.py              # FastAPI主应用 + API路由
├── graphs/
│   ├── graph.py         # 工作流编排（DAG）
│   ├── state.py         # 状态定义
│   └── nodes/           # 工作流节点
│       ├── asr_recognition_node.py
│       ├── ocr_recognition_node.py
│       ├── nlu_extraction_node.py
│       ├── data_validation_node.py
│       ├── data_aggregation_node.py
│       ├── anomaly_detection_node.py
│       └── report_generation_node.py
├── utils/
│   ├── auth.py          # JWT鉴权
│   ├── feishu_notify.py # 飞书推送
│   └── product_knowledge.py # 商品知识库
├── tools/               # 工具定义
└── storage/             # 存储层
assets/
├── index.html           # 老板端（PC）
├── mobile.html          # 店长端（移动）
├── login.html           # 登录页
├── products.html        # 商品管理
├── app.js               # 前端逻辑
└── styles.css           # 样式
config/                  # LLM配置
data/                    # 数据存储（JSON）
```
