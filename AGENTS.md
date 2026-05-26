# 服装连锁AI记账助手

## 项目概述
- **名称**: 服装连锁AI记账助手
- **功能**: 面向服装连锁店的智能记账系统，支持语音报账、拍照录入、数据看板、异常预警、多格式报告导出、飞书消息推送等功能
- **数据库**: asyncpg 异步连接池（PostgreSQL）

## 用户角色
| 角色 | 权限 | 默认账号 | 密码 |
|------|------|---------|------|
| 老板(owner) | 全部功能、多门店数据 | boss | 123456 |
| 店长(manager) | 单店数据、语音/拍照录入 | manager1/manager2 | 123456 |
| 会计(accountant) | 数据查看、报表导出 | accountant | 123456 |

## 核心功能
1. **语音报账**: 说一句话自动记账，支持ASR语音识别，智能库存校验与自动扣减
2. **拍照录入**: 拍单据自动识别入库，支持OCR图片识别
3. **数据看板**: 实时营收、毛利、趋势分析
4. **异常预警**: 毛利率异常、营收偏离检测
5. **报告生成**: 自动生成经营报告，支持PDF/Word/Excel多格式导出
6. **商品管理**: SKU管理、库存预警、多店铺商品管理
7. **飞书通知**: 异常预警、日报推送到飞书群
8. **知识库增强**: 商品知识库提升NLU识别准确率
9. **多店铺支持**: 商品库按店铺筛选，每家店独立库存管理

## 节点清单

| 节点名 | 文件位置 | 类型 | 功能描述 | 配置文件 |
|-------|---------|------|---------|---------|
| entry_router | `graph.py` | task | 入口路由，按input_type透传数据 | - |
| asr_recognition | `nodes/asr_recognition_node.py` | task | ASR语音识别，将音频转为文字 | - |
| ocr_recognition | `nodes/ocr_recognition_node.py` | task | OCR图片识别，提取图片中的账目信息 | - |
| nlu_extraction | `nodes/nlu_extraction_node.py` | agent | NLU意图识别，提取结构化数据，支持知识库增强 | `config/nlu_extraction_cfg.json` |
| data_validation | `nodes/data_validation_node.py` | task | 数据校验，验证提取的数据完整性 | - |
| data_aggregation | `nodes/data_aggregation_node.py` | task | 数据聚合，计算营收/成本/毛利 | - |
| anomaly_detection | `nodes/anomaly_detection_node.py` | agent | 异常检测，检测毛利率/营收异常 | `config/anomaly_detection_cfg.json` |
| report_generation | `nodes/report_generation_node.py` | task | 报告生成，生成Markdown格式经营分析报告 | - |
| report_export | `nodes/report_export_node.py` | task | 报告导出，支持PDF/DOCX/XLSX多格式 | - |
| route_input_type | `graph.py` | condition | 输入类型路由(voice→ASR, image→OCR, query→聚合) | - |

## 数据库架构 (asyncpg)

### 连接池
- **文件**: `src/utils/db_pool.py`
- **单例模式**: 全局一个 asyncpg.Pool，min=5, max=20
- **生命周期**: FastAPI startup 预热、shutdown 关闭

### 数据访问层
- **文件**: `src/storage/database/repository.py`
- **全部异步**: 所有函数 async def，从 asyncpg 池获取连接
- **返回值**: list[dict] / dict / None / int

### 数据库表 (6张)
| 表名 | 主键 | 说明 |
|------|------|------|
| stores | store_id (TEXT) | 门店信息 |
| users | id (TEXT) | 用户账号(含密码哈希、角色、门店权限) |
| products | id (TEXT) | 商品SKU库(含进价/售价/库存) |
| records | id (TEXT) | 交易记录(核心表，items为JSONB) |
| ai_raw_records | id (BIGSERIAL) | AI原始识别记录(审计用) |
| audit_logs | id (BIGSERIAL) | 审计日志 |

### 建表SQL
- `scripts/create_schema.sql` — 含6张表+索引

### 迁移脚本
- `scripts/migrate_json_to_pg.py` — JSON数据→PostgreSQL

## 文件结构

