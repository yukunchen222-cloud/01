"""Utilities for importing products from spreadsheet rows."""
import io
import re
from typing import Any

import pandas as pd


COLUMN_ALIASES = {
    "sku": "sku",
    "SKU": "sku",
    "款号": "sku",
    "货号": "sku",
    "编码": "sku",
    "商品编码": "sku",
    "条码": "sku",
    "商品条码": "sku",
    "code": "sku",
    "product_code": "sku",
    "商品名称": "name",
    "名称": "name",
    "品名": "name",
    "商品名": "name",
    "name": "name",
    "product_name": "name",
    "类目": "category",
    "分类": "category",
    "类别": "category",
    "品类": "category",
    "category": "category",
    "进价": "cost_price",
    "成本价": "cost_price",
    "成本": "cost_price",
    "采购价": "cost_price",
    "cost": "cost_price",
    "cost_price": "cost_price",
    "售价": "sale_price",
    "销售价": "sale_price",
    "零售价": "sale_price",
    "吊牌价": "sale_price",
    "单价": "sale_price",
    "price": "sale_price",
    "sale_price": "sale_price",
    "库存": "stock",
    "库存数量": "stock",
    "数量": "stock",
    "stock": "stock",
    "qty": "stock",
}


def read_product_spreadsheet(content: bytes, filename: str) -> pd.DataFrame:
    """Read an uploaded product spreadsheet into a DataFrame.
    
    自动检测表头位置，支持标题行在表头上方的Excel格式。
    """
    suffix = (filename or "").lower().rsplit(".", 1)[-1]
    buffer = io.BytesIO(content)

    if suffix == "csv":
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            buffer.seek(0)
            try:
                df = pd.read_csv(buffer, encoding=encoding)
                return _find_header_row_csv(df, buffer, encoding)
            except UnicodeDecodeError:
                continue
        buffer.seek(0)
        return pd.read_csv(buffer)

    if suffix == "xlsx":
        df = pd.read_excel(buffer, engine="openpyxl", header=None)
        return _find_header_row_excel(df, buffer, "openpyxl")
    if suffix == "xls":
        df = pd.read_excel(buffer, engine="xlrd", header=None)
        return _find_header_row_excel(df, buffer, "xlrd")

    raise ValueError("仅支持 .xlsx、.xls、.csv 文件")


def _find_header_row_excel(df: pd.DataFrame, buffer: io.BytesIO, engine: str) -> pd.DataFrame:
    """智能检测Excel表头位置，跳过标题行"""
    header_keywords = ["款号", "货号", "SKU", "sku", "商品名称", "品名", "名称", "name", 
                       "编码", "条码", "code", "商品编码", "商品条码"]
    
    for row_idx in range(min(10, len(df))):
        row = df.iloc[row_idx]
        row_values = [str(v).strip().lower() if v is not None else "" for v in row]
        matches = sum(1 for v in row_values for kw in header_keywords if kw.lower() in v)
        
        if matches >= 2:
            buffer.seek(0)
            return pd.read_excel(buffer, engine=engine, header=row_idx)
    
    return df


def _find_header_row_csv(df: pd.DataFrame, buffer: io.BytesIO, encoding: str) -> pd.DataFrame:
    """智能检测CSV表头位置，跳过标题行"""
    header_keywords = ["款号", "货号", "SKU", "sku", "商品名称", "品名", "名称", "name", 
                       "编码", "条码", "code", "商品编码", "商品条码"]
    
    for row_idx in range(min(10, len(df))):
        row = df.iloc[row_idx]
        row_values = [str(v).strip().lower() if v is not None else "" for v in row]
        matches = sum(1 for v in row_values for kw in header_keywords if kw.lower() in v)
        
        if matches >= 2:
            buffer.seek(0)
            return pd.read_csv(buffer, encoding=encoding, header=row_idx)
    
    return df


def normalize_product_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize common Chinese/English product headers to API field names."""
    normalized = df.copy()
    normalized.columns = [_normalize_header(col) for col in normalized.columns]
    return normalized


def build_product_from_row(row: Any, org_id: str) -> dict:
    """Build a product payload from a normalized pandas row."""
    sku = _cell_to_str(row.get("sku", ""))
    name = _cell_to_str(row.get("name", ""))
    if not sku or not name:
        raise ValueError("款号或名称为空")

    return {
        "org_id": org_id,
        "sku": sku,
        "name": name,
        "category": _cell_to_str(row.get("category", "")) or "其他",
        "cost_price": _cell_to_float(row.get("cost_price", 0)),
        "sale_price": _cell_to_float(row.get("sale_price", 0)),
        "stock": int(_cell_to_float(row.get("stock", 0))),
    }


def _normalize_header(value: Any) -> str:
    header = _cell_to_str(value)
    compact = re.sub(r"[\s_（）()\-]+", "", header).lower()

    for alias, field in COLUMN_ALIASES.items():
        if compact == re.sub(r"[\s_（）()\-]+", "", alias).lower():
            return field

    return header


def _cell_to_str(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _cell_to_float(value: Any) -> float:
    if value is None or pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return 0.0
    text = text.translate(str.maketrans("０１２３４５６７８９．，", "0123456789.,"))
    text = re.sub(r"[￥¥,\s]", "", text)
    if not text:
        return 0.0
    return float(text)
