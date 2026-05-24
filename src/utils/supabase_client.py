import os
from typing import Optional

import httpx
from supabase import create_client, Client, ClientOptions

_env_loaded = False


def _load_env() -> None:
    global _env_loaded

    if _env_loaded or (os.getenv("COZE_SUPABASE_URL") and os.getenv("COZE_SUPABASE_ANON_KEY")):
        return

    try:
        from dotenv import load_dotenv
        load_dotenv()
        if os.getenv("COZE_SUPABASE_URL") and os.getenv("COZE_SUPABASE_ANON_KEY"):
            _env_loaded = True
            return
    except ImportError:
        pass

    try:
        from coze_workload_identity import Client as WorkloadClient

        client = WorkloadClient()
        env_vars = client.get_project_env_vars()
        client.close()

        for env_var in env_vars:
            if not os.getenv(env_var.key):
                os.environ[env_var.key] = env_var.value

        _env_loaded = True
    except Exception:
        pass


def get_supabase_credentials() -> tuple[str, str]:
    _load_env()

    url = os.getenv("COZE_SUPABASE_URL")
    anon_key = os.getenv("COZE_SUPABASE_ANON_KEY")

    if not url:
        raise ValueError("COZE_SUPABASE_URL is not set")
    if not anon_key:
        raise ValueError("COZE_SUPABASE_ANON_KEY is not set")

    return url, anon_key


def get_supabase_service_role_key() -> Optional[str]:
    _load_env()
    return os.getenv("COZE_SUPABASE_SERVICE_ROLE_KEY")


# ============================================================
# 单例客户端 — 全局只创建一次，所有请求复用同一个连接池
# ============================================================

_cached_service_client: Optional[Client] = None
_cached_user_client: Optional[Client] = None
_cached_user_token: Optional[str] = None


def get_supabase_client(token: Optional[str] = None) -> Client:
    """
    获取 Supabase 客户端（单例模式）。

    - 不传 token → 使用 service_role_key（后端管理操作）
    - 传 token   → 使用 anon_key + 用户 JWT（RLS 场景）

    每种模式只创建一次客户端实例，后续调用直接返回缓存。
    这样 httpx 连接池在整个进程生命周期内复用，不会泄漏连接。
    """
    global _cached_service_client, _cached_user_client, _cached_user_token

    url, anon_key = get_supabase_credentials()

    # ---------- service_role 模式（无 token） ----------
    if not token:
        if _cached_service_client is not None:
            return _cached_service_client

        service_role_key = get_supabase_service_role_key()
        key = service_role_key if service_role_key else anon_key

        options = ClientOptions(
            auto_refresh_token=False,
        )
        _cached_service_client = create_client(url, key, options=options)
        return _cached_service_client

    # ---------- 用户 JWT 模式（带 token） ----------
    # 如果 token 没变，复用已有客户端
    if _cached_user_client is not None and _cached_user_token == token:
        return _cached_user_client

    key = anon_key
    options = ClientOptions(
        headers={"Authorization": f"Bearer {token}"},
        auto_refresh_token=False,
    )
    _cached_user_client = create_client(url, key, options=options)
    _cached_user_token = token
    return _cached_user_client
