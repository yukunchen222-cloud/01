import argparse
import asyncio
import json
import os
import threading
import traceback
import logging
from functools import wraps
from typing import Any, Dict, Iterable, AsyncIterable, AsyncGenerator, Optional

# 确保 JWT_SECRET 在 auth 模块加载前设置
if not os.getenv("JWT_SECRET"):
    os.environ["JWT_SECRET"] = "coze_clothing_ai_prod_key_2026"
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "⚠️ JWT_SECRET 环境变量未设置，已使用开发密钥。生产环境请务必配置！"
    )
import cozeloop
import uvicorn
import time
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from coze_coding_utils.runtime_ctx.context import new_context, Context
from coze_coding_utils.helper import graph_helper
from coze_coding_utils.log.node_log import LOG_FILE
from coze_coding_utils.log.write_log import setup_logging, request_context
from coze_coding_utils.log.config import LOG_LEVEL
from coze_coding_utils.error.classifier import ErrorClassifier, classify_error
from coze_coding_utils.helper.stream_runner import AgentStreamRunner, WorkflowStreamRunner,agent_stream_handler,workflow_stream_handler, RunOpt

setup_logging(
    log_file=LOG_FILE,
    max_bytes=100 * 1024 * 1024, # 100MB
    backup_count=5,
    log_level=LOG_LEVEL,
    use_json_format=True,
    console_output=True
)

logger = logging.getLogger(__name__)


def endpoint_timeout(seconds: float = 5.0):
    """Fail fast for read endpoints instead of leaving the browser pending."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                logger.warning("%s timed out after %.1fs", func.__name__, seconds)
                raise HTTPException(status_code=504, detail="处理超时，请重试")

        return wrapper

    return decorator

from coze_coding_utils.helper.agent_helper import to_stream_input
from coze_coding_utils.openai.handler import OpenAIChatHandler
from coze_coding_utils.log.parser import LangGraphParser
from coze_coding_utils.log.err_trace import extract_core_stack
from coze_coding_utils.log.loop_trace import init_run_config, init_agent_config


# 超时配置常量
TIMEOUT_SECONDS = 900  # 15分钟

class GraphService:
    def __init__(self):
        # 用于跟踪正在运行的任务（使用asyncio.Task）
        self.running_tasks: Dict[str, asyncio.Task] = {}
        # 错误分类器
        self.error_classifier = ErrorClassifier()
        # stream runner
        self._agent_stream_runner = AgentStreamRunner()
        self._workflow_stream_runner = WorkflowStreamRunner()
        self._graph = None
        self._graph_lock = threading.Lock()

    def _get_graph(self, ctx=Context):
        if graph_helper.is_agent_proj():
            return graph_helper.get_agent_instance("agents.agent", ctx)

        if self._graph is not None:
            return self._graph
        with self._graph_lock:
            if self._graph is not None:
                return self._graph
            self._graph = graph_helper.get_graph_instance("graphs.graph")
            return self._graph

    @staticmethod
    def _sse_event(data: Any, event_id: Any = None) -> str:
        id_line = f"id: {event_id}\n" if event_id else ""
        return f"{id_line}event: message\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"

    def _get_stream_runner(self):
        if graph_helper.is_agent_proj():
            return self._agent_stream_runner
        else:
            return self._workflow_stream_runner

    # 流式运行（原始迭代器）：本地调用使用
    def stream(self, payload: Dict[str, Any], run_config: RunnableConfig, ctx=Context) -> Iterable[Any]:
        graph = self._get_graph(ctx)
        stream_runner = self._get_stream_runner()
        for chunk in stream_runner.stream(payload, graph, run_config, ctx):
            yield chunk

    # 同步运行：本地/HTTP 通用
    async def run(self, payload: Dict[str, Any], ctx=None) -> Dict[str, Any]:
        if ctx is None:
            ctx = new_context("run")

        run_id = ctx.run_id
        logger.info(f"Starting run with run_id: {run_id}")

        try:
            graph = self._get_graph(ctx)
            # custom tracer
            run_config = init_run_config(graph, ctx)
            run_config["configurable"] = {"thread_id": ctx.run_id}

            # 直接调用，LangGraph会在当前任务上下文中执行
            # 如果当前任务被取消，LangGraph的执行也会被取消
            return await graph.ainvoke(payload, config=run_config, context=ctx)

        except asyncio.CancelledError:
            logger.info(f"Run {run_id} was cancelled")
            return {"status": "cancelled", "run_id": run_id, "message": "Execution was cancelled"}
        except Exception as e:
            # 使用错误分类器分类错误
            err = self.error_classifier.classify(e, {"node_name": "run", "run_id": run_id})
            # 记录详细的错误信息和堆栈跟踪
            logger.error(
                f"Error in GraphService.run: [{err.code}] {err.message}\n"
                f"Category: {err.category.name}\n"
                f"Traceback:\n{extract_core_stack()}"
            )
            # 保留原始异常堆栈，便于上层返回真正的报错位置
            raise
        finally:
            # 清理任务记录
            self.running_tasks.pop(run_id, None)

    # 流式运行（SSE 格式化）：HTTP 路由使用
    async def stream_sse(self, payload: Dict[str, Any], ctx=None, run_opt: Optional[RunOpt] = None) -> AsyncGenerator[str, None]:
        if ctx is None:
            ctx = new_context(method="stream_sse")
        if run_opt is None:
            run_opt = RunOpt()

        run_id = ctx.run_id
        logger.info(f"Starting stream with run_id: {run_id}")
        graph = self._get_graph(ctx)
        if graph_helper.is_agent_proj():
            run_config = init_agent_config(graph, ctx)
        else:
            run_config = init_run_config(graph, ctx)  # vibeflow

        is_workflow = not graph_helper.is_agent_proj()

        try:
            async for chunk in self.astream(payload, graph, run_config=run_config, ctx=ctx, run_opt=run_opt):
                if is_workflow and isinstance(chunk, tuple):
                    event_id, data = chunk
                    yield self._sse_event(data, event_id)
                else:
                    yield self._sse_event(chunk)
        finally:
            # 清理任务记录
            self.running_tasks.pop(run_id, None)
            cozeloop.flush()

    # 取消执行 - 使用asyncio的标准方式
    def cancel_run(self, run_id: str, ctx: Optional[Context] = None) -> Dict[str, Any]:
        """
        取消指定run_id的执行

        使用asyncio.Task.cancel()来取消任务,这是标准的Python异步取消机制。
        LangGraph会在节点之间检查CancelledError,实现优雅的取消。
        """
        logger.info(f"Attempting to cancel run_id: {run_id}")

        # 查找对应的任务
        if run_id in self.running_tasks:
            task = self.running_tasks[run_id]
            if not task.done():
                # 使用asyncio的标准取消机制
                # 这会在下一个await点抛出CancelledError
                task.cancel()
                logger.info(f"Cancellation requested for run_id: {run_id}")
                return {
                    "status": "success",
                    "run_id": run_id,
                    "message": "Cancellation signal sent, task will be cancelled at next await point"
                }
            else:
                logger.info(f"Task already completed for run_id: {run_id}")
                return {
                    "status": "already_completed",
                    "run_id": run_id,
                    "message": "Task has already completed"
                }
        else:
            logger.warning(f"No active task found for run_id: {run_id}")
            return {
                "status": "not_found",
                "run_id": run_id,
                "message": "No active task found with this run_id. Task may have already completed or run_id is invalid."
            }

    # 运行指定节点：本地/HTTP 通用
    async def run_node(self, node_id: str, payload: Dict[str, Any], ctx=None) -> Any:
        if ctx is None or Context.run_id == "":
            ctx = new_context(method="node_run")

        _graph = self._get_graph()
        node_func, input_cls, output_cls = graph_helper.get_graph_node_func_with_inout(_graph.get_graph(), node_id)
        if node_func is None or input_cls is None:
            raise KeyError(f"node_id '{node_id}' not found")

        parser = LangGraphParser(_graph)
        metadata = parser.get_node_metadata(node_id) or {}

        _g = StateGraph(input_cls, input_schema=input_cls, output_schema=output_cls)
        _g.add_node("sn", node_func, metadata=metadata)
        _g.set_entry_point("sn")
        _g.add_edge("sn", END)
        _graph = _g.compile()

        run_config = init_run_config(_graph, ctx)
        return await _graph.ainvoke(payload, config=run_config)

    def graph_inout_schema(self) -> Any:
        if graph_helper.is_agent_proj():
            return {"input_schema": {}, "output_schema": {}}
        builder = getattr(self._get_graph(), 'builder', None)
        if builder is not None:
            input_cls = getattr(builder, 'input_schema', None) or self.graph.get_input_schema()
            output_cls = getattr(builder, 'output_schema', None) or self.graph.get_output_schema()
        else:
            logger.warning(f"No builder input schema found for graph_inout_schema, using graph input schema instead")
            input_cls = self.graph.get_input_schema()
            output_cls = self.graph.get_output_schema()

        return {
            "input_schema": input_cls.model_json_schema(), 
            "output_schema": output_cls.model_json_schema(),
            "code":0,
            "msg":""
        }

    async def astream(self, payload: Dict[str, Any], graph: CompiledStateGraph, run_config: RunnableConfig, ctx=Context, run_opt: Optional[RunOpt] = None) -> AsyncIterable[Any]:
        stream_runner = self._get_stream_runner()
        async for chunk in stream_runner.astream(payload, graph, run_config, ctx, run_opt):
            yield chunk


service = GraphService()
app = FastAPI(title="服装连锁AI记账助手", version="1.0.0")

# ==================== asyncpg 连接池生命周期 ====================
from storage.database import repository as repo
from utils.db_pool import get_pool, close_pool
from utils.run_sync import run_sync, shutdown_executor


@app.on_event("startup")
async def _init_pool():
    """应用启动时预热连接池，第一个请求不会冷启动。"""
    await get_pool()


@app.on_event("shutdown")
async def _close_pool():
    await close_pool()
    shutdown_executor()

# CORS配置 - 限制来源而非全开放
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "https://9f450885-7dd8-4e7b-9cde-11d2486de9a8.dev.coze.site",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
import os
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_workspace = os.getenv("COZE_WORKSPACE_PATH", _project_root)
_static_dir = os.path.join(_workspace, "assets")
if os.path.exists(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# OpenAI 兼容接口处理器
openai_handler = OpenAIChatHandler(service)

# ==================== 统一数据访问层（asyncpg 异步） ====================

async def _fetch_records(request: Request, store_id: str = None, record_type: str = None,
                   start_date: str = None, end_date: str = None) -> list:
    """统一获取记录 - 使用 asyncpg 异步查询"""
    # 解析用户权限
    auth_header = request.headers.get("Authorization", "")
    org_id = "org_default"
    user_role = "owner"
    user_store_ids = None
    
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        from utils.auth import decode_token
        payload = decode_token(token)
        if payload:
            org_id = payload.get("org_id", org_id)
            user_role = payload.get("role", user_role)
            user_store_ids = payload.get("store_ids")
    
    # 店长只看自己的门店
    actual_store_id = store_id if store_id and store_id != "all" else None
    if user_role == "manager" and user_store_ids:
        # 店长模式下，如果没指定门店或指定了 all，用店长的门店列表
        if not actual_store_id:
            actual_store_id = user_store_ids[0] if user_store_ids else None
        elif actual_store_id not in user_store_ids:
            actual_store_id = user_store_ids[0] if user_store_ids else None
    
    # 类型映射
    actual_type = None
    if record_type and record_type != "all":
        type_map = {"sale": "revenue", "expense": "expense", "return": "return", "purchase": "purchase"}
        actual_type = type_map.get(record_type, record_type)
    
    # 日期筛选
    start_at = start_date if start_date else None
    end_at = (end_date + " 23:59:59") if end_date else None
    
    records = await repo.get_records(
        org_id=org_id,
        store_id=actual_store_id,
        record_type=actual_type,
        start_at=start_at,
        end_at=end_at,
        limit=10000,
    )
    logger.info(f"从数据库获取{len(records)}条记录")
    return records


async def _save_record(record: dict) -> dict:
    """统一保存记录 - 使用 asyncpg 异步写入"""
    import secrets
    if "id" not in record or not record["id"]:
        record["id"] = f"rec_{secrets.token_hex(6)}"
    new_record = await repo.insert_record(record)
    return new_record


async def _update_record(record_id: str, updates: dict) -> Optional[dict]:
    """统一更新记录 - 使用 asyncpg 异步更新"""
    updated = await repo.update_record(record_id, updates)
    return updated


# ==================== 鉴权工具函数 ====================

async def get_current_user(request: Request):
    """从请求头获取当前用户，未登录返回None"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        # 尝试从cookie获取
        token = request.cookies.get("token", "")
    else:
        token = auth_header[7:]
    if not token:
        return None
    from utils.auth import decode_token
    payload = decode_token(token)
    if not payload:
        return None
    user_id = payload.get("user_id", "")
    user_data = await repo.get_user_by_id(user_id)
    if not user_data:
        return None
    # 转换为 auth.User 兼容对象
    from utils.auth import User
    return User(
        user_id=str(user_data.get("id", "")),
        username=user_data.get("username", ""),
        password_hash=user_data.get("password_hash", ""),
        role=user_data.get("role", ""),
        org_id=str(user_data.get("org_id", "")),
        store_ids=user_data.get("store_ids", []) or [],
        name=user_data.get("name", ""),
        phone=user_data.get("phone", ""),
        is_active=user_data.get("is_active", True),
        created_at=str(user_data.get("created_at", "")),
        last_login=str(user_data.get("last_login", ""))
    )


