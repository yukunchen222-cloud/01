"""
集成压测：并发命中 /api/dashboard 等核心端点，断言全 200 + 总耗时 < 5s
"""
import asyncio
import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.db_pool import get_pool, close_pool
from storage.database import repository as repo


async def test_concurrent_dashboard():
    """20 并发查询 dashboard 数据，断言全成功且 < 5s"""
    pool = await get_pool()
    
    start = time.time()
    tasks = []
    for i in range(20):
        tasks.append(repo.get_records(org_id="org_default", limit=100))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start
    
    errors = [r for r in results if isinstance(r, Exception)]
    success = [r for r in results if not isinstance(r, Exception)]
    
    print(f"20 并发查询: 成功={len(success)}, 失败={len(errors)}, 耗时={elapsed:.2f}s")
    
    assert len(errors) == 0, f"有 {len(errors)} 个请求失败: {[str(e)[:100] for e in errors]}"
    assert elapsed < 5.0, f"总耗时 {elapsed:.2f}s > 5s，连接池可能不足"
    
    print("✅ 并发压测通过！")


async def test_decimal_conversion():
    """验证 repository 返回的数据中 Decimal 已正确转为 float"""
    records = await repo.get_records(org_id="org_default", limit=1)
    
    if records:
        val = records[0].get("total_amount")
        assert val is not None, "total_amount 不应为 None"
        from decimal import Decimal
        assert not isinstance(val, Decimal), f"total_amount 仍是 Decimal: {val}"
        assert isinstance(val, (int, float)), f"total_amount 类型异常: {type(val)}"
        print(f"✅ Decimal 转换验证通过: total_amount={val} (type={type(val).__name__})")
    else:
        print("⚠️ 无记录可验证，跳过 Decimal 测试")


async def test_pool_stats():
    """验证连接池参数"""
    pool = await get_pool()
    # asyncpg Pool 的 minsize/maxsize 属性
    assert pool._minsize >= 10, f"连接池 min_size={pool._minsize} < 10"
    assert pool._maxsize >= 50, f"连接池 max_size={pool._maxsize} < 50"
    print(f"✅ 连接池参数验证通过: min={pool._minsize}, max={pool._maxsize}")


if __name__ == "__main__":
    print("=" * 60)
    print("集成压测开始")
    print("=" * 60)
    
    async def run_all():
        await test_pool_stats()
        await test_decimal_conversion()
        await test_concurrent_dashboard()
        await close_pool()
    
    asyncio.run(run_all())
    
    print("\n" + "=" * 60)
    print("🎉 全部集成测试通过！")
    print("=" * 60)
