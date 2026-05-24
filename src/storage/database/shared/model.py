from coze_coding_dev_sdk.database import Base

from typing import Optional
import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Double, Integer, Numeric, PrimaryKeyConstraint, Table, Text, text, String, ForeignKey, Index, JSON, func
from sqlalchemy.dialects.postgresql import OID
from sqlalchemy.orm import Mapped, mapped_column

class HealthCheck(Base):
    __tablename__ = 'health_check'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='health_check_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))


t_pg_stat_statements = Table(
    'pg_stat_statements', Base.metadata,
    Column('userid', OID),
    Column('dbid', OID),
    Column('toplevel', Boolean),
    Column('queryid', BigInteger),
    Column('query', Text),
    Column('plans', BigInteger),
    Column('total_plan_time', Double(53)),
    Column('min_plan_time', Double(53)),
    Column('max_plan_time', Double(53)),
    Column('mean_plan_time', Double(53)),
    Column('stddev_plan_time', Double(53)),
    Column('calls', BigInteger),
    Column('total_exec_time', Double(53)),
    Column('min_exec_time', Double(53)),
    Column('max_exec_time', Double(53)),
    Column('mean_exec_time', Double(53)),
    Column('stddev_exec_time', Double(53)),
    Column('rows', BigInteger),
    Column('shared_blks_hit', BigInteger),
    Column('shared_blks_read', BigInteger),
    Column('shared_blks_dirtied', BigInteger),
    Column('shared_blks_written', BigInteger),
    Column('local_blks_hit', BigInteger),
    Column('local_blks_read', BigInteger),
    Column('local_blks_dirtied', BigInteger),
    Column('local_blks_written', BigInteger),
    Column('temp_blks_read', BigInteger),
    Column('temp_blks_written', BigInteger),
    Column('shared_blk_read_time', Double(53)),
    Column('shared_blk_write_time', Double(53)),
    Column('local_blk_read_time', Double(53)),
    Column('local_blk_write_time', Double(53)),
)

# ============================================================
# 服装连锁AI记账助手 - 业务表定义
# ============================================================

class Organization(Base):
    """组织/租户表"""
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="组织唯一标识")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="组织名称")
    plan: Mapped[str] = mapped_column(String(32), nullable=False, server_default="free", comment="套餐: free/pro/enterprise")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", comment="是否启用")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    __table_args__ = (
        Index("ix_organizations_org_id", "org_id"),
    )


class Store(Base):
    """门店表"""
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="门店唯一标识")
    org_id: Mapped[str] = mapped_column(String(64), ForeignKey("organizations.org_id"), nullable=False, comment="所属组织")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="门店名称")
    address: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="门店地址")
    manager_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="店长姓名")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", comment="是否营业")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_stores_org_id", "org_id"),
        Index("ix_stores_store_id", "store_id"),
    )


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="用户唯一标识")
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="登录用户名")
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False, comment="密码哈希")
    role: Mapped[str] = mapped_column(String(32), nullable=False, comment="角色: owner/manager/accountant")
    org_id: Mapped[str] = mapped_column(String(64), ForeignKey("organizations.org_id"), nullable=False, comment="所属组织")
    store_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, comment="可管理的门店ID列表")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="姓名")
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="手机号")
    avatar: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="头像URL")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", comment="是否启用")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后登录时间")

    __table_args__ = (
        Index("ix_users_username", "username"),
        Index("ix_users_org_id", "org_id"),
    )


class Product(Base):
    """商品库表"""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="商品唯一标识")
    org_id: Mapped[str] = mapped_column(String(64), ForeignKey("organizations.org_id"), nullable=False, comment="所属组织")
    sku: Mapped[str] = mapped_column(String(64), nullable=False, comment="SKU编码")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="商品名称")
    category: Mapped[str] = mapped_column(String(64), nullable=False, comment="品类: 外套/连衣裙/衬衫/裤装")
    cost_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, server_default="0", comment="成本价")
    sale_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, server_default="0", comment="售价")
    stock: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", comment="库存数量")
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="active", comment="状态: active/inactive/discontinued")
    last_sale_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后销售日期")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    __table_args__ = (
        Index("ix_products_org_id", "org_id"),
        Index("ix_products_sku", "sku"),
        Index("ix_products_category", "category"),
        Index("ix_products_product_id", "product_id"),
    )


class Record(Base):
    """记账记录表（ai_raw_records）"""
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="记录唯一标识")
    org_id: Mapped[str] = mapped_column(String(64), ForeignKey("organizations.org_id"), nullable=False, comment="所属组织")
    store_id: Mapped[str] = mapped_column(String(64), ForeignKey("stores.store_id"), nullable=False, comment="所属门店")
    store_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="门店名称(冗余)")
    type: Mapped[str] = mapped_column(String(32), nullable=False, comment="类型: revenue/purchase/return/expense")
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="品类")
    items: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, comment="商品明细列表")
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, server_default="0", comment="总金额")
    payment_method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="支付方式")
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, server_default="0", comment="AI识别置信度")
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending", comment="状态: pending/approved/rejected")
    input_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="输入方式: voice/image/text")
    original_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="原始识别文本")
    operator: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="操作人")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="备注")
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="审核人")
    reviewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="审核时间")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    __table_args__ = (
        Index("ix_records_org_id", "org_id"),
        Index("ix_records_store_id", "store_id"),
        Index("ix_records_type", "type"),
        Index("ix_records_status", "status"),
        Index("ix_records_created_at", "created_at"),
        Index("ix_records_record_id", "record_id"),
        Index("ix_records_org_status", "org_id", "status"),
        Index("ix_records_org_date", "org_id", "created_at"),
    )


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[str] = mapped_column(String(64), ForeignKey("organizations.org_id"), nullable=False, comment="所属组织")
    user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="操作用户ID")
    action: Mapped[str] = mapped_column(String(64), nullable=False, comment="操作类型: approve/reject/create/update/delete")
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="目标类型: record/product/user")
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="目标ID")
    detail: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="操作详情")
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True, comment="IP地址")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_org_id", "org_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_target", "target_type", "target_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )
