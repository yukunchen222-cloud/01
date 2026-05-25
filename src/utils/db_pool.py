"""asyncpg connection pool singleton."""
import logging
import os
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def init_connection(conn: asyncpg.Connection) -> None:
    """Initialize each new database connection."""
    await conn.execute("SET TIME ZONE 'Asia/Shanghai'")
    try:
        await conn.execute("SET log_min_duration_statement = 500")
    except Exception as e:
        logger.debug(f"Unable to set slow-query logging threshold: {e}")


def _get_db_url() -> str:
    """Read the database URL from env or Coze workload identity."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    url = os.getenv("PGDATABASE_URL", "").strip()
    if url:
        return url

    try:
        from coze_workload_identity import Client

        client = Client()
        env_vars = client.get_project_env_vars()
        client.close()
        for env_var in env_vars:
            if env_var.key == "PGDATABASE_URL":
                return env_var.value
    except Exception as e:
        logger.error(f"Unable to read PGDATABASE_URL from coze_workload_identity: {e}")

    raise ValueError("PGDATABASE_URL is not set")


async def get_pool() -> asyncpg.Pool:
    """Return the global asyncpg pool, creating it on first use."""
    global _pool
    if _pool is not None and not _pool._closed:
        return _pool

    url = _get_db_url()
    if "+" in url.split("://")[0]:
        url = "postgresql://" + url.split("://", 1)[1]

    _pool = await asyncpg.create_pool(
        url,
        init=init_connection,
        min_size=10,
        max_size=50,
        max_inactive_connection_lifetime=60,
        command_timeout=8,
        timeout=3,
    )
    logger.info("asyncpg pool created: min=10, max=50, timeout=3s")
    return _pool


async def close_pool() -> None:
    """Close the global asyncpg pool on app shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")
