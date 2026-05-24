# 服装连锁AI记账助手

## 项目概述
- **名称**: 服装连锁AI记账助手
- **功能**: 面向服装连锁店的智能记账系统，支持语音报账、拍照录入、数据看板、异常预警、多格式报告导出、飞书消息推送等功能

## 用户角色
| 角色 | 权限 | 默认账号 | 密码 |
|------|------|---------|------|
| 老板(owner) | 全部功能、多门店数据 | boss | 123456 |
| 店长(manager) | 单店数据、语音/拍照录入 | manager1/manager2 | 123456 |
| 会计(accountant) | 数据查看、报表导出 | accountant | 123456 |

## 核心功能
1. **语音报账**: 说一句话自动记账，支持ASR语音识别
2. **拍照录入**: 拍单据自动识别入库，支持OCR图片识别
3. **数据看板**: 实时营收、毛利、趋势分析
4. **异常预警**: 毛利率异常、营收偏离检测
5. **报告生成**: 自动生成经营报告，支持PDF/Word/Excel多格式导出
6. **商品管理**: SKU管理、库存预警
7. **飞书通知**: 异常预警、日报推送到飞书群
8. **知识库增强**: 商品知识库提升NLU识别准确率

## 节点清单

| 节点名 | 文件位置 | 类型 | 功能描述 | 配置文件 |
|-------|---------|------|---------|---------|
| asr_recognition | `nodes/asr_recognition_node.py` | task | ASR语音识别，将音频转为文字 | - |
| ocr_recognition | `nodes/ocr_recognition_node.py` | task | OCR图片识别，提取图片中的账目信息 | - |
| nlu_extraction | `nodes/nlu_extraction_node.py` | agent | NLU意图识别，提取结构化数据，支持知识库增强 | `config/nlu_extraction_cfg.json` |
| data_validation | `nodes/data_validation_node.py` | task | 数据校验，验证提取的数据完整性 | - |
| data_aggregation | `nodes/data_aggregation_node.py` | task | 数据聚合，计算营收/成本/毛利 | - |
| anomaly_detection | `nodes/anomaly_detection_node.py` | agent | 异常检测，检测毛利率/营收异常 | `config/anomaly_detection_cfg.json` |
| report_generation | `nodes/report_generation_node.py` | task | 报告生成，生成Markdown格式经营分析报告 | - |
| report_export | `nodes/report_export_node.py` | task | 报告导出，支持PDF/DOCX/XLSX多格式 | - |
| dashboard_query | `nodes/dashboard_query_node.py` | task | 看板查询，返回统计数据 | - |
| route_input_type | `graph.py` | condition | 输入类型路由 | - |

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
│   ├── users.json          # 用户数据
│   ├── organizations.json  # 组织数据
│   ├── stores.json         # 门店数据
│   └── products.json       # 商品数据
├── src/
│   ├── main.py             # FastAPI主应用
│   ├── graphs/
│   │   ├── state.py        # 状态定义
│   │   ├── graph.py        # 主图编排
│   │   └── nodes/          # 节点实现
│   └── utils/
│       ├── auth.py         # 认证模块
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
| `/api/stores` | GET | 门店列表 |
| `/api/products` | GET/POST | 商品CRUD |

### 报告相关
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/report` | POST | 生成Markdown报告 |
| `/api/report/export` | POST | 导出PDF/Word/Excel报告 |

### 消息推送
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/notify/feishu` | POST | 推送消息到飞书群 |

### 商品管理
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/products` | GET | 商品列表 |
| `/api/products` | POST | 创建商品 |
| `/api/products/{id}` | PUT | 更新商品 |
| `/api/products/{id}` | DELETE | 删除商品 |

### 知识库
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/knowledge/search` | POST | 商品知识库搜索 |

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
- **AI能力**: 
  - ASR: coze-coding-dev-sdk AudioClient
  - LLM: 豆包大模型
  - Storage: coze-coding-dev-sdk StorageClient
- **认证**: JWT Token
- **数据存储**: JSON文件

## 运行方式

```bash
# 启动服务
python -m src.main

# 访问地址
# 老板端: http://localhost:5000/
# 登录页: http://localhost:5000/login.html
# 店长端: http://localhost:5000/mobile.html
# 商品管理: http://localhost:5000/products.html
```

## 更新日志

### v2.0.0 (2024-05-25)
- ✅ 新增登录鉴权系统（JWT Token）
- ✅ 新增用户角色权限（老板/店长/会计）
- ✅ 新增店长移动端界面（3大按钮主页）
- ✅ 扩展NLU意图（支持退换货/盘点）
- ✅ 新增商品库管理功能
- ✅ 新增多门店数据隔离

### v1.0.0 (2024-05-24)
- ✅ 语音报账功能
- ✅ 图片OCR识别
- ✅ 数据看板
- ✅ 异常预警
- ✅ 报告生成
