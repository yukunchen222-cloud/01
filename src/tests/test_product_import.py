import io
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.product_import import (
    build_product_from_row,
    normalize_product_columns,
    read_product_spreadsheet,
)


def test_normalizes_common_headers_and_builds_product():
    df = pd.DataFrame(
        [
            {
                "商品编码": "SKU001",
                "商品名称": "黑色西装外套",
                "品类": "外套",
                "成本价": "¥1,200.50",
                "零售价": "1599",
                "库存数量": "12",
            }
        ]
    )

    normalized = normalize_product_columns(df)
    product = build_product_from_row(normalized.iloc[0], "org_1")

    assert product == {
        "org_id": "org_1",
        "sku": "SKU001",
        "name": "黑色西装外套",
        "category": "外套",
        "cost_price": 1200.50,
        "sale_price": 1599.0,
        "stock": 12,
    }


def test_full_width_numbers_are_parsed():
    df = pd.DataFrame(
        [{"sku": "A001", "name": "测试商品", "cost_price": "１２３．５", "stock": "３"}]
    )

    product = build_product_from_row(normalize_product_columns(df).iloc[0], "org_default")

    assert product["cost_price"] == 123.5
    assert product["stock"] == 3


def test_gb18030_csv_can_be_read():
    csv_bytes = "款号,商品名称,售价\nSKU002,红色连衣裙,299\n".encode("gb18030")

    df = read_product_spreadsheet(csv_bytes, "products.csv")
    product = build_product_from_row(normalize_product_columns(df).iloc[0], "org_default")

    assert product["sku"] == "SKU002"
    assert product["name"] == "红色连衣裙"
    assert product["sale_price"] == 299.0


def test_xlsx_can_be_read_with_uppercase_extension():
    stream = io.BytesIO()
    pd.DataFrame([{"SKU": "SKU003", "name": "白色衬衫"}]).to_excel(stream, index=False)

    df = read_product_spreadsheet(stream.getvalue(), "PRODUCTS.XLSX")
    product = build_product_from_row(normalize_product_columns(df).iloc[0], "org_default")

    assert product["sku"] == "SKU003"
    assert product["name"] == "白色衬衫"
