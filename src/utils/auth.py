"""
用户认证模块 - JWT Token 验证和用户管理
优先使用Supabase数据库，JSON文件作为fallback
"""
import os
import json
import hashlib
import secrets
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

# 用户数据文件路径 - fallback使用
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_workspace = os.getenv("COZE_WORKSPACE_PATH", _project_root)
USERS_FILE = os.path.join(_workspace, "data/users.json")
ORGANIZATIONS_FILE = os.path.join(_workspace, "data/organizations.json")
STORES_FILE = os.path.join(_workspace, "data/stores.json")
PRODUCTS_FILE = os.path.join(_workspace, "data/products.json")
RECORDS_FILE = os.path.join(_workspace, "data/records.json")

# 数据库模式开关
USE_DB = os.getenv("USE_DATABASE", "true").lower() == "true"


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
    payload = {
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


# ==================== JSON文件操作（fallback） ====================

def _load_json_file(file_path: str) -> Dict:
    """加载JSON文件"""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_json_file(file_path: str, data: Dict):
    """保存JSON文件"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==================== 数据库操作（优先） ====================

def _get_db():
    """获取数据库操作模块"""
    from utils.db import (
        get_user_by_username as db_get_user,
        get_user_by_id as db_get_user_by_id,
        get_stores as db_get_stores,
        get_products as db_get_products,
        create_product as db_create_product,
        create_user as db_create_user,
        create_record as db_create_record,
        get_records as db_get_records,
        update_record as db_update_record,
        approve_record as db_approve_record,
        reject_record as db_reject_record,
        aggregate_dashboard as db_aggregate_dashboard,
    )
    return {
        "get_user_by_username": db_get_user,
        "get_user_by_id": db_get_user_by_id,
        "get_stores": db_get_stores,
        "get_products": db_get_products,
        "create_product": db_create_product,
        "create_user": db_create_user,
        "create_record": db_create_record,
        "get_records": db_get_records,
        "update_record": db_update_record,
        "approve_record": db_approve_record,
        "reject_record": db_reject_record,
        "aggregate_dashboard": db_aggregate_dashboard,
    }


# ==================== 统一接口（优先数据库，fallback JSON） ====================

def get_user_by_username(username: str) -> Optional[User]:
    """根据用户名获取用户"""
    if USE_DB:
        try:
            db = _get_db()
            user_data = db["get_user_by_username"](username)
            if user_data:
                # 数据库字段名映射
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
        except Exception as e:
            logger.warning(f"数据库查询用户失败，fallback到JSON: {e}")

    # Fallback: JSON文件
    data = _load_json_file(USERS_FILE)
    users = data.get("users", [])
    for user_data in users:
        if user_data.get("username") == username:
            return User(**user_data)
    return None


def get_user_by_id(user_id: str) -> Optional[User]:
    """根据ID获取用户"""
    if USE_DB:
        try:
            db = _get_db()
            user_data = db["get_user_by_id"](user_id)
            if user_data:
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
        except Exception as e:
            logger.warning(f"数据库查询用户失败，fallback到JSON: {e}")

    # Fallback: JSON文件
    data = _load_json_file(USERS_FILE)
    users = data.get("users", [])
    for user_data in users:
        if user_data.get("user_id") == user_id:
            return User(**user_data)
    return None


def create_user(username: str, password: str, role: str, org_id: str,
                name: str = "", phone: str = "", store_ids: List[str] = None) -> User:
    """创建用户"""
    user_id = f"user_{secrets.token_hex(8)}"
    user = User(
        user_id=user_id,
        username=username,
        password_hash=hash_password(password),
        role=role,
        org_id=org_id,
        store_ids=store_ids or [],
        name=name,
        phone=phone,
        created_at=datetime.now().isoformat()
    )

    if USE_DB:
        try:
            db = _get_db()
            db["create_user"]({
                "id": user_id,
                "username": username,
                "password_hash": hash_password(password),
                "role": role,
                "org_id": org_id,
                "store_ids": store_ids or [],
                "name": name,
                "phone": phone,
                "is_active": True,
                "created_at": datetime.now().isoformat()
            })
            return user
        except Exception as e:
            logger.warning(f"数据库创建用户失败，fallback到JSON: {e}")

    # Fallback: JSON文件
    data = _load_json_file(USERS_FILE)
    if "users" not in data:
        data["users"] = []
    data["users"].append(user.model_dump())
    _save_json_file(USERS_FILE, data)
    return user


def update_user_login(user_id: str):
    """更新用户登录时间"""
    # 简化：数据库和JSON都尝试更新
    now = datetime.now().isoformat()

    if USE_DB:
        try:
            from utils.supabase_client import get_supabase_client
            client = get_supabase_client()
            client.table("users").update({"last_login": now}).eq("id", user_id).execute()
            return
        except Exception as e:
            logger.warning(f"数据库更新登录时间失败: {e}")

    # Fallback: JSON文件
    data = _load_json_file(USERS_FILE)
    users = data.get("users", [])
    for user in users:
        if user.get("user_id") == user_id:
            user["last_login"] = now
            break
    _save_json_file(USERS_FILE, data)


def get_stores_by_org(org_id: str) -> List[Store]:
    """获取组织的门店列表"""
    if USE_DB:
        try:
            db = _get_db()
            stores_data = db["get_stores"](org_id=org_id)
            return [Store(
                store_id=str(s.get("id", "")),
                org_id=str(s.get("org_id", "")),
                name=s.get("name", ""),
                address=s.get("address", ""),
                manager_id=s.get("manager_id"),
                phone=s.get("phone", ""),
                status=s.get("status", "active"),
                created_at=str(s.get("created_at", ""))
            ) for s in stores_data]
        except Exception as e:
            logger.warning(f"数据库查询门店失败，fallback到JSON: {e}")

    # Fallback: JSON文件
    data = _load_json_file(STORES_FILE)
    stores = data.get("stores", [])
    return [Store(**s) for s in stores if s.get("org_id") == org_id]


def get_products_by_org(org_id: str) -> List[Product]:
    """获取组织的商品列表"""
    if USE_DB:
        try:
            db = _get_db()
            products_data = db["get_products"](org_id=org_id)
            return [Product(
                product_id=str(p.get("id", "")),
                org_id=str(p.get("org_id", "")),
                sku=p.get("sku", ""),
                name=p.get("name", ""),
                category=p.get("category", ""),
                cost_price=float(p.get("cost_price", 0)),
                sale_price=float(p.get("sale_price", 0)),
                stock=int(p.get("stock", 0)),
                status=p.get("status", "active"),
                last_sale_date=p.get("last_sale_date"),
                created_at=str(p.get("created_at", ""))
            ) for p in products_data]
        except Exception as e:
            logger.warning(f"数据库查询商品失败，fallback到JSON: {e}")

    # Fallback: JSON文件
    data = _load_json_file(PRODUCTS_FILE)
    products = data.get("products", [])
    return [Product(**p) for p in products if p.get("org_id") == org_id]


def create_product(org_id: str, sku: str, name: str, category: str = "",
                   cost_price: float = 0.0, sale_price: float = 0.0, stock: int = 0) -> Product:
    """创建商品"""
    product_id = f"prod_{secrets.token_hex(8)}"
    product = Product(
        product_id=product_id,
        org_id=org_id,
        sku=sku,
        name=name,
        category=category,
        cost_price=cost_price,
        sale_price=sale_price,
        stock=stock,
        created_at=datetime.now().isoformat()
    )

    if USE_DB:
        try:
            db = _get_db()
            db["create_product"]({
                "id": product_id,
                "org_id": org_id,
                "sku": sku,
                "name": name,
                "category": category,
                "cost_price": cost_price,
                "sale_price": sale_price,
                "stock": stock,
                "status": "active",
                "created_at": datetime.now().isoformat()
            })
            return product
        except Exception as e:
            logger.warning(f"数据库创建商品失败，fallback到JSON: {e}")

    # Fallback: JSON文件
    data = _load_json_file(PRODUCTS_FILE)
    if "products" not in data:
        data["products"] = []
    data["products"].append(product.model_dump())
    _save_json_file(PRODUCTS_FILE, data)
    return product


def init_default_data():
    """初始化默认数据 - 优先写入数据库"""
    now = datetime.now().isoformat()

    if USE_DB:
        try:
            from utils.supabase_client import get_supabase_client
            client = get_supabase_client()

            # 检查是否已有数据
            existing = client.table("organizations").select("id").limit(1).execute()
            if existing.data:
                logger.info("数据库已有数据，跳过初始化")
                return

            # 插入默认组织
            client.table("organizations").insert({
                "id": "org_default", "name": "示例服装连锁",
                "plan": "pro", "max_stores": 10, "max_users": 20,
                "settings": json.dumps({"fixed_expenses": {"rent": 15000, "utilities": 2000, "salary": 50000, "other": 3000}}),
                "created_at": now
            }).execute()

            # 插入默认门店
            stores_data = [
                {"id": "store_001", "org_id": "org_default", "name": "中山路店", "address": "中山路128号", "status": "active", "created_at": now},
                {"id": "store_002", "org_id": "org_default", "name": "人民广场店", "address": "人民广场地铁站B口", "status": "active", "created_at": now},
                {"id": "store_003", "org_id": "org_default", "name": "南京路店", "address": "南京路步行街88号", "status": "active", "created_at": now},
                {"id": "store_004", "org_id": "org_default", "name": "淮海路店", "address": "淮海中路666号", "status": "active", "created_at": now},
                {"id": "store_005", "org_id": "org_default", "name": "徐家汇店", "address": "徐家汇港汇广场", "status": "active", "created_at": now},
            ]
            client.table("stores").insert(stores_data).execute()

            # 插入默认用户
            users_data = [
                {"id": "user_boss", "username": "boss", "password_hash": hash_password("123456"), "role": "owner", "org_id": "org_default", "store_ids": [], "name": "张总", "phone": "13800138000", "is_active": True, "created_at": now},
                {"id": "user_mgr1", "username": "manager1", "password_hash": hash_password("123456"), "role": "manager", "org_id": "org_default", "store_ids": ["store_001"], "name": "李店长", "phone": "13800138001", "is_active": True, "created_at": now},
                {"id": "user_mgr2", "username": "manager2", "password_hash": hash_password("123456"), "role": "manager", "org_id": "org_default", "store_ids": ["store_002"], "name": "王店长", "phone": "13800138002", "is_active": True, "created_at": now},
                {"id": "user_acct", "username": "accountant", "password_hash": hash_password("123456"), "role": "accountant", "org_id": "org_default", "store_ids": [], "name": "赵会计", "phone": "13800138003", "is_active": True, "created_at": now},
            ]
            client.table("users").insert(users_data).execute()

            # 插入默认商品
            products_data = [
                {"id": "prod_001", "org_id": "org_default", "sku": "SKU001", "name": "黑色西装外套", "category": "外套", "cost_price": 150, "sale_price": 359, "stock": 50, "status": "active", "created_at": now},
                {"id": "prod_002", "org_id": "org_default", "sku": "SKU002", "name": "红色连衣裙", "category": "连衣裙", "cost_price": 120, "sale_price": 299, "stock": 35, "status": "active", "created_at": now},
                {"id": "prod_003", "org_id": "org_default", "sku": "SKU003", "name": "白色衬衫", "category": "衬衫", "cost_price": 60, "sale_price": 159, "stock": 80, "status": "active", "created_at": now},
                {"id": "prod_004", "org_id": "org_default", "sku": "SKU004", "name": "蓝色牛仔裤", "category": "裤装", "cost_price": 80, "sale_price": 199, "stock": 60, "status": "active", "created_at": now},
                {"id": "prod_005", "org_id": "org_default", "sku": "SKU005", "name": "针织开衫", "category": "毛衣", "cost_price": 90, "sale_price": 229, "stock": 45, "status": "active", "created_at": now},
                {"id": "prod_006", "org_id": "org_default", "sku": "SKU006", "name": "半身裙", "category": "裙装", "cost_price": 70, "sale_price": 179, "stock": 40, "status": "active", "created_at": now},
                {"id": "prod_007", "org_id": "org_default", "sku": "SKU007", "name": "风衣外套", "category": "外套", "cost_price": 200, "sale_price": 499, "stock": 25, "status": "active", "created_at": now},
                {"id": "prod_008", "org_id": "org_default", "sku": "SKU008", "name": "休闲T恤", "category": "T恤", "cost_price": 40, "sale_price": 99, "stock": 100, "status": "active", "created_at": now},
            ]
            client.table("products").insert(products_data).execute()

            logger.info("✅ 默认数据已写入数据库")
            return
        except Exception as e:
            logger.warning(f"数据库初始化失败，fallback到JSON: {e}")

    # Fallback: JSON文件初始化
    org_data = _load_json_file(ORGANIZATIONS_FILE)
    if not org_data.get("organizations"):
        org_data["organizations"] = [{
            "org_id": "org_default", "name": "示例服装连锁",
            "plan": "pro", "max_stores": 10, "max_users": 20,
            "settings": {"fixed_expenses": {"rent": 15000, "utilities": 2000, "salary": 50000, "other": 3000}},
            "created_at": now
        }]
        _save_json_file(ORGANIZATIONS_FILE, org_data)

    store_data = _load_json_file(STORES_FILE)
    if not store_data.get("stores"):
        store_data["stores"] = [
            {"store_id": "store_001", "org_id": "org_default", "name": "中山路店", "address": "中山路128号", "status": "active"},
            {"store_id": "store_002", "org_id": "org_default", "name": "人民广场店", "address": "人民广场地铁站B口", "status": "active"},
            {"store_id": "store_003", "org_id": "org_default", "name": "南京路店", "address": "南京路步行街88号", "status": "active"},
            {"store_id": "store_004", "org_id": "org_default", "name": "淮海路店", "address": "淮海中路666号", "status": "active"},
            {"store_id": "store_005", "org_id": "org_default", "name": "徐家汇店", "address": "徐家汇港汇广场", "status": "active"},
        ]
        _save_json_file(STORES_FILE, store_data)

    user_data = _load_json_file(USERS_FILE)
    if not user_data.get("users"):
        default_users = [
            {"username": "boss", "password": "123456", "role": "owner", "name": "张总", "phone": "13800138000"},
            {"username": "manager1", "password": "123456", "role": "manager", "name": "李店长", "phone": "13800138001", "store_ids": ["store_001"]},
            {"username": "manager2", "password": "123456", "role": "manager", "name": "王店长", "phone": "13800138002", "store_ids": ["store_002"]},
            {"username": "accountant", "password": "123456", "role": "accountant", "name": "赵会计", "phone": "13800138003"},
        ]
        user_data["users"] = []
        for u in default_users:
            user = User(
                user_id=f"user_{secrets.token_hex(8)}", username=u["username"],
                password_hash=hash_password(u["password"]), role=u["role"],
                org_id="org_default", store_ids=u.get("store_ids", []),
                name=u["name"], phone=u["phone"], created_at=now
            )
            user_data["users"].append(user.model_dump())
        _save_json_file(USERS_FILE, user_data)

    product_data = _load_json_file(PRODUCTS_FILE)
    if not product_data.get("products"):
        default_products = [
            {"sku": "SKU001", "name": "黑色西装外套", "category": "外套", "cost_price": 150, "sale_price": 359, "stock": 50},
            {"sku": "SKU002", "name": "红色连衣裙", "category": "连衣裙", "cost_price": 120, "sale_price": 299, "stock": 35},
            {"sku": "SKU003", "name": "白色衬衫", "category": "衬衫", "cost_price": 60, "sale_price": 159, "stock": 80},
            {"sku": "SKU004", "name": "蓝色牛仔裤", "category": "裤装", "cost_price": 80, "sale_price": 199, "stock": 60},
            {"sku": "SKU005", "name": "针织开衫", "category": "毛衣", "cost_price": 90, "sale_price": 229, "stock": 45},
            {"sku": "SKU006", "name": "半身裙", "category": "裙装", "cost_price": 70, "sale_price": 179, "stock": 40},
            {"sku": "SKU007", "name": "风衣外套", "category": "外套", "cost_price": 200, "sale_price": 499, "stock": 25},
            {"sku": "SKU008", "name": "休闲T恤", "category": "T恤", "cost_price": 40, "sale_price": 99, "stock": 100},
        ]
        product_data["products"] = []
        for p in default_products:
            product = Product(
                product_id=f"prod_{secrets.token_hex(8)}", org_id="org_default",
                sku=p["sku"], name=p["name"], category=p["category"],
                cost_price=p["cost_price"], sale_price=p["sale_price"],
                stock=p["stock"], created_at=now
            )
            product_data["products"].append(product.model_dump())
        _save_json_file(PRODUCTS_FILE, product_data)


# 初始化默认数据
init_default_data()