```
├── config/
│   ├── nlu_extraction_cfg.json      # NLU意图识别配置
│   └── anomaly_detection_cfg.json   # 异常检测配置
├── assets/
│   ├── index.html          # 老板端Web界面
│   ├── mobile.html         # 店长端移动界面
│   ├── login.html          # 登录页面
│   ├── products.html       # 商品管理页面
│   ├── app.js              # 前端交互脚本
│   └── styles.css          # 样式文件
├── data/
│   ├── users.json          # 用户数据(fallback)
│   ├── organizations.json  # 组织数据(fallback)
│   ├── stores.json         # 门店数据(fallback)
│   └── products.json       # 商品数据(fallback)
├── scripts/
│   ├── create_schema.sql   # PostgreSQL建表SQL
│   └── migrate_json_to_pg.py  # JSON→PG迁移脚本
├── src/
│   ├── main.py             # FastAPI主应用(19个API路由，全部async)
│   ├── graphs/
│   │   ├── state.py        # 状态定义
│   │   ├── graph.py        # 主图编排(entry_router入口路由)
│   │   └── nodes/          # 节点实现
│   ├── storage/
│   │   └── database/
│   │       └── repository.py  # asyncpg数据访问层
│   └── utils/
│       ├── auth.py         # 认证模块(JWT, 密码验证)
│       ├── db_pool.py      # asyncpg连接池单例
│       ├── feishu_notify.py    # 飞书消息推送
│       └── product_knowledge.py # 商品知识库
└── AGENTS.md               # 本文件
```

## API端点

### 认证相关
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 用户登录 |
| `/api/auth/verify` | POST | 验证Token |
| `/api/auth/logout` | POST | 用户登出 |

### 业务相关
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/voice/base64` | POST | 语音报账(base64音频→ASR→NLU) |
| `/api/image` | POST | 图片识别(file_url→OCR→NLU) |
| `/api/document` | POST | PDF文档识别(file_url→提取文本→NLU) |
| `/api/upload` | POST | 文件上传到对象存储 |
| `/api/dashboard` | GET | 看板数据(真实统计，支持period/store_id) |
| `/api/records` | GET | 历史记录(分页、日期筛选、类型筛选) |
| `/api/records` | POST | 创建交易记录(确认提交) |
| `/api/records/{id}/approve` | PUT | 审核通过 |
| `/api/records/{id}/reject` | PUT | 审核驳回 |
| `/api/records/{id}` | PUT | 编辑记录 |
| `/api/reviews` | GET | 待审核记录列表 |
| `/api/pending_reviews` | GET | 审核中心专用(含统计) |
| `/api/stores` | GET | 门店列表 |
| `/api/stores/list` | GET | 门店列表(带权限过滤) |
| `/api/analysis` | GET | 款式分析(畅销/滞销/补货建议) |
| `/api/alerts` | GET | 异常预警(5类规则引擎) |
| `/api/history` | GET | 历史记录(多维度筛选) |

### 商品管理
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/products` | GET | 商品列表 |
| `/api/products` | POST | 创建商品 |
| `/api/products/{id}` | PUT | 更新商品 |
| `/api/products/{id}` | DELETE | 删除商品 |

### 报告相关
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/report/export` | POST | 导出PDF/Word/Excel报告 |

### 消息推送
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/notify/feishu` | POST | 推送消息到飞书群 |

## 数据类型

### NLU意图类型
- `revenue`: 销售/营收
- `expense`: 支出/费用
- `purchase`: 进货
- `return`: 退换货
- `inventory`: 盘点
- `query`: 查询

### 用户角色
- `owner`: 老板 - 全部权限
- `manager`: 店长 - 单店数据、录入权限
- `accountant`: 会计 - 查看权限、导出报告

## 技术栈
- **后端**: FastAPI + LangGraph
- **前端**: 原生HTML/CSS/JS
- **数据库**: PostgreSQL + asyncpg 异步连接池
- **AI能力**: 
  - ASR: coze-coding-dev-sdk AudioClient
  - LLM: 豆包大模型
  - Storage: coze-coding-dev-sdk StorageClient
- **认证**: JWT Token
- **旧依赖(已弃用)**: supabase-py → 迁移到 asyncpg

## 运行方式

```bash
# 启动服务
python -m src.main
