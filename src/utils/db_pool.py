"""
asyncpg 连接池单例。
所有 FastAPI 路由通过 await get_pool() 获取池子，再通过 acquire() 拿连接。
连接池由 asyncpg 内部管理，自动复用、自动归还、不阻塞事件循环。
"""
import os
import logging
from typing import Optional
import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


def _get_db_url() -> str:
    """从环境变量读取数据库连接字符串。"""
    # 优先用本地 .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    url = os.getenv("PGDATABASE_URL", "").strip()
    if url:
        return url

    # 兜底：从 coze_workload_identity 读
    try:
        from coze_workload_identity import Client
        client = Client()
        env_vars = client.get_project_env_vars()
        client.close()
        for env_var in env_vars:
            if env_var.key == "PGDATABASE_URL":
                return env_var.value
    except Exception as e:
        logger.error(f"无法从 coze_workload_identity 读取 PGDATABASE_URL: {e}")

    raise ValueError("PGDATABASE_URL 未设置")


async def get_pool() -> asyncpg.Pool:
    """
    获取全局连接池（懒加载单例）。

    第一次调用时建池子，min_size=5 max_size=20。
    后续调用直接返回缓存。
    """
    global _pool
    if _pool is not None and not _pool._closed:
        return _pool

    url = _get_db_url()
    # asyncpg 不识别 postgresql+psycopg2:// 这种 SQLAlchemy 风格，统一转成 postgresql://
    if "+" in url.split("://")[0]:
        url = "postgresql://" + url.split("://", 1)[1]

    _pool = await asyncpg.create_pool(
        url,
        min_size=5,
        max_size=20,
        max_inactive_connection_lifetime=300,  # 5分钟空闲就回收
        command_timeout=10,                    # 单条 SQL 最长 10 秒
        timeout=8,                             # acquire 连接最长等 8 秒
    )
    logger.info("asyncpg 连接池已创建：min=5, max=20")
    return _pool


async def close_pool() -> None:
    """应用关闭时优雅关连接池。"""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg 连接池已关闭")
