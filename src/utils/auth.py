"""
用户认证模块 - JWT Token 验证和用户管理
数据库操作已迁移到 asyncpg (repository.py)
"""
import os
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import jwt

logger = logging.getLogger(__name__)

# JWT配置
JWT_SECRET = os.getenv("JWT_SECRET", "coze_clothing_ai_secret_key_2024")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24


class UserRole(str):
    """用户角色"""
    OWNER = "owner"       # 老板
    MANAGER = "manager"   # 店长
    ACCOUNTANT = "accountant"  # 会计


class User(BaseModel):
    """用户模型"""
    user_id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    password_hash: str = Field(..., description="密码哈希")
    role: str = Field(..., description="角色：owner/manager/accountant")
    org_id: str = Field(..., description="组织ID")
    store_ids: List[str] = Field(default=[], description="可访问的门店ID列表")
    name: str = Field(default="", description="姓名")
    phone: str = Field(default="", description="手机号")
    avatar: str = Field(default="", description="头像URL")
    is_active: bool = Field(default=True, description="是否激活")
    created_at: str = Field(default="", description="创建时间")
    last_login: str = Field(default="", description="最后登录时间")


class Organization(BaseModel):
    """组织/企业模型"""
    org_id: str = Field(..., description="组织ID")
    name: str = Field(..., description="组织名称")
    plan: str = Field(default="basic", description="套餐：basic/pro/enterprise")
    max_stores: int = Field(default=5, description="最大门店数")
    max_users: int = Field(default=10, description="最大用户数")
    settings: Dict[str, Any] = Field(default={}, description="组织设置")
    created_at: str = Field(default="", description="创建时间")


class Store(BaseModel):
    """门店模型"""
    store_id: str = Field(..., description="门店ID")
    org_id: str = Field(..., description="组织ID")
    name: str = Field(..., description="门店名称")
    address: str = Field(default="", description="地址")
    manager_id: Optional[str] = Field(default=None, description="店长ID")
    phone: str = Field(default="", description="联系电话")
    status: str = Field(default="active", description="状态")
    created_at: str = Field(default="", description="创建时间")


class Product(BaseModel):
    """商品模型"""
    product_id: str = Field(..., description="商品ID")
    org_id: str = Field(..., description="组织ID")
    sku: str = Field(..., description="款号")
    name: str = Field(..., description="商品名称")
    category: str = Field(default="", description="类目")
    cost_price: float = Field(default=0.0, description="进价")
    sale_price: float = Field(default=0.0, description="售价")
    stock: int = Field(default=0, description="库存")
    status: str = Field(default="active", description="状态")
    last_sale_date: Optional[str] = Field(default=None, description="最后销售日期")
    created_at: str = Field(default="", description="创建时间")


def hash_password(password: str) -> str:
    """密码哈希"""
    return hashlib.sha256(f"{password}{JWT_SECRET}".encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    return hash_password(password) == password_hash


def create_token(user_id: str, role: str, org_id: str, store_ids: List[str]) -> str:
    """创建JWT Token"""
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "role": role,
        "org_id": org_id,
        "store_ids": store_ids,
        "exp": expire.timestamp()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """解码JWT Token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
