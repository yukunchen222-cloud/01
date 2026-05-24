import argparse
import asyncio
import json
import threading
import traceback
import logging
from typing import Any, Dict, Iterable, AsyncIterable, AsyncGenerator, Optional
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
app = FastAPI()

# 挂载静态文件目录
import os
_static_dir = os.path.join(os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects"), "assets")
if os.path.exists(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# OpenAI 兼容接口处理器
openai_handler = OpenAIChatHandler(service)

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
async def get_stores():
    """获取门店列表"""
    stores = [
        {"id": "store_001", "name": "中山路店", "address": "中山路128号"},
        {"id": "store_002", "name": "解放路店", "address": "解放路256号"},
        {"id": "store_003", "name": "人民广场店", "address": "人民广场东侧"},
        {"id": "store_004", "name": "万达广场店", "address": "万达广场3楼"},
        {"id": "store_005", "name": "银泰城店", "address": "银泰城2楼"},
    ]
    return {"success": True, "stores": stores}

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
    """语音报账API"""
    try:
        payload = await request.json()
        payload["input_type"] = "voice"
        
        ctx = new_context(method="api_voice")
        result = await service.run(payload, ctx)
        
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    """图片上传API - 上传图片到对象存储"""
    from coze_coding_dev_sdk import StorageClient
    
    try:
        ctx = new_context(method="api_upload")
        storage_client = StorageClient(ctx=ctx)
        
        # 读取文件内容
        content = await file.read()
        
        # 生成唯一文件名
        import time
        timestamp = int(time.time() * 1000)
        filename = f"upload_{timestamp}_{file.filename}"
        
        # 上传到对象存储
        result = storage_client.put_object(
            key=f"uploads/{filename}",
            data=content
        )
        
        # 获取访问URL
        url = result.get("url", "")
        
        return {"success": True, "url": url, "filename": filename}
    except Exception as e:
        logger.error(f"图片上传失败: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/image")
async def api_image(request: Request):
    """拍照录入API"""
    try:
        payload = await request.json()
        payload["input_type"] = "image"
        
        ctx = new_context(method="api_image")
        result = await service.run(payload, ctx)
        
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/records")
async def get_records(
    store_id: str = None,
    record_type: str = None,
    page: int = 1,
    page_size: int = 20
):
    """获取历史记录"""
    # 示例数据
    records = [
        {
            "id": "r001",
            "store_id": "store_001",
            "store_name": "中山路店",
            "type": "sale",
            "amount": 2580.00,
            "category": "连衣裙",
            "description": "红色连衣裙x2",
            "created_at": "2024-05-24 14:30:00"
        },
        {
            "id": "r002",
            "store_id": "store_001",
            "store_name": "中山路店",
            "type": "expense",
            "amount": 450.00,
            "category": "水电费",
            "description": "5月电费",
            "created_at": "2024-05-24 10:00:00"
        }
    ]
    return {
        "success": True,
        "records": records,
        "total": len(records),
        "page": page,
        "page_size": page_size
    }

# ==================== 登录鉴权API ====================

@app.post("/api/auth/login")
async def api_login(request: Request):
    """用户登录API"""
    from utils.auth import get_user_by_username, verify_password, create_token, update_user_login
    
    try:
        payload = await request.json()
        username = payload.get("username", "")
        password = payload.get("password", "")
        
        user = get_user_by_username(username)
        if not user:
            return {"success": False, "message": "用户不存在"}
        
        if not verify_password(password, user.password_hash):
            return {"success": False, "message": "密码错误"}
        
        if not user.is_active:
            return {"success": False, "message": "账号已被禁用"}
        
        # 生成Token
        token = create_token(user.user_id, user.role, user.org_id, user.store_ids)
        
        # 更新登录时间
        update_user_login(user.user_id)
        
        return {
            "success": True,
            "token": token,
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "name": user.name,
                "role": user.role,
                "org_id": user.org_id,
                "store_ids": user.store_ids
            }
        }
    except Exception as e:
        logger.error(f"登录失败: {e}")
        return {"success": False, "message": "登录失败，请稍后重试"}

@app.post("/api/auth/verify")
async def api_verify_token(request: Request):
    """验证Token有效性"""
    from utils.auth import decode_token, get_user_by_id
    
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return {"valid": False, "message": "缺少Token"}
    
    token = auth_header[7:]
    payload = decode_token(token)
    
    if not payload:
        return {"valid": False, "message": "Token无效或已过期"}
    
    user = get_user_by_id(payload.get("user_id"))
    if not user:
        return {"valid": False, "message": "用户不存在"}
    
    return {
        "valid": True,
        "user": {
            "user_id": user.user_id,
            "username": user.username,
            "name": user.name,
            "role": user.role,
            "org_id": user.org_id,
            "store_ids": user.store_ids
        }
    }

@app.post("/api/auth/logout")
async def api_logout():
    """用户登出"""
    return {"success": True, "message": "登出成功"}

# ==================== 商品管理API ====================

@app.get("/api/products")
async def get_products(request: Request):
    """获取商品列表"""
    from utils.auth import get_products_by_org, decode_token
    
    auth_header = request.headers.get("Authorization", "")
    org_id = "org_default"  # 默认组织
    
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload:
            org_id = payload.get("org_id", org_id)
    
    products = get_products_by_org(org_id)
    
    return {
        "success": True,
        "products": [p.model_dump() for p in products],
        "total": len(products)
    }

@app.post("/api/products")
async def create_product_api(request: Request):
    """创建商品"""
    from utils.auth import create_product, decode_token
    
    auth_header = request.headers.get("Authorization", "")
    org_id = "org_default"
    
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload:
            org_id = payload.get("org_id", org_id)
    
    try:
        data = await request.json()
        product = create_product(
            org_id=org_id,
            sku=data.get("sku", ""),
            name=data.get("name", ""),
            category=data.get("category", ""),
            cost_price=float(data.get("cost_price", 0)),
            sale_price=float(data.get("sale_price", 0)),
            stock=int(data.get("stock", 0))
        )
        return {"success": True, "product": product.model_dump()}
    except Exception as e:
        logger.error(f"创建商品失败: {e}")
        return {"success": False, "message": str(e)}

@app.put("/api/products/{product_id}")
async def update_product_api(product_id: str, request: Request):
    """更新商品"""
    from utils.auth import _load_json_file, _save_json_file, PRODUCTS_FILE
    
    try:
        data = await request.json()
        
        product_data = _load_json_file(PRODUCTS_FILE)
        products = product_data.get("products", [])
        
        for i, p in enumerate(products):
            if p.get("product_id") == product_id or p.get("sku") == product_id:
                # 更新字段
                products[i].update({
                    "sku": data.get("sku", products[i].get("sku")),
                    "name": data.get("name", products[i].get("name")),
                    "category": data.get("category", products[i].get("category")),
                    "cost_price": float(data.get("cost_price", 0)),
                    "sale_price": float(data.get("sale_price", 0)),
                    "stock": int(data.get("stock", 0))
                })
                product_data["products"] = products
                _save_json_file(PRODUCTS_FILE, product_data)
                return {"success": True, "product": products[i]}
        
        return {"success": False, "message": "商品不存在"}
    except Exception as e:
        logger.error(f"更新商品失败: {e}")
        return {"success": False, "message": str(e)}

@app.delete("/api/products/{product_id}")
async def delete_product_api(product_id: str):
    """删除商品"""
    from utils.auth import _load_json_file, _save_json_file, PRODUCTS_FILE
    
    try:
        product_data = _load_json_file(PRODUCTS_FILE)
        products = product_data.get("products", [])
        
        # 过滤掉要删除的商品
        new_products = [p for p in products if p.get("product_id") != product_id and p.get("sku") != product_id]
        
        if len(new_products) == len(products):
            return {"success": False, "message": "商品不存在"}
        
        product_data["products"] = new_products
        _save_json_file(PRODUCTS_FILE, product_data)
        
        return {"success": True, "message": "删除成功"}
    except Exception as e:
        logger.error(f"删除商品失败: {e}")
        return {"success": False, "message": str(e)}

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
    from utils.auth import get_stores_by_org, decode_token
    
    auth_header = request.headers.get("Authorization", "")
    org_id = "org_default"
    user_store_ids = None
    
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload:
            org_id = payload.get("org_id", org_id)
            user_store_ids = payload.get("store_ids")
    
    all_stores = get_stores_by_org(org_id)
    
    # 店长只能看到自己负责的门店
    if user_store_ids is not None and payload.get("role") == "manager":
        all_stores = [s for s in all_stores if s.store_id in user_store_ids]
    
    return {
        "success": True,
        "stores": [s.model_dump() for s in all_stores]
    }

# ==================== 语音/图片上传API ====================

@app.post("/api/voice/upload")
async def upload_voice(file: UploadFile = File(...), store_id: str = ""):
    """语音上传并识别"""
    from coze_coding_dev_sdk import AudioClient
    from utils.auth import _load_json_file, _save_json_file
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
            result = audio_client.asr(audio_file.read())
        
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
    from coze_coding_dev_sdk import StorageClient
    
    try:
        ctx = new_context(method="upload_image")
        
        # 上传图片到对象存储
        storage_client = StorageClient(ctx=ctx)
        content = await file.read()
        
        import time
        timestamp = int(time.time() * 1000)
        filename = f"upload_{timestamp}_{file.filename}"
        
        result = storage_client.put_object(
            key=f"images/{filename}",
            data=content
        )
        
        image_url = result.get("url", "")
        
        # 调用工作流进行OCR识别
        payload = {
            "input_type": "image",
            "image_url": image_url,
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
