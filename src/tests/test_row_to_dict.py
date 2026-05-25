"""防止 asyncpg Decimal/REAL 类型回归"""
from decimal import Decimal
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from storage.database.repository import _row_to_dict


class FakeRecord(dict):
    """模拟 asyncpg.Record，行为像 dict"""
    pass


def test_decimal_converts_to_float():
    row = FakeRecord(total_amount=Decimal("12907.50"), cost=Decimal("5860"))
    out = _row_to_dict(row)
    assert isinstance(out["total_amount"], float)
    assert out["total_amount"] == 12907.50
    assert isinstance(out["cost"], float)


def test_confidence_rounded():
    row = FakeRecord(confidence=0.800000011920929)
    out = _row_to_dict(row)
    assert out["confidence"] == 0.80


def test_datetime_to_iso():
    row = FakeRecord(created_at=datetime(2026, 5, 24, 14, 8, 6))
    out = _row_to_dict(row)
    assert out["created_at"] == "2026-05-24T14:08:06"


def test_none_passthrough():
    row = FakeRecord(reviewed_at=None, total_amount=None)
    out = _row_to_dict(row)
    assert out["reviewed_at"] is None
    assert out["total_amount"] is None


def test_jsonb_string_parsed():
    row = FakeRecord(items='[{"name":"红色连衣裙","qty":3}]')
    out = _row_to_dict(row)
    assert isinstance(out["items"], list)
    assert out["items"][0]["qty"] == 3