async def require_owner(request: Request):
    """要求老板权限"""
    user = await get_current_user(request)
    if not user or user.role != "owner":
        return None
    return user


# ==================== Web界面路由 ====================

@app.get("/", response_class=HTMLResponse)
async def web_home():
    """Web界面首页"""
    html_path = os.path.join(_static_dir, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Web界面文件不存在</h1>", status_code=404)

@app.get("/web", response_class=HTMLResponse)
async def web_ui():
    """Web界面入口"""
    return await web_home()

@app.get("/api/stores")
async def get_stores(request: Request):
    """获取门店列表（asyncpg 异步查询）"""
    from utils.auth import decode_token
    
    org_id = "org_default"
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload:
            org_id = payload.get("org_id", org_id)
    
    try:
        stores = await repo.get_stores(org_id)
        return {"success": True, "stores": stores}
    except Exception as e:
        logger.error(f"数据库查询门店失败: {e}")
        return {"success": False, "stores": [], "error": str(e)}

@app.post("/api/query")
async def api_query(request: Request):
    """查询看板数据API"""
    try:
        payload = await request.json()
        input_type = payload.get("input_type", "query")
        query_type = payload.get("query_type", "month")
        store_id = payload.get("store_id")
        
        # 调用工作流
        ctx = new_context(method="api_query")
        result = await service.run(payload, ctx)
        
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/voice")
async def api_voice(request: Request):
    """语音报账API - 接收audio_url进行语音识别"""
    try:
        payload = await request.json()
        payload["input_type"] = "voice"
        
        # 将audio_url转换为audio_file格式
        audio_url = payload.pop("audio_url", None)
        if audio_url:
            payload["audio_file"] = {"url": audio_url, "file_type": "audio"}
        
        ctx = new_context(method="api_voice")
        result = await service.run(payload, ctx)
        
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"语音报账失败: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/voice/base64")
async def api_voice_base64(request: Request):
    """语音识别API - 接收base64编码的音频进行ASR识别"""
    import base64
    from coze_coding_dev_sdk import ASRClient
    
    try:
        data = await request.json()
        audio_base64 = data.get("audio_base64", "")
        audio_format = data.get("audio_format", "webm")
        store_id = data.get("store_id", "")
        
        if not audio_base64:
            return {"success": False, "error": "音频数据不能为空"}
        
        ctx = new_context(method="api_voice_base64")
        
        # 步骤1：使用ASR客户端直接用base64识别语音
        asr_client = ASRClient(ctx=ctx)
        recognized_text, asr_data = await run_sync(
            asr_client.recognize,
            uid="accounting_assistant",
            base64_data=audio_base64
        )
        
        if not recognized_text or not recognized_text.strip():
            return {"success": False, "error": "语音识别结果为空，请重新录音"}
        
        # 步骤2：将识别文本构造成工作流输入，传入recognized_text跳过ASR节点
        payload = {
            "input_type": "voice",
            # 不传audio_file，ASR节点会检测到无音频文件并透传recognized_text
            "recognized_text": recognized_text,  # 直接传入识别结果
            "store_id": store_id
        }
        
        nlu_result = await service.run(payload, ctx)
        
        return {
            "success": True,
            "recognized_text": recognized_text,
            "extracted_data": nlu_result.get("extracted_data", {}),
            **nlu_result
        }
    except Exception as e:
        logger.error(f"语音识别失败: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    """图片/文件上传API - 上传到对象存储并返回URL"""
    from coze_coding_dev_sdk import S3SyncStorage
    
    try:
        ctx = new_context(method="api_upload")
        storage = S3SyncStorage()
        
        # 读取文件内容
        content = await file.read()
        
        # 生成唯一文件名
        import time
        timestamp = int(time.time() * 1000)
        filename = f"upload_{timestamp}_{file.filename}"
        
        # 确定content_type
        content_type = file.content_type or "application/octet-stream"
        
        # 上传到对象存储（upload_file 返回 URL 字符串）
        url = await run_sync(
            storage.upload_file,
            file_content=content,
            file_name=filename,
            content_type=content_type
        )
        
        return {"success": True, "url": url, "filename": filename}
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/image")
async def api_image(request: Request):
    """拍照录入API - 接收file_url进行图片识别"""
    try:
        payload = await request.json()
        payload["input_type"] = "image"
        
        # 将file_url转换为image_file格式
        file_url = payload.pop("file_url", None) or payload.pop("image_url", None)
        if file_url:
            payload["image_file"] = {"url": file_url, "file_type": "image"}
        
        ctx = new_context(method="api_image")
        result = await service.run(payload, ctx)
        
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"图片识别失败: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/document")
async def api_document(request: Request):
    """文档识别API - 支持PDF等文档文件识别"""
    try:
        payload = await request.json()
        payload["input_type"] = "image"  # 复用image通道，OCR节点会检测PDF
        
        # 将file_url转换为image_file格式（PDF也用image_file传递）
        file_url = payload.pop("file_url", None) or payload.pop("document_url", None)
        if file_url:
            payload["image_file"] = {"url": file_url, "file_type": "document"}
        
        ctx = new_context(method="api_document")
        result = await service.run(payload, ctx)
        
        return {
            "success": True,
            "recognized_text": result.get("ocr_text", ""),
            "extracted_data": result.get("extracted_data", {}),
            **result
        }
    except Exception as e:
        logger.error(f"文档识别失败: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/records")
@endpoint_timeout(5.0)
async def get_records(
    request: Request,
    store_id: str = None,
    record_type: str = None,
    start_date: str = None,
    end_date: str = None,
    page: int = 1,
    page_size: int = 20
):
    """获取历史记录（真实数据）"""
    try:
        records = await _fetch_records(request, store_id, record_type, start_date, end_date)
        
        # 按时间倒序
        records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        # 分页
        total = len(records)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_records = records[start_idx:end_idx]
        
        return {
            "success": True,
            "records": page_records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        return {"success": False, "records": [], "total": 0, "error": str(e)}

@app.post("/api/records")
async def create_record(request: Request):
    """创建交易记录（确认提交）- 需要登录，自动扣减库存"""
    user = await get_current_user(request)
    if not user:
        return {"success": False, "error": "未登录，请先登录"}
    
    try:
        data = await request.json()
        org_id = data.get("org_id", "org_default")
        items = data.get("items", [])
        record_type = data.get("type", "revenue")
        
        # 库存校验和扣减（仅销售类型记录）
        stock_warnings = []
        stock_deductions = []
        
        if record_type == "revenue" and items:
            # 获取商品库所有商品
            all_products = await repo.get_products(org_id)
            products_map = {p.get("sku", ""): p for p in all_products}
            products_by_name = {p.get("name", ""): p for p in all_products}
            
            for item in items:
                item_name = item.get("name", "")
                item_sku = item.get("sku", "")
                item_qty = int(item.get("quantity", 0))
                
                # 尝试匹配商品（优先SKU，其次名称）
                product = None
                if item_sku and item_sku in products_map:
                    product = products_map[item_sku]
                elif item_name and item_name in products_by_name:
                    product = products_by_name[item_name]
                elif item_name:
                    # 模糊匹配：商品名称包含或被包含
                    for p in all_products:
                        pname = p.get("name", "")
                        if item_name in pname or pname in item_name:
                            product = p
                            break
                
                if product:
                    product_id = product.get("product_id") or product.get("id")
                    current_stock = int(product.get("stock", 0))
                    product_name = product.get("name", item_name)
                    sku = product.get("sku", item_sku)
                    
                    # 更新item的SKU信息
                    item["sku"] = sku
                    item["matched_product"] = product_name
                    
                    if current_stock < item_qty:
                        # 库存不足
                        stock_warnings.append({
                            "product_name": product_name,
                            "sku": sku,
                            "requested": item_qty,
                            "available": current_stock,
                            "shortage": item_qty - current_stock,
                            "message": f"「{product_name}」库存不足！需要{item_qty}件，当前库存{current_stock}件，缺少{item_qty - current_stock}件"
                        })
                    else:
                        # 可以扣减
                        stock_deductions.append({
                            "product_id": product_id,
                            "product_name": product_name,
                            "sku": sku,
                            "deduct_qty": item_qty,
                            "old_stock": current_stock,
                            "new_stock": current_stock - item_qty
                        })
                else:
                    # 商品库中未找到
                    stock_warnings.append({
                        "product_name": item_name,
                        "sku": item_sku,
                        "requested": item_qty,
                        "available": 0,
                        "shortage": item_qty,
                        "not_found": True,
                        "message": f"「{item_name}」在商品库中未找到，请先添加该商品"
                    })
        
        # 如果有库存问题，返回警告让前端确认
        if stock_warnings:
            return {
                "success": False,
                "need_confirm": True,
                "stock_warnings": stock_warnings,
                "stock_deductions": stock_deductions,
                "message": "库存校验发现问题，请检查后确认",
                "error_type": "stock_insufficient"
            }
        
        # 执行库存扣减
        for deduction in stock_deductions:
            await repo.update_product(deduction["product_id"], {
                "stock": deduction["new_stock"]
            })
            logger.info(f"库存扣减: {deduction['product_name']} {deduction['old_stock']} -> {deduction['new_stock']}")
        
        # 构建新记录
        new_record = {
            "org_id": org_id,
            "store_id": data.get("store_id", ""),
            "store_name": data.get("store_name", ""),
            "type": record_type,
            "category": data.get("category", ""),
            "items": items,
            "total_amount": float(data.get("total_amount", 0)),
            "payment_method": data.get("payment_method", ""),
            "confidence": float(data.get("confidence", 0.8)),
            "status": data.get("status", "pending"),
            "operator": data.get("operator", ""),
            "created_at": data.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S")),
            "stock_deducted": len(stock_deductions) > 0  # 标记是否已扣减库存
        }
        
        saved = await _save_record(new_record)
        return {"success": True, "record": saved, "stock_deductions": stock_deductions}
    except Exception as e:
        logger.error(f"创建记录失败: {e}")
        return {"success": False, "message": str(e)}

@app.post("/api/records/force")
async def create_record_force(request: Request):
    """强制创建记录（忽略库存警告）- 需要登录"""
    user = await get_current_user(request)
    if not user:
        return {"success": False, "error": "未登录，请先登录"}
    
    try:
        data = await request.json()
        org_id = data.get("org_id", "org_default")
        items = data.get("items", [])
        force_deduct = data.get("force_deduct", True)  # 是否强制扣减（可能导致负库存）
        
        # 如果需要强制扣减库存
        stock_deductions = []
        if force_deduct and items:
            all_products = await repo.get_products(org_id)
            products_map = {p.get("sku", ""): p for p in all_products}
            products_by_name = {p.get("name", ""): p for p in all_products}
            
            for item in items:
                item_name = item.get("name", "")
                item_sku = item.get("sku", "")
                item_qty = int(item.get("quantity", 0))
                
                product = None
                if item_sku and item_sku in products_map:
                    product = products_map[item_sku]
                elif item_name and item_name in products_by_name:
                    product = products_by_name[item_name]
                elif item_name:
                    for p in all_products:
                        pname = p.get("name", "")
                        if item_name in pname or pname in item_name:
                            product = p
                            break
                
                if product:
                    product_id = product.get("product_id") or product.get("id")
                    current_stock = int(product.get("stock", 0))
                    new_stock = current_stock - item_qty
                    
                    # 强制扣减（可能变成负数）
                    await repo.update_product(product_id, {"stock": new_stock})
                    item["sku"] = product.get("sku", item_sku)
                    stock_deductions.append({
                        "product_name": product.get("name", item_name),
                        "old_stock": current_stock,
                        "new_stock": new_stock
                    })
                    logger.warning(f"强制库存扣减: {product.get('name')} {current_stock} -> {new_stock}")
        
        # 构建记录
        new_record = {
            "org_id": org_id,
            "store_id": data.get("store_id", ""),
            "store_name": data.get("store_name", ""),
            "type": data.get("type", "revenue"),
            "category": data.get("category", ""),
            "items": items,
            "total_amount": float(data.get("total_amount", 0)),
            "payment_method": data.get("payment_method", ""),
            "confidence": float(data.get("confidence", 0.8)),
            "status": "pending",
            "operator": data.get("operator", ""),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stock_deducted": len(stock_deductions) > 0,
            "forced": True  # 标记为强制提交
        }
        
        saved = await _save_record(new_record)
        return {
            "success": True, 
            "record": saved, 
            "stock_deductions": stock_deductions,
            "message": "已强制记录，库存已扣减（可能出现负库存）"
        }
    except Exception as e:
        logger.error(f"强制创建记录失败: {e}")
        return {"success": False, "message": str(e)}

@app.put("/api/records/{record_id}/approve")
async def approve_record(record_id: str, request: Request):
    """审核通过 - 仅老板可操作"""
    user = await require_owner(request)
    if not user:
        return {"success": False, "error": "无权限，仅老板可审核"}
    """审核通过记录"""
    try:
        updated = await _update_record(record_id, {"status": "approved"})
        if updated:
            return {"success": True, "record": updated}
        return {"success": False, "message": "记录不存在"}
    except Exception as e:
        logger.error(f"审核通过失败: {e}")
        return {"success": False, "message": str(e)}

@app.put("/api/records/{record_id}/reject")
async def reject_record(record_id: str, request: Request):
    """审核驳回记录 - 仅老板可操作"""
    user = await require_owner(request)
    if not user:
        return {"success": False, "error": "无权限，仅老板可审核"}
    
    try:
        updated = await _update_record(record_id, {"status": "rejected"})
        if updated:
            return {"success": True, "record": updated}
        return {"success": False, "message": "记录不存在"}
    except Exception as e:
        logger.error(f"审核驳回失败: {e}")
        return {"success": False, "message": str(e)}

@app.put("/api/records/{record_id}")
async def update_record(record_id: str, request: Request):
    """编辑记录"""
    try:
        data = await request.json()
        updates = {}
        for key in ["items", "total_amount", "category", "payment_method", "type"]:
            if key in data:
                updates[key] = data[key]
        updates["status"] = "pending"  # 编辑后重新待审核
        
        updated = await _update_record(record_id, updates)
        if updated:
            return {"success": True, "record": updated}
        return {"success": False, "message": "记录不存在"}
    except Exception as e:
        logger.error(f"编辑记录失败: {e}")
        return {"success": False, "message": str(e)}

@app.get("/api/dashboard")
@endpoint_timeout(5.0)
async def get_dashboard_data(
    request: Request,
    period: str = "month",
    store_id: str = "all",
    start_date: str = "",
    end_date: str = ""
):
    """获取看板数据（真实统计）"""
    import datetime
    
    try:
        # 使用统一数据访问层
        records = await _fetch_records(request, store_id=store_id if store_id != "all" else None,
                                 start_date=start_date if start_date else None,
                                 end_date=end_date if end_date else None)
        
        # 日期过滤
        if start_date and end_date:
            # 自定义日期范围
            sd = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            ed = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)
            filtered = []
            for r in records:
                try:
                    rd = datetime.datetime.strptime(r.get("created_at", "")[:10], "%Y-%m-%d")
                    if sd <= rd < ed:
                        filtered.append(r)
                except (ValueError, TypeError):
                    pass
            records = filtered
            period = "custom"
        else:
            # 预设期间
            now = datetime.datetime.now()
            if period == "day":
                date_prefix = now.strftime("%Y-%m-%d")
                records = [r for r in records if r.get("created_at", "").startswith(date_prefix)]
            elif period == "month":
                date_prefix = now.strftime("%Y-%m")
                records = [r for r in records if r.get("created_at", "").startswith(date_prefix)]
            elif period == "year":
                date_prefix = now.strftime("%Y")
                records = [r for r in records if r.get("created_at", "").startswith(date_prefix)]
        
        # 统计汇总
        total_revenue = sum(r.get("total_amount", 0) for r in records if r.get("type") == "revenue" and r.get("status") == "approved")
        total_cost = sum(r.get("total_amount", 0) for r in records if r.get("type") == "purchase" and r.get("status") == "approved")
        total_expense = sum(r.get("total_amount", 0) for r in records if r.get("type") == "expense" and r.get("status") == "approved")
        total_returns = sum(r.get("total_amount", 0) for r in records if r.get("type") == "return" and r.get("status") == "approved")
        gross_profit = total_revenue - total_cost - total_returns
        gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # Bug1修复：固定费用按门店分摊+按时间窗口缩放
        # expense记录已按store_id筛选，total_expense就是当前视图的固定费用
        total_fixed = total_expense
        
        # 按有营收记录的天数缩放固定费用
        # 固定费用是月度预估值，如果数据只覆盖了部分天数，按比例缩放
        revenue_dates = set()
        for r in records:
            if r.get("type") == "revenue" and r.get("status") == "approved" and r.get("created_at"):
                try:
                    revenue_dates.add(r["created_at"][:10])
                except (IndexError, TypeError):
                    pass
        
        if revenue_dates and total_revenue > 0:
            # 有营收的天数占30天的比例
            coverage_ratio = len(revenue_dates) / 30.0
            # 如果覆盖率过低(数据不完整)，至少按1天算
            coverage_ratio = max(coverage_ratio, 1/30.0)
        else:
            coverage_ratio = 1.0
        
        # 同时考虑用户选择的时间窗口
        period_days = 30
        if start_date and end_date:
            try:
                sd = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                ed = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                period_days = max((ed - sd).days, 1)
            except ValueError:
                pass
        elif period == "day":
            period_days = 1
        elif period == "year":
            period_days = 365
        
        # 固定费用 = 月度费用 × 时间窗口缩放 × 数据覆盖率缩放
        time_scale = period_days / 30.0
        total_fixed = total_fixed * time_scale * coverage_ratio

        net_profit = gross_profit - total_fixed
        net_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
        transaction_count = len([r for r in records if r.get("type") in ("revenue", "purchase", "return") and r.get("status") == "approved"])
        
        # 门店统计
        store_stats = {}
        for r in records:
            if r.get("status") != "approved":
                continue
            sid = r.get("store_id", "")
            sname = r.get("store_name", sid)
            if sid not in store_stats:
                store_stats[sid] = {"store_name": sname, "revenue": 0, "cost": 0, "count": 0}
            if r.get("type") == "revenue":
                store_stats[sid]["revenue"] += r.get("total_amount", 0)
                store_stats[sid]["count"] += 1
            elif r.get("type") == "purchase":
                store_stats[sid]["cost"] += r.get("total_amount", 0)
        
        # Bug3修复：品类拆分 - 销售品类 vs 支出品类
        sales_categories = {}   # 只放商品销售（连衣裙/衬衫/裤装/外套）
        expense_categories = {} # 只放支出科目（房租/人工/水电）
        for r in records:
            if r.get("status") != "approved":
                continue
            rtype = r.get("type", "")
            cat = r.get("category", "其他")
            amount = r.get("total_amount", 0)
            if rtype in ("revenue", "purchase", "return"):
                # 商品品类
                if cat not in sales_categories:
                    sales_categories[cat] = {"revenue": 0, "cost": 0, "return": 0}
                if rtype == "revenue":
                    sales_categories[cat]["revenue"] += amount
                elif rtype == "purchase":
                    sales_categories[cat]["cost"] += amount
                elif rtype == "return":
                    sales_categories[cat]["return"] += amount
            elif rtype == "expense":
                # 支出科目
                expense_categories[cat] = expense_categories.get(cat, 0) + amount
        
        # Bug2修复：前端兼容 - category_stats使用sales_categories（纯数字格式）
        category_stats = {}
        for cat, vals in sales_categories.items():
            category_stats[cat] = vals.get("revenue", 0)
        
        # 固定费用
        fixed_expenses = {"rent": 0, "utilities": 0, "salary": 0, "other": 0}
        for r in records:
            if r.get("status") != "approved" or r.get("type") != "expense":
                continue
            cat = r.get("category", "")
            if "房租" in cat or "rent" in cat.lower():
                fixed_expenses["rent"] += r.get("total_amount", 0)
            elif "水电" in cat or "utilities" in cat.lower():
                fixed_expenses["utilities"] += r.get("total_amount", 0)
            elif "人工" in cat or "工资" in cat or "salary" in cat.lower():
                fixed_expenses["salary"] += r.get("total_amount", 0)
            else:
                fixed_expenses["other"] += r.get("total_amount", 0)
        
        # 趋势数据：按日汇总营收和成本
        daily_data = {}
        for r in records:
            if r.get("status") != "approved":
                continue
            try:
                day_str = r.get("created_at", "")[:10]  # YYYY-MM-DD
            except (ValueError, TypeError):
                continue
            if not day_str:
                continue
            if day_str not in daily_data:
                daily_data[day_str] = {"date": day_str, "revenue": 0, "cost": 0, "profit": 0}
            rtype = r.get("type", "")
            amount = r.get("total_amount", 0)
            if rtype == "revenue":
                daily_data[day_str]["revenue"] += amount
            elif rtype == "purchase":
                daily_data[day_str]["cost"] += amount
            elif rtype == "return":
                daily_data[day_str]["cost"] += amount
            elif rtype == "expense":
                daily_data[day_str]["cost"] += amount
        # 计算利润并排序
        for d in daily_data.values():
            d["profit"] = d["revenue"] - d["cost"]
        trend_data = sorted(daily_data.values(), key=lambda x: x["date"])
        
        # 商品销量统计
        product_sales = {}
        for r in records:
            if r.get("status") != "approved" or r.get("type") not in ("revenue",):
                continue
            for item in r.get("items", []):
                pname = item.get("name", "")
                if not pname:
                    continue
                if pname not in product_sales:
                    product_sales[pname] = {"name": pname, "category": r.get("category", ""), "quantity": 0, "revenue": 0}
                product_sales[pname]["quantity"] += item.get("quantity", 0)
                product_sales[pname]["revenue"] += item.get("amount", 0)
        
        top_sellers = sorted(product_sales.values(), key=lambda x: x["revenue"], reverse=True)[:10]
        slow_sellers = sorted(product_sales.values(), key=lambda x: x["quantity"])[:5]
        
        # 异常检测
        anomaly_alerts = []
        if gross_margin < 30 and total_revenue > 0:
            anomaly_alerts.append({"type": "low_margin", "level": "critical", "message": f"毛利率仅{gross_margin:.1f}%，低于30%警戒线", "value": gross_margin})
        if total_revenue == 0:
            anomaly_alerts.append({"type": "no_revenue", "level": "warning", "message": "当前期间暂无营收数据", "value": 0})
        for sid, sdata in store_stats.items():
            if sdata["revenue"] > 0 and sdata["cost"] / sdata["revenue"] > 0.65:
                anomaly_alerts.append({"type": "high_cost", "level": "warning", "message": f"{sdata['store_name']}成本占营收{(sdata['cost']/sdata['revenue']*100):.0f}%，偏高", "value": sdata["cost"]/sdata["revenue"]})
        if gross_margin < 0:
            anomaly_alerts.append({"type": "negative_margin", "level": "critical", "message": f"毛利率为负({gross_margin:.1f}%)，存在严重亏损风险", "value": gross_margin})
        
        return {
            "success": True,
            "dashboard_data": {
                "period": period,
                "summary": {
                    "total_revenue": round(total_revenue, 0),
                    "total_cost": round(total_cost, 0),
                    "total_expense": round(total_expense, 0),
                    "total_returns": round(total_returns, 0),
                    "gross_profit": round(gross_profit, 0),
                    "gross_margin": round(gross_margin, 1),
                    "net_profit": round(net_profit, 0),
                    "net_margin": round(net_margin, 1),
                    "transaction_count": transaction_count,
                    "fixed_expenses": fixed_expenses
                },
                "store_stats": store_stats,
                "category_stats": category_stats,
                "sales_categories": sales_categories,
                "expense_categories": expense_categories,
                "trend_data": trend_data,
                "product_analysis": {
                    "top_sellers": top_sellers,
                    "slow_sellers": slow_sellers,
                    "product_count": len(product_sales)
                }
            },
            "anomaly_alerts": anomaly_alerts
        }
    except Exception as e:
        logger.error(f"获取看板数据失败: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/analysis")
@endpoint_timeout(5.0)
async def get_analysis(request: Request, period: str = "month", store_id: str = "all"):
    """款式分析API - 畅销款/滞销款/补货建议"""
    try:
        records = await _fetch_records(request, store_id=store_id)
        product_sales: Dict[str, Any] = {}
        for record in records:
            if record.get("type") not in ("revenue", "purchase"):
                continue
            items = record.get("items", [])
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except Exception:
                    items = []
            if not isinstance(items, list):
                continue
            for item in items:
                name = item.get("name", "未知")
                if name not in product_sales:
                    product_sales[name] = {"name": name, "category": item.get("category", ""), "quantity": 0, "revenue": 0.0, "cost": 0.0}
                qty = item.get("quantity", 1)
                amt = item.get("amount", 0)
                if record.get("type") == "revenue":
                    product_sales[name]["quantity"] += qty
                    product_sales[name]["revenue"] += amt
                elif record.get("type") == "purchase":
                    product_sales[name]["cost"] += amt

        sorted_products = sorted(product_sales.values(), key=lambda x: x["revenue"], reverse=True)
        top_sellers = sorted_products[:5]
        slow_sellers = sorted_products[-3:] if len(sorted_products) >= 3 else []

        # 补货建议：库存<10或近期无销量
        restock_suggestions = []
        for p in slow_sellers:
            if p["quantity"] < 10:
                restock_suggestions.append({"name": p["name"], "category": p["category"], "reason": f"销量偏低({p['quantity']}件),建议补货", "suggested_qty": 20})

        return {"success": True, "top_sellers": top_sellers, "slow_sellers": slow_sellers, "restock_suggestions": restock_suggestions}
    except Exception as e:
        logger.error(f"款式分析失败: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/alerts")
@endpoint_timeout(5.0)
async def get_alerts(request: Request, period: str = "month", store_id: str = "all"):
    """异常预警API - 规则引擎（5类异常检测）"""
    try:
        user = await get_current_user(request)
        org_id = user.org_id if user else "org_default"

        records = await repo.get_records(org_id=org_id, limit=10000)
        if store_id and store_id != "all":
            records = [r for r in records if r.get("store_id") == store_id]

        approved = [r for r in records if r.get("status") == "approved"]
        alerts: List[Dict[str, Any]] = []

        total_revenue = sum(r.get("total_amount", 0) for r in approved if r.get("type") == "revenue")
        total_cost = sum(r.get("total_amount", 0) for r in approved if r.get("type") in ("purchase",))
        total_expense = sum(r.get("total_amount", 0) for r in approved if r.get("type") == "expense")
        total_returns = sum(r.get("total_amount", 0) for r in approved if r.get("type") == "return")

        gross_profit = total_revenue - total_cost
        gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0

        # 规则1: 毛利率异常
        if gross_margin < 30 and total_revenue > 0:
            level = "critical" if gross_margin < 20 else "warning"
            alerts.append({"type": "low_margin", "level": level, "message": f"整体毛利率{gross_margin:.1f}%偏低(阈值30%)，建议检查进货成本", "value": round(gross_margin, 1), "threshold": 30})
        if gross_margin < 0:
            alerts.append({"type": "negative_margin", "level": "critical", "message": f"毛利率为负({gross_margin:.1f}%)，存在严重亏损风险", "value": round(gross_margin, 1)})

        # 规则2: 门店营收偏离
        store_rev: Dict[str, float] = {}
        for r in approved:
            if r.get("type") == "revenue":
                sid = r.get("store_id", "unknown")
                store_rev[sid] = store_rev.get(sid, 0) + r.get("total_amount", 0)
        if store_rev:
            avg_rev = sum(store_rev.values()) / len(store_rev)
            for sid, rev in store_rev.items():
                if avg_rev > 0 and rev > avg_rev * 1.5:
                    alerts.append({"type": "store_high", "level": "info", "message": f"门店{sid}营收¥{rev:,.0f}超出均值50%，请确认数据无误", "value": rev, "store_id": sid})
                if avg_rev > 0 and rev < avg_rev * 0.5:
                    alerts.append({"type": "store_low", "level": "warning", "message": f"门店{sid}营收¥{rev:,.0f}低于均值50%，需关注经营状况", "value": rev, "store_id": sid})

        # 规则3: 品类结构异常
        cat_rev: Dict[str, float] = {}
        for r in approved:
            if r.get("type") == "revenue":
                items = r.get("items", [])
                if isinstance(items, str):
                    try:
                        items = json.loads(items)
                    except Exception:
                        items = []
                if isinstance(items, list):
                    for item in items:
                        cat = item.get("category", "其他")
                        cat_rev[cat] = cat_rev.get(cat, 0) + item.get("amount", 0)
        if cat_rev and total_revenue > 0:
            for cat, amt in cat_rev.items():
                ratio = amt / total_revenue * 100
                if ratio > 60:
                    alerts.append({"type": "category_concentration", "level": "warning", "message": f"品类「{cat}」占营收{ratio:.1f}%，经营过于集中", "value": round(ratio, 1), "category": cat})

        # 规则4: 退货率过高
        if total_returns > total_revenue * 0.1 and total_revenue > 0:
            return_rate = total_returns / total_revenue * 100
            alerts.append({"type": "high_returns", "level": "warning" if return_rate < 20 else "critical", "message": f"退货率达{return_rate:.1f}%，需关注商品质量", "value": round(return_rate, 1), "threshold": 10})

        # 规则5: 费用占比异常
        if total_revenue > 0:
            expense_ratio = (total_expense / total_revenue) * 100
            if expense_ratio > 30:
                alerts.append({"type": "high_expense", "level": "warning" if expense_ratio < 50 else "critical", "message": f"费用占营收{expense_ratio:.1f}%，高于30%警戒线", "value": round(expense_ratio, 1), "threshold": 30})

        if not alerts:
            alerts.append({"type": "info", "level": "info", "message": "暂无异常，经营状况正常", "value": 0})

        return {"success": True, "alerts": alerts, "summary": {"total_revenue": total_revenue, "total_cost": total_cost, "total_expense": total_expense, "total_returns": total_returns, "gross_margin": round(gross_margin, 1)}}
    except Exception as e:
        logger.error(f"异常预警失败: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/history")
@endpoint_timeout(5.0)
async def get_history(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    record_type: Optional[str] = None,
    store_id: Optional[str] = None,
    status: Optional[str] = None
):
    """历史记录查询（增强版，支持多维度筛选）"""
    try:
        user = await get_current_user(request)
        org_id = user.org_id if user else "org_default"

        records = await repo.get_records(org_id=org_id, limit=10000)
        if not records:
            return {"success": True, "records": [], "total": 0, "page": page, "total_pages": 0}

        # 筛选
        filtered = []
        for r in records:
            if start_date and r.get("created_at", "")[:10] < start_date:
                continue
            if end_date and r.get("created_at", "")[:10] > end_date:
                continue
            if record_type and r.get("type") != record_type:
                continue
            if store_id and store_id != "all" and r.get("store_id") != store_id:
                continue
            if status and r.get("status") != status:
                continue
            filtered.append(r)

        # 按时间倒序
        filtered.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # 分页
        total = len(filtered)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start_idx = (page - 1) * page_size
        page_records = filtered[start_idx:start_idx + page_size]

        # 格式化时间戳
        for r in page_records:
            if "created_at" in r and r["created_at"]:
                dt_str = r["created_at"]
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    r["created_at_display"] = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    r["created_at_display"] = dt_str[:16]

        return {
            "success": True,
            "records": page_records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
    except Exception as e:
        logger.error(f"历史记录查询失败: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/pending_reviews")
@endpoint_timeout(5.0)
async def get_pending_reviews(request: Request):
    """获取待审核记录（审核中心专用）"""
    try:
        user = await get_current_user(request)
        if not user:
            return {"success": False, "error": "未登录"}

        if user.role not in ("owner", "manager"):
            return {"success": False, "error": "无审核权限"}

        org_id = user.org_id
        records = await repo.get_records(org_id=org_id, limit=10000)

        pending = [r for r in records if r.get("status") == "pending"]
        approved = [r for r in records if r.get("status") == "approved"]
        rejected = [r for r in records if r.get("status") == "rejected"]

        # 按时间倒序
        pending.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return {
            "success": True,
            "pending": pending,
            "stats": {
                "pending_count": len(pending),
                "approved_count": len(approved),
                "rejected_count": len(rejected),
                "total_count": len(records)
            },
            "can_review": user.role in ("owner", "manager")
        }
    except Exception as e:
        logger.error(f"待审核查询失败: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/reviews")
@endpoint_timeout(5.0)
async def get_reviews(request: Request):
    """获取待审核记录"""
    try:
        all_records = await _fetch_records(request)
        
        # 解析用户角色
        from utils.auth import decode_token
        auth_header = request.headers.get("Authorization", "")
        user_role = "owner"
        if auth_header.startswith("Bearer "):
            payload = decode_token(auth_header[7:])
            if payload:
                user_role = payload.get("role", user_role)
        
        pending = [r for r in all_records if r.get("status") == "pending"]
        approved_count = len([r for r in all_records if r.get("status") == "approved"])
        rejected_count = len([r for r in all_records if r.get("status") == "rejected"])
        can_review = user_role in ("owner", "manager")
        
        pending.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return {
            "success": True,
            "pending": pending,
            "stats": {
                "pending_count": len(pending),
                "approved_count": approved_count,
                "rejected_count": rejected_count
            },
            "can_review": can_review
        }
    except Exception as e:
        logger.error(f"获取审核记录失败: {e}")
        return {"success": False, "pending": [], "error": str(e)}

# ==================== 登录鉴权API ====================

@app.post("/api/auth/login")
async def api_login(request: Request):
    """用户登录API"""
    from utils.auth import verify_password, create_token
    
    try:
        payload = await request.json()
        username = payload.get("username", "")
        password = payload.get("password", "")
        
        user_data = await repo.get_user_by_username(username)
        if not user_data:
            return {"success": False, "message": "用户不存在"}
        
        if not verify_password(password, user_data.get("password_hash", "")):
            return {"success": False, "message": "密码错误"}
        
        if not user_data.get("is_active", True):
            return {"success": False, "message": "账号已被禁用"}
        
        # 生成Token
        user_id = str(user_data.get("id", ""))
        role = user_data.get("role", "")
        org_id = str(user_data.get("org_id", ""))
        store_ids = user_data.get("store_ids", []) or []
        token = create_token(user_id, role, org_id, store_ids)
        
        # 更新登录时间
        await repo.update_user_login_time(user_id)
        
        return {
            "success": True,
            "token": token,
            "user": {
                "user_id": user_id,
                "username": user_data.get("username", ""),
                "name": user_data.get("name", ""),
                "role": role,
                "org_id": org_id,
                "store_ids": store_ids
            }
        }
    except Exception as e:
        logger.error(f"登录失败: {e}")
        return {"success": False, "message": "登录失败，请稍后重试"}

@app.post("/api/auth/verify")
async def api_verify_token(request: Request):
    """验证Token有效性"""
    from utils.auth import decode_token
    
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return {"valid": False, "message": "缺少Token"}
    
    token = auth_header[7:]
    payload = decode_token(token)
    
    if not payload:
        return {"valid": False, "message": "Token无效或已过期"}
    
    user_data = await repo.get_user_by_id(payload.get("user_id"))
    if not user_data:
        return {"valid": False, "message": "用户不存在"}
    
    return {
        "valid": True,
        "user": {
            "user_id": str(user_data.get("id", "")),
            "username": user_data.get("username", ""),
            "name": user_data.get("name", ""),
            "role": user_data.get("role", ""),
            "org_id": str(user_data.get("org_id", "")),
            "store_ids": user_data.get("store_ids", []) or []
        }
    }

@app.post("/api/auth/logout")
async def api_logout():
    """用户登出"""
    return {"success": True, "message": "登出成功"}

# ==================== 商品管理API ====================

@app.get("/api/products")
async def get_products(request: Request):
    """获取商品列表（asyncpg 异步查询）"""
    from utils.auth import decode_token
    
    auth_header = request.headers.get("Authorization", "")
    org_id = "org_default"
    
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload:
            org_id = payload.get("org_id", org_id)
    
    try:
        products = await repo.get_products(org_id)
        return {"success": True, "products": products, "total": len(products)}
    except Exception as e:
        logger.error(f"数据库查询商品失败: {e}")
        return {"success": False, "products": [], "error": str(e)}

@app.post("/api/products")
async def create_product_api(request: Request):
    """创建商品"""
    from utils.auth import decode_token
    
    auth_header = request.headers.get("Authorization", "")
    org_id = "org_default"
    
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload:
            org_id = payload.get("org_id", org_id)
    
    # 读取 merge_duplicates 查询参数
    merge_duplicates = request.query_params.get("merge_duplicates", "false").lower() == "true"
    
    try:
        data = await request.json()
        product = await repo.insert_product({
            "org_id": org_id,
            "sku": data.get("sku", ""),
            "name": data.get("name", ""),
            "category": data.get("category", ""),
            "cost_price": float(data.get("cost_price", 0) or 0),
            "sale_price": float(data.get("sale_price", 0) or 0),
            "stock": int(data.get("stock", 0) or 0)
        }, merge_duplicate_sku=merge_duplicates)
        return {"success": True, "product": product}
    except Exception as e:
        logger.error(f"创建商品失败: {e}")
        return {"success": False, "message": str(e)}

@app.put("/api/products/{product_id}")
async def update_product_api(product_id: str, request: Request):
    """更新商品"""
    try:
        data = await request.json()
        updates = {}
        for key in ["sku", "name", "category", "cost_price", "sale_price", "stock"]:
            if key in data:
                updates[key] = data[key]
        updated = await repo.update_product(product_id, updates)
        if updated:
            return {"success": True, "product": updated}
        return {"success": False, "message": "商品不存在"}
    except Exception as e:
        logger.error(f"更新商品失败: {e}")
        return {"success": False, "message": str(e)}

@app.delete("/api/products/{product_id}")
async def delete_product_api(product_id: str):
    """删除商品"""
    try:
        deleted = await repo.delete_product(product_id)
        if deleted:
            return {"success": True, "message": "删除成功"}
        return {"success": False, "message": "商品不存在"}
    except Exception as e:
        logger.error(f"删除商品失败: {e}")
        return {"success": False, "message": str(e)}


@app.post("/api/products/batch-delete")
async def batch_delete_products_api(request: Request):
    """批量删除商品"""
    try:
        data = await request.json()
        product_ids = data.get("product_ids", [])
        
        if not product_ids or not isinstance(product_ids, list):
            return {"success": False, "message": "请提供要删除的商品ID列表"}
        
        deleted_count = 0
        for pid in product_ids:
            if await repo.delete_product(pid):
                deleted_count += 1
        
        logger.info(f"批量删除商品: 请求{len(product_ids)}个, 成功{deleted_count}个")
        return {"success": True, "deleted_count": deleted_count, "message": f"成功删除 {deleted_count} 个商品"}
        
    except Exception as e:
        logger.error(f"批量删除商品失败: {e}")
        return {"success": False, "message": str(e)}


@app.post("/api/products/import")
async def import_products_api(request: Request):
    """批量导入商品（Excel文件）"""
    from utils.auth import decode_token
    from utils.product_import import (
        build_product_from_row,
        normalize_product_columns,
        read_product_spreadsheet,
    )
    
    try:
        # 获取认证信息
        auth_header = request.headers.get("Authorization", "")
        org_id = "org_default"
        
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = decode_token(token)
            if payload:
                org_id = payload.get("org_id", org_id)
        
        # 获取查询参数
        merge_duplicates = request.query_params.get("merge_duplicates", "false").lower() == "true"
        
        # 读取上传的文件
        form = await request.form()
        file = form.get("file")
        if not file:
            return {"success": False, "message": "未找到上传文件"}
        
        content = await file.read()
        filename = file.filename or "unknown.xlsx"

        df = normalize_product_columns(read_product_spreadsheet(content, filename))
        
        logger.info(f"Excel解析成功，共{len(df)}行，列名: {list(df.columns)}")
        if df.empty:
            return {"success": False, "message": "导入失败：表格中没有可导入的数据"}

        success_count = 0
        fail_count = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                product_data = build_product_from_row(row, org_id)
                await repo.insert_product(product_data, merge_duplicate_sku=merge_duplicates)
                success_count += 1
                
            except Exception as e:
                fail_count += 1
                errors.append(f"第{idx+1}行: {str(e)}")
        
        logger.info(f"导入完成: 成功{success_count}条, 失败{fail_count}条")
        
        ok = success_count > 0 or fail_count == 0
        message = f"导入完成：成功 {success_count} 条，失败 {fail_count} 条"
        if success_count == 0 and errors:
            message += f"；首个错误：{errors[0]}"

        return {
            "success": ok,
            "message": message,
            "success_count": success_count,
            "fail_count": fail_count,
            "errors": errors[:10]  # 只返回前10个错误
        }
        
    except Exception as e:
        logger.error(f"Excel导入失败: {e}")
        return {"success": False, "message": f"导入失败: {str(e)}"}


# ==================== 静态页面路由 ====================

@app.get("/login.html", response_class=HTMLResponse)
async def login_page():
    """登录页面"""
    html_path = os.path.join(_static_dir, "login.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>登录页面不存在</h1>", status_code=404)

@app.get("/mobile.html", response_class=HTMLResponse)
async def mobile_page():
    """店长移动端页面"""
    html_path = os.path.join(_static_dir, "mobile.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>移动端页面不存在</h1>", status_code=404)

@app.get("/products.html", response_class=HTMLResponse)
async def products_page():
    """商品管理页面"""
    html_path = os.path.join(_static_dir, "products.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>商品管理页面不存在</h1>", status_code=404)

# ==================== 门店管理API ====================

@app.get("/api/stores/list")
async def get_stores_list(request: Request):
    """获取门店列表（带权限过滤）"""
    from utils.auth import decode_token
    
    auth_header = request.headers.get("Authorization", "")
    org_id = "org_default"
    user_store_ids = None
    user_role = "owner"
    
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload:
            org_id = payload.get("org_id", org_id)
            user_store_ids = payload.get("store_ids")
            user_role = payload.get("role", "owner")
    
    all_stores = await repo.get_stores(org_id)
    
    # 店长只能看到自己负责的门店
    if user_store_ids is not None and user_role == "manager":
        all_stores = [s for s in all_stores if s.get("store_id") in user_store_ids]
    
    return {
        "success": True,
        "stores": all_stores
    }

# ==================== 语音/图片上传API ====================

@app.post("/api/voice/upload")
async def upload_voice(file: UploadFile = File(...), store_id: str = ""):
    """语音上传并识别"""
    from coze_coding_dev_sdk import AudioClient
    import tempfile
    
    try:
        ctx = new_context(method="upload_voice")
        
        # 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # ASR识别
        audio_client = AudioClient(ctx=ctx)
        
        with open(tmp_path, "rb") as audio_file:
            result = await run_sync(audio_client.asr, audio_file.read())
        
        # 清理临时文件
        os.unlink(tmp_path)
        
        recognized_text = result.get("text", "") if isinstance(result, dict) else str(result)
        
        # 调用工作流进行NLU提取
        payload = {
            "input_type": "voice",
            "text": recognized_text,
            "store_id": store_id
        }
        
        nlu_result = await service.run(payload, ctx)
        
        return {
            "success": True,
            "recognized_text": recognized_text,
            "extracted_data": nlu_result.get("extracted_data", {}),
            **nlu_result
        }
    except Exception as e:
        logger.error(f"语音上传失败: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/image/upload")
async def upload_image(file: UploadFile = File(...), store_id: str = ""):
    """图片上传并识别"""
    from coze_coding_dev_sdk import S3SyncStorage
    
    try:
        ctx = new_context(method="upload_image")
        
        # 上传图片到对象存储
        storage = S3SyncStorage()
        content = await file.read()
        
        import time
        timestamp = int(time.time() * 1000)
        filename = f"upload_{timestamp}_{file.filename}"
        content_type = file.content_type or "application/octet-stream"
        
        image_url = await run_sync(
            storage.upload_file,
            file_content=content,
            file_name=filename,
            content_type=content_type
        )
        
        # 调用工作流进行OCR识别
        payload = {
            "input_type": "image",
            "image_file": {"url": image_url, "file_type": "image"},
            "store_id": store_id
        }
        
        ocr_result = await service.run(payload, ctx)
        
        return {
            "success": True,
            "image_url": image_url,
            "extracted_data": ocr_result.get("extracted_data", {}),
            **ocr_result
        }
    except Exception as e:
        logger.error(f"图片上传失败: {e}")
        return {"success": False, "error": str(e)}

# ==================== 报告导出API ====================

@app.post("/api/report/export")
async def export_report(request: Request):
    """导出经营报告 (PDF/DOCX/XLSX)"""
    from graphs.nodes.report_export_node import report_export_node, ReportExportInput
    
    try:
        data = await request.json()
        
        # 构建输入
        report_input = ReportExportInput(
            report_type=data.get("report_type", "pdf"),
            period=data.get("period", "month"),
            start_date=data.get("start_date", ""),
            end_date=data.get("end_date", ""),
            summary=data.get("summary", {}),
            store_stats=data.get("store_stats", {}),
            category_stats=data.get("category_stats", {}),
            trend_data=data.get("trend_data", []),
            anomaly_alerts=data.get("anomaly_alerts", []),
            product_analysis=data.get("product_analysis", {}),
            org_name=data.get("org_name", "服装连锁")
        )
        
        # 调用报告生成
        from coze_coding_utils.runtime_ctx.context import Context
        ctx = new_context(method="report_export")
        runtime = type('Runtime', (), {'context': ctx})()
        config = {"configurable": {}}
        
        result = await run_sync(report_export_node, report_input, config, runtime)
        
        return {
            "success": result.success,
            "report_url": result.report_url,
            "report_type": result.report_type,
            "message": result.message
        }
    except Exception as e:
        logger.error(f"报告导出失败: {e}")
        return {"success": False, "error": str(e)}

# ==================== Surya OCR API ====================

@app.post("/api/ocr/image")
async def ocr_image(request: Request):
    """
    Surya OCR 图片识别接口
    
    使用专业的 Surya OCR 引擎识别图片中的文字和表格。
    支持中英文混合、表格结构识别。
    
    Body:
        image_url: 图片URL
        languages: 语言列表，默认 ["zh", "en"]
    
    Returns:
        {
            "success": true,
            "text": "识别的完整文本",
            "lines": [{"text": "行文本", "bbox": [x1,y1,x2,y2]}, ...],
            "markdown": "表格Markdown格式（如果检测到表格）"
        }
    """
    try:
        body = await request.json()
        image_url = body.get("image_url", "")
        languages = body.get("languages", ["zh", "en"])
        
        if not image_url:
            raise HTTPException(status_code=400, detail="请提供 image_url")
        
        from utils.surya_ocr import surya_ocr_async, surya_table_async
        
        # 执行 OCR
        ocr_result = await surya_ocr_async(image_url, languages)
        
        if not ocr_result.get("success"):
            return {
                "success": False,
                "error": ocr_result.get("error", "OCR识别失败"),
                "text": "",
                "lines": []
            }
        
        # 尝试检测表格结构
        try:
            table_result = await surya_table_async(image_url)
            markdown = table_result.get("markdown", "") if table_result.get("success") else ""
        except Exception:
            markdown = ""
        
        return {
            "success": True,
            "text": ocr_result.get("text", ""),
            "lines": ocr_result.get("lines", []),
            "markdown": markdown,
            "line_count": len(ocr_result.get("lines", []))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR识别失败: {e}")
        return {"success": False, "error": str(e), "text": "", "lines": []}


# ==================== 飞书通知API ====================

@app.post("/api/notify/feishu")
async def send_feishu_notification(request: Request):
    """发送飞书通知"""
    from utils.feishu_notify import send_anomaly_alert, send_daily_report, send_inventory_alert, send_text_message
    
    try:
        data = await request.json()
        notify_type = data.get("type", "text")
        
        if notify_type == "anomaly":
            result = send_anomaly_alert(
                store_name=data.get("store_name", ""),
                alerts=data.get("alerts", []),
                dashboard_url=data.get("dashboard_url")
            )
        elif notify_type == "daily_report":
            result = send_daily_report(
                store_name=data.get("store_name", ""),
                summary=data.get("summary", {}),
                top_products=data.get("top_products"),
                report_url=data.get("report_url")
            )
        elif notify_type == "inventory":
            result = send_inventory_alert(
                store_name=data.get("store_name", ""),
                low_stock_items=data.get("low_stock_items", [])
            )
        else:
            result = send_text_message(data.get("text", ""))
        
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"飞书通知发送失败: {e}")
        return {"success": False, "error": str(e)}

# ==================== 表格识别API ====================

@app.post("/api/table/recognize")
async def recognize_table(request: Request):
    """用多模态大模型识别表格图片/文件，返回结构化数据并可选自动导入

    请求体:
    - image_url: 图片URL（拍照/截图的表格）
    - file_url:  文件URL（Excel/PDF等）
    - table_text: 表格文本（前端解析Excel后的JSON字符串）
    - import_type: 导入类型 "products"(商品) | "records"(记录)，空则只识别不导入
    - org_id: 组织ID
    - store_id: 门店ID（records导入时需要）
    - rows: 直接传入已识别的行数据（确认导入时用，跳过识别步骤）
    - table_type: 直接传入表格类型（配合rows使用）
    """
    import re as _re
    import uuid

    body = await request.json()
    image_url: str = body.get("image_url", "")
    image_base64: str = body.get("image_base64", "")  # 前端直接传base64
    file_url: str = body.get("file_url", "")
    table_text: str = body.get("table_text", "")
    import_type: str = body.get("import_type", "")
    org_id: str = body.get("org_id", "org_default")
    store_id: str = body.get("store_id", "")
    direct_rows: list = body.get("rows", [])
    direct_table_type: str = body.get("table_type", "")
    merge_duplicate: bool = body.get("merge_duplicate", True)  # 合并重复款号（库存累加）

    if not image_url and not image_base64 and not file_url and not table_text and not direct_rows:
        raise HTTPException(status_code=400, detail="请提供 image_url、image_base64、file_url、table_text 或 rows")

    # 如果直接传入了 rows（确认导入步骤），跳过识别
    if direct_rows:
        table_type: str = direct_table_type or import_type or "products"
        rows: list = direct_rows
        result: Dict[str, Any] = {
            "success": True,
            "table_type": table_type,
            "row_count": len(rows),
            "rows": rows,
            "imported": 0
        }
    else:
        # ===== 识别流程 =====
        try:
            from coze_coding_dev_sdk import LLMClient
            from langchain_core.messages import SystemMessage, HumanMessage

            # 1. 读取文件内容（根据文件类型选择解析方式）
            text_content: str = ""
            table_markdown: str = ""
            
            if file_url:
                # 判断文件类型
                file_lower = file_url.lower()
                is_excel = file_lower.endswith('.xlsx') or file_lower.endswith('.xls') or file_lower.endswith('.csv')
                
                if is_excel:
                    # Excel/CSV 文件：用 pandas 解析成 Markdown 表格
                    try:
                        import pandas as pd
                        import tempfile
                        import os
                        import requests
                        
                        # 下载文件到临时目录
                        resp = requests.get(file_url, timeout=30)
                        resp.raise_for_status()
                        
                        suffix = '.xlsx' if file_lower.endswith('.xlsx') else '.xls' if file_lower.endswith('.xls') else '.csv'
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                            tmp.write(resp.content)
                            tmp_path = tmp.name
                        
                        try:
                            if suffix == '.csv':
                                df = pd.read_csv(tmp_path, encoding='utf-8-sig')
                            else:
                                df = pd.read_excel(tmp_path, engine='openpyxl' if suffix == '.xlsx' else 'xlrd')
                            
                            # 转成 Markdown 表格
                            table_markdown = df.to_markdown(index=False, tablefmt='pipe')
                            text_content = f"Excel表格内容（{len(df)}行 x {len(df.columns)}列）：\n\n{table_markdown}"
                            logger.info(f"Excel解析成功: {len(df)}行, 列: {list(df.columns)}")
                        finally:
                            os.unlink(tmp_path)
                    except Exception as ex:
                        logger.warning(f"Excel解析失败，尝试文本提取: {ex}")
                        from utils.file.file import File, FileOps
                        f = File(url=file_url)
                        try:
                            text_content = FileOps.extract_text(f)
                        except Exception as ex2:
                            logger.error(f"文件提取也失败: {ex2}")
                else:
                    # 非Excel文件（PDF等）：用文本提取
                    from utils.file.file import File, FileOps
                    f = File(url=file_url)
                    try:
                        text_content = FileOps.extract_text(f)
                    except Exception as ex:
                        logger.warning(f"文件提取失败: {ex}")

            # 1.5 处理前端传来的已解析表格文本（优先使用）
            if table_text:
                text_content = f"表格数据：\n{table_text}"
                logger.info(f"使用前端解析的表格数据: {len(table_text)} 字符")

            # 1.6 图片OCR：使用 Surya 专业OCR引擎
            if (image_url or image_base64) and not table_text:
                try:
                    from utils.surya_ocr import surya_ocr_async
                    import base64 as b64
                    import tempfile
                    
                    # 处理base64图片：保存为临时文件
                    ocr_image_url = image_url
                    if image_base64 and not image_url:
                        # 去掉data:image/xxx;base64,前缀
                        base64_data = image_base64
                        if "," in base64_data:
                            base64_data = base64_data.split(",")[1]
                        img_bytes = b64.b64decode(base64_data)
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                            tmp.write(img_bytes)
                            ocr_image_url = f"file://{tmp.name}"
                            logger.info(f"base64图片已保存到临时文件: {tmp.name}")
                    
                    surya_result = await surya_ocr_async(ocr_image_url, languages=["zh", "en"])
                    if surya_result.get("success") and surya_result.get("text"):
                        text_content = f"图片OCR识别结果：\n{surya_result['text']}"
                        logger.info(f"Surya OCR成功: {len(surya_result.get('lines', []))}行文本")
                    else:
                        logger.warning(f"Surya OCR失败: {surya_result.get('error', '未知错误')}")
                        # 降级：保留 image_base64 让多模态LLM直接处理
                except Exception as ex:
                    logger.warning(f"Surya OCR异常: {ex}，降级使用多模态LLM")

            # 2. 构造多模态消息
            system_prompt: str = """你是服装连锁店的表格识别专家。用户会上传一张表格图片或一段表格文本，你需要精确识别其中所有数据。

**识别规则**：
1. 仔细识别表格中每一行每一列的数据，不要遗漏任何一行
2. 数字字段不要带单位符号（如¥、元、件等），只保留纯数字
3. 如果某列数据缺失，用 null 表示
4. 保持原始数据的精确性，不要四舍五入或估算
5. 如果表头是中文，请根据含义映射到对应字段

**输出格式**：严格返回JSON，不要包含任何其他文字说明：

如果表格是商品清单（含SKU/品名/进价/售价/库存等）：
```json
{
  "table_type": "products",
  "rows": [
    {"sku": "SKU001", "name": "红色连衣裙", "category": "连衣裙", "cost_price": 120, "sale_price": 299, "stock": 50},
    {"sku": "SKU002", "name": "白色T恤", "category": "T恤", "cost_price": 45, "sale_price": 129, "stock": 200}
  ]
}
```

如果表格是进销存记录（含日期/品名/数量/金额/类型等）：
```json
{
  "table_type": "records",
  "rows": [
    {"date": "2025-05-20", "type": "revenue", "name": "红色连衣裙", "category": "连衣裙", "quantity": 3, "amount": 897, "store_name": "中山路店"},
    {"date": "2025-05-20", "type": "purchase", "name": "白色T恤", "category": "T恤", "quantity": 50, "amount": 2250, "store_name": "中山路店"}
  ]
}
```

如果无法判断类型，优先按商品清单输出。"""

            user_parts: list = []
            file_hint: str = ""
            if text_content:
                # 增加 字符限制，支持更多表格数据
                max_chars: int = 8000
                truncated: str = text_content[:max_chars]
                if len(text_content) > max_chars:
                    truncated += f"\n... (已截断，共{len(text_content)}字符)"
                file_hint = f"\n\n以下是表格数据（Markdown格式）：\n{truncated}"

            user_parts.append({
                "type": "text",
                "text": f"请仔细识别表格中的所有行和列，返回完整的结构化JSON。{file_hint}"
            })

            if image_url:
                user_parts.append({
                    "type": "image_url",
                    "image_url": {"url": image_url}
                })
            elif image_base64:
                # 确保 base64 格式正确
                img_url = image_base64
                if not img_url.startswith("data:"):
                    img_url = f"data:image/png;base64,{image_base64}"
                user_parts.append({
                    "type": "image_url",
                    "image_url": {"url": img_url}
                })

            client = LLMClient()
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_parts)
            ]

            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.invoke(
                        messages=messages,
                        model="doubao-seed-1-8-251228",
                        temperature=0.1,
                        max_completion_tokens=8192
                    )
                ),
                timeout=60.0
            )

            # 3. 解析大模型返回
            raw_content = response.content
            if isinstance(raw_content, list):
                text_parts: list = []
                for item in raw_content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        text_parts.append(item)
                raw_content = " ".join(text_parts)

            raw_content = str(raw_content).strip()

            # 提取JSON（可能被markdown代码块包裹）
            json_match = _re.search(r'```(?:json)?\s*([\s\S]*?)```', raw_content)
            if json_match:
                json_str: str = json_match.group(1).strip()
            else:
                json_str = raw_content

            table_data: dict = json.loads(json_str)
            table_type = table_data.get("table_type", "products")
            rows = table_data.get("rows", [])

            result = {
                "success": True,
                "table_type": table_type,
                "row_count": len(rows),
                "rows": rows,
                "imported": 0
            }

        except json.JSONDecodeError as e:
            logger.error(f"表格识别JSON解析失败: {e}")
            return {"success": False, "error": f"识别结果解析失败: {str(e)}", "raw": raw_content[:500] if 'raw_content' in dir() else ""}
        except asyncio.TimeoutError:
            return {"success": False, "error": "识别超时，请重试"}
        except Exception as e:
            logger.error(f"表格识别失败: {e}")
            return {"success": False, "error": str(e)}

    # ===== 自动导入到数据库 =====
    if import_type and rows:
        from storage.database import repository as repo

        imported_count: int = 0
        merged_count: int = 0  # 合并的商品数
        for row in rows:
            try:
                if import_type == "products" or table_type == "products":
                    result = await repo.insert_product({
                        "org_id": org_id,
                        "sku": row.get("sku", ""),
                        "name": row.get("name", ""),
                        "category": row.get("category", "其他"),
                        "cost_price": float(row.get("cost_price", 0) or 0),
                        "sale_price": float(row.get("sale_price", 0) or 0),
                        "stock": int(row.get("stock", 0) or 0),
                    }, merge_duplicate_sku=merge_duplicate)
                    imported_count += 1
                    if result and result.get("merged"):
                        merged_count += 1
                elif import_type == "records" or table_type == "records":
                    items: list = [{
                        "name": row.get("name", ""),
                        "quantity": int(row.get("quantity", 1) or 1),
                        "amount": float(row.get("amount", 0) or 0),
                        "category": row.get("category", ""),
                    }]
                    await repo.insert_record({
                        "id": f"rec_{uuid.uuid4().hex[:12]}",
                        "org_id": org_id,
                        "store_id": store_id or "store_001",
                        "store_name": row.get("store_name", ""),
                        "type": row.get("type", "revenue"),
                        "category": row.get("category", ""),
                        "items": items,
                        "total_amount": float(row.get("amount", 0) or 0),
                        "status": "pending",
                        "operator": "表格导入",
                    })
                    imported_count += 1
            except Exception as ex:
                logger.warning(f"导入行失败: {ex}, row={row}")

        result["imported"] = imported_count
        if import_type == "products" or table_type == "products":
            result["merged"] = merged_count

    return result


# ==================== 智能表格识别API ====================

@app.post("/api/table/smart-recognize")
async def smart_recognize_table(request: Request):
    """使用大模型智能识别表格，提取商品信息和连带关系
    
    请求体:
    - image_url: 图片URL
    - image_base64: 图片base64编码
    - file_content: Excel/CSV文件base64编码
    - table_text: Markdown格式的表格文本（前端解析Excel后传入）
    - filename: 文件名（用于判断文件类型）
    - table_type: 表格类型 (auto/products/purchase/sales)
    - import_after: 是否识别后自动导入 (默认false，只返回结果)
    - analyze_relations: 是否分析连带关系 (默认true)
    """
    import base64 as b64
    
    body = await request.json()
    image_url: str = body.get("image_url", "")
    image_base64: str = body.get("image_base64", "")
    file_content: str = body.get("file_content", "")  # base64编码的文件内容
    table_text: str = body.get("table_text", "")  # Markdown格式的表格文本
    filename: str = body.get("filename", "")
    table_type: str = body.get("table_type", "auto")
    import_after: bool = body.get("import_after", False)
    analyze_relations: bool = body.get("analyze_relations", True)
    
    from utils.smart_table_recognition import (
        recognize_table_with_llm,
        recognize_excel_with_llm,
        recognize_text_table_with_llm,
        analyze_product_relations
    )
    
    try:
        result = {"success": False, "items": [], "relations": [], "summary": {}}
        
        # 1. 处理图片
        if image_url or image_base64:
            # 如果是base64图片，确保格式正确
            if image_base64 and not image_base64.startswith("data:"):
                image_base64 = f"data:image/jpeg;base64,{image_base64}"
            
            result = await recognize_table_with_llm(
                image_url=image_url,
                image_base64=image_base64,
                table_type=table_type
            )
        
        # 2. 处理Markdown表格文本（前端解析Excel后传入）
        elif table_text:
            result = await recognize_text_table_with_llm(table_text, table_type)
        
        # 3. 处理Excel/CSV文件（base64编码）
        elif file_content:
            # 解码base64文件内容
            file_bytes = b64.b64decode(file_content)
            result = await recognize_excel_with_llm(file_bytes, filename)
        
        else:
            return {"success": False, "error": "请提供 image_url、image_base64、file_content 或 table_text"}
        
        # 3. 分析连带关系
        if result.get("success") and analyze_relations and result.get("items"):
            items = result.get("items", [])
            if len(items) >= 2:
                relations = await analyze_product_relations(items)
                result["relations"] = relations
        
        # 4. 自动导入（如果需要）
        if result.get("success") and import_after and result.get("items"):
            imported_count = 0
            for item in result["items"]:
                try:
                    await repo.insert_product({
                        "org_id": "org_default",
                        "sku": item.get("sku", ""),
                        "name": item.get("name", ""),
                        "category": item.get("category", "其他"),
                        "cost_price": float(item.get("cost_price", 0) or 0),
                        "sale_price": float(item.get("sale_price", 0) or 0),
                        "stock": int(item.get("stock", 0) or 0)
                    }, merge_duplicate_sku=True)
                    imported_count += 1
                except Exception as ex:
                    logger.warning(f"导入商品失败: {ex}")
            
            result["imported_count"] = imported_count
            result["message"] = f"成功识别 {len(result['items'])} 个商品，已导入 {imported_count} 个"
        
        return result
        
    except Exception as e:
        logger.error(f"智能表格识别失败: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/products/relations/{sku}")
async def get_product_relations_api(sku: str, org_id: str = "org_default"):
    """获取指定商品的连带关系"""
    try:
        # 获取商品信息
        products = await repo.get_products(org_id)
        target = None
        for p in products:
            if p.get("sku") == sku:
                target = p
                break
        
        if not target:
            return {"success": False, "error": "商品不存在"}
        
        # 获取同类别商品作为潜在关联
        same_category = [p for p in products if p.get("category") == target.get("category") and p.get("sku") != sku]
        
        # 使用大模型分析连带关系
        from utils.smart_table_recognition import analyze_product_relations
        all_items = [target] + same_category[:10]
        relations = await analyze_product_relations(all_items)
        
        # 过滤出与目标商品相关的连带关系
        related = []
        for r in relations:
            if sku in r.get("skus", []):
                related.append(r)
        
        return {
            "success": True,
            "product": target,
            "relations": related,
            "related_products": [p for p in same_category if any(r.get("skus", []) and p.get("sku") in r.get("skus", []) for r in relations)]
        }
        
    except Exception as e:
        logger.error(f"获取连带关系失败: {e}")
        return {"success": False, "error": str(e)}


# ==================== 商品知识库API ====================

@app.get("/api/products/search")
async def search_products_api(query: str, org_id: str = "org_default"):
    """搜索商品（知识库）"""
    from utils.product_knowledge import search_product
    
    try:
        results = search_product(query, org_id)
        return {"success": True, "products": results, "total": len(results)}
    except Exception as e:
        logger.error(f"商品搜索失败: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/products/categories")
async def get_categories_api(org_id: str = "org_default"):
    """获取商品类目列表"""
    from utils.product_knowledge import get_product_knowledge_base
    
    try:
        kb = get_product_knowledge_base(org_id)
        categories = kb.get_categories()
        return {"success": True, "categories": categories}
    except Exception as e:
        logger.error(f"获取类目失败: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/products/price-range")
async def get_price_range_api(
    product_name: str = None,
    category: str = None,
    org_id: str = "org_default"
):
    """获取商品价格范围"""
    from utils.product_knowledge import get_product_knowledge_base
    
    try:
        kb = get_product_knowledge_base(org_id)
        price_range = kb.get_price_range(product_name, category)
        return {"success": True, **price_range}
    except Exception as e:
        logger.error(f"获取价格范围失败: {e}")
        return {"success": False, "error": str(e)}

# ==================== 原有API路由 ====================


HEADER_X_RUN_ID = "x-run-id"
@app.post("/run")
async def http_run(request: Request) -> Dict[str, Any]:
    global result
    raw_body = await request.body()
    try:
        body_text = raw_body.decode("utf-8")
    except Exception as e:
        body_text = str(raw_body)
        raise HTTPException(status_code=400,
                            detail=f"Invalid JSON format: {body_text}, traceback: {traceback.format_exc()}, error: {e}")

    ctx = new_context(method="run", headers=request.headers)
    # 优先使用上游指定的 run_id，保证 cancel 能精确匹配
    upstream_run_id = request.headers.get(HEADER_X_RUN_ID)
    if upstream_run_id:
        ctx.run_id = upstream_run_id
    run_id = ctx.run_id
    request_context.set(ctx)

    logger.info(
        f"Received request for /run: "
        f"run_id={run_id}, "
        f"query={dict(request.query_params)}, "
        f"body={body_text}"
    )

    try:
        payload = await request.json()

        # 创建任务并记录 - 这是关键，让我们可以通过run_id取消任务
        task = asyncio.create_task(service.run(payload, ctx))
        service.running_tasks[run_id] = task

        try:
            result = await asyncio.wait_for(task, timeout=float(TIMEOUT_SECONDS))
        except asyncio.TimeoutError:
            logger.error(f"Run execution timeout after {TIMEOUT_SECONDS}s for run_id: {run_id}")
            task.cancel()
            try:
                result = await task
            except asyncio.CancelledError:
                return {
                    "status": "timeout",
                    "run_id": run_id,
                    "message": f"Execution timeout: exceeded {TIMEOUT_SECONDS} seconds"
                }

        if not result:
            result = {}
        if isinstance(result, dict):
            result["run_id"] = run_id
        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in http_run: {e}, traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON format, {extract_core_stack()}")

    except asyncio.CancelledError:
        logger.info(f"Request cancelled for run_id: {run_id}")
        result = {"status": "cancelled", "run_id": run_id, "message": "Execution was cancelled"}
        return result

    except Exception as e:
        # 使用错误分类器获取错误信息
        error_response = service.error_classifier.get_error_response(e, {"node_name": "http_run", "run_id": run_id})
        logger.error(
            f"Unexpected error in http_run: [{error_response['error_code']}] {error_response['error_message']}, "
            f"traceback: {traceback.format_exc()}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": error_response["error_code"],
                "error_message": error_response["error_message"],
                "stack_trace": extract_core_stack(),
            }
        )
    finally:
        cozeloop.flush()


HEADER_X_WORKFLOW_STREAM_MODE = "x-workflow-stream-mode"


def _register_task(run_id: str, task: asyncio.Task):
    service.running_tasks[run_id] = task


@app.post("/stream_run")
async def http_stream_run(request: Request):
    ctx = new_context(method="stream_run", headers=request.headers)
    # 优先使用上游指定的 run_id，保证 cancel 能精确匹配
    upstream_run_id = request.headers.get(HEADER_X_RUN_ID)
    if upstream_run_id:
        ctx.run_id = upstream_run_id
    workflow_stream_mode = request.headers.get(HEADER_X_WORKFLOW_STREAM_MODE, "").lower()
    workflow_debug = workflow_stream_mode == "debug"
    request_context.set(ctx)
    raw_body = await request.body()
    try:
        body_text = raw_body.decode("utf-8")
    except Exception as e:
        body_text = str(raw_body)
        raise HTTPException(status_code=400,
                            detail=f"Invalid JSON format: {body_text}, traceback: {extract_core_stack()}, error: {e}")
    run_id = ctx.run_id
    is_agent = graph_helper.is_agent_proj()
    logger.info(
        f"Received request for /stream_run: "
        f"run_id={run_id}, "
        f"is_agent_project={is_agent}, "
        f"query={dict(request.query_params)}, "
        f"body={body_text}"
    )
    try:
        payload = await request.json()
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in http_stream_run: {e}, traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON format:{extract_core_stack()}")

    if is_agent:
        stream_generator = agent_stream_handler(
            payload=payload,
            ctx=ctx,
            run_id=run_id,
            stream_sse_func=service.stream_sse,
            sse_event_func=service._sse_event,
            error_classifier=service.error_classifier,
            register_task_func=_register_task,
        )
    else:
        stream_generator = workflow_stream_handler(
            payload=payload,
            ctx=ctx,
            run_id=run_id,
            stream_sse_func=service.stream_sse,
            sse_event_func=service._sse_event,
            error_classifier=service.error_classifier,
            register_task_func=_register_task,
            run_opt=RunOpt(workflow_debug=workflow_debug),
        )

    response = StreamingResponse(stream_generator, media_type="text/event-stream")
    return response

@app.post("/cancel/{run_id}")
async def http_cancel(run_id: str, request: Request):
    """
    取消指定run_id的执行

    使用asyncio.Task.cancel()实现取消,这是Python标准的异步任务取消机制。
    LangGraph会在节点之间的await点检查CancelledError,实现优雅取消。
    """
    ctx = new_context(method="cancel", headers=request.headers)
    request_context.set(ctx)
    logger.info(f"Received cancel request for run_id: {run_id}")
    result = service.cancel_run(run_id, ctx)
    return result


@app.post(path="/node_run/{node_id}")
async def http_node_run(node_id: str, request: Request):
    raw_body = await request.body()
    try:
        body_text = raw_body.decode("utf-8")
    except UnicodeDecodeError:
        body_text = str(raw_body)
        raise HTTPException(status_code=400, detail=f"Invalid JSON format: {body_text}")
    ctx = new_context(method="node_run", headers=request.headers)
    request_context.set(ctx)
    logger.info(
        f"Received request for /node_run/{node_id}: "
        f"query={dict(request.query_params)}, "
        f"body={body_text}",
    )

    try:
        payload = await request.json()
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in http_node_run: {e}, traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON format:{extract_core_stack()}")
    try:
        return await service.run_node(node_id, payload, ctx)
    except KeyError:
        raise HTTPException(status_code=404,
                            detail=f"node_id '{node_id}' not found or input miss required fields, traceback: {extract_core_stack()}")
    except Exception as e:
        # 使用错误分类器获取错误信息
        error_response = service.error_classifier.get_error_response(e, {"node_name": node_id})
        logger.error(
            f"Unexpected error in http_node_run: [{error_response['error_code']}] {error_response['error_message']}, "
            f"traceback: {traceback.format_exc()}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": error_response["error_code"],
                "error_message": error_response["error_message"],
                "stack_trace": extract_core_stack(),
            }
        )
    finally:
        cozeloop.flush()


@app.post("/v1/chat/completions")
async def openai_chat_completions(request: Request):
    """OpenAI Chat Completions API 兼容接口"""
    ctx = new_context(method="openai_chat", headers=request.headers)
    request_context.set(ctx)

    logger.info(f"Received request for /v1/chat/completions: run_id={ctx.run_id}")

    try:
        payload = await request.json()
        return await openai_handler.handle(payload, ctx)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in openai_chat_completions: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    finally:
        cozeloop.flush()


@app.get("/health")
async def health_check():
    try:
        # 这里可以添加更多的健康检查逻辑
        return {
            "status": "ok",
            "message": "Service is running",
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get(path="/graph_parameter")
async def http_graph_inout_parameter(request: Request):
    return service.graph_inout_schema()

def parse_args():
    parser = argparse.ArgumentParser(description="Start FastAPI server")
    parser.add_argument("-m", type=str, default="http", help="Run mode, support http,flow,node")
    parser.add_argument("-n", type=str, default="", help="Node ID for single node run")
    parser.add_argument("-p", type=int, default=5000, help="HTTP server port")
    parser.add_argument("-i", type=str, default="", help="Input JSON string for flow/node mode")
    return parser.parse_args()


def parse_input(input_str: str) -> Dict[str, Any]:
    """Parse input string, support both JSON string and plain text"""
    if not input_str:
        return {"text": "你好"}

    # Try to parse as JSON first
    try:
        return json.loads(input_str)
    except json.JSONDecodeError:
        # If not valid JSON, treat as plain text
        return {"text": input_str}

def start_http_server(port):
    workers = 1
    reload = False
    if graph_helper.is_dev_env():
        reload = True

    logger.info(f"Start HTTP Server, Port: {port}, Workers: {workers}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=reload, workers=workers)

if __name__ == "__main__":
    args = parse_args()
    if args.m == "http":
        start_http_server(args.p)
    elif args.m == "flow":
        payload = parse_input(args.i)
        result = asyncio.run(service.run(payload))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.m == "node" and args.n:
        payload = parse_input(args.i)
        result = asyncio.run(service.run_node(args.n, payload))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.m == "agent":
        agent_ctx = new_context(method="agent")
        for chunk in service.stream(
                {
                    "type": "query",
                    "session_id": "1",
                    "message": "你好",
                    "content": {
                        "query": {
                            "prompt": [
                                {
                                    "type": "text",
                                    "content": {"text": "现在几点了？请调用工具获取当前时间"},
                                }
                            ]
                        }
                    },
                },
                run_config={"configurable": {"session_id": "1"}},
                ctx=agent_ctx,
        ):
            print(chunk)
