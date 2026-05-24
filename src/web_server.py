"""
服装连锁AI记账助手 - Web服务器
提供前端页面托管和API接口
"""
import os
import json
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="服装连锁AI记账助手",
    description="智能记账助手Web接口",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件目录
ASSETS_DIR = os.path.join(os.getenv("COZE_WORKSPACE_PATH", "."), "assets")


# ==================== 请求模型 ====================
class QueryRequest(BaseModel):
    """查询请求"""
    input_type: str = "query"
    query_type: str = "month"  # day, week, month, year
    store_id: Optional[str] = None


class VoiceRequest(BaseModel):
    """语音报账请求"""
    input_type: str = "voice"
    audio_url: Optional[str] = None
    store_id: Optional[str] = None
    store_name: Optional[str] = None


class ImageRequest(BaseModel):
    """拍照录入请求"""
    input_type: str = "image"
    image_url: Optional[str] = None
    store_id: Optional[str] = None
    store_name: Optional[str] = None


# ==================== 模拟数据 ====================
def get_dashboard_data(period: str, store_id: Optional[str] = None) -> Dict[str, Any]:
    """获取看板数据"""
    # 模拟不同门店的数据
    store_multipliers = {
        "store_001": 1.0,
        "store_002": 0.85,
        "store_003": 0.72,
    }
    
    multiplier = store_multipliers.get(store_id, 1.0) if store_id else 1.0
    
    # 根据时间周期调整数据规模
    period_multipliers = {
        "day": 0.03,
        "week": 0.25,
        "month": 1.0,
        "year": 12.0
    }
    
    pm = period_multipliers.get(period, 1.0)
    
    base_revenue = 125800 * pm * multiplier
    base_cost = 75480 * pm * multiplier
    base_expense = 12580 * pm * multiplier
    base_transactions = int(856 * pm * multiplier)
    
    gross_profit = base_revenue - base_cost - base_expense
    gross_margin = (gross_profit / base_revenue * 100) if base_revenue > 0 else 0
    net_profit = gross_profit - (base_revenue * 0.05)  # 扣除5%税费
    
    return {
        "period": period,
        "store_id": store_id,
        "summary": {
            "total_revenue": round(base_revenue, 2),
            "total_cost": round(base_cost, 2),
            "total_expense": round(base_expense, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_margin": round(gross_margin, 1),
            "net_profit": round(net_profit, 2),
            "transaction_count": base_transactions
        },
        "store_stats": {
            "store_001": {"name": "中山路店", "revenue": 125800, "profit": 37800},
            "store_002": {"name": "人民广场店", "revenue": 98600, "profit": 28500},
            "store_003": {"name": "万达广场店", "revenue": 87200, "profit": 24300},
        } if not store_id else {},
        "category_stats": {
            "连衣裙": {"revenue": 45600, "percentage": 36},
            "牛仔裤": {"revenue": 38200, "percentage": 30},
            "T恤": {"revenue": 25100, "percentage": 20},
            "外套": {"revenue": 16900, "percentage": 14},
        }
    }


def get_anomaly_alerts(data: Dict[str, Any]) -> list:
    """获取异常预警"""
    alerts = []
    summary = data.get("summary", {})
    
    margin = summary.get("gross_margin", 0)
    if margin < 20:
        alerts.append({
            "type": "low_margin",
            "level": "critical" if margin < 10 else "warning",
            "message": f"毛利率较低 ({margin:.1f}%)，建议优化成本结构",
            "value": margin
        })
    
    if summary.get("transaction_count", 0) < 100:
        alerts.append({
            "type": "low_transactions",
            "level": "warning",
            "message": "交易笔数较少，建议增加营销活动",
            "value": summary.get("transaction_count", 0)
        })
    
    return alerts


# ==================== API路由 ====================
@app.get("/", response_class=HTMLResponse)
async def index():
    """返回主页面"""
    index_path = os.path.join(ASSETS_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "AI记账助手"}


@app.post("/api/query")
async def query_dashboard(request: QueryRequest):
    """查询看板数据"""
    try:
        dashboard_data = get_dashboard_data(request.query_type, request.store_id)
        alerts = get_anomaly_alerts(dashboard_data)
        
        return {
            "success": True,
            "dashboard_data": dashboard_data,
            "anomaly_alerts": alerts,
            "confidence": 1.0
        }
    except Exception as e:
        logger.error(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/voice")
async def voice_record(request: VoiceRequest):
    """语音报账"""
    try:
        # 实际应用中会调用工作流
        return {
            "success": True,
            "message": "语音报账成功",
            "extracted_data": {
                "type": "sale",
                "product": "红色连衣裙",
                "quantity": 1,
                "price": 299,
                "cost": 120
            },
            "confidence": 0.92
        }
    except Exception as e:
        logger.error(f"语音报账失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/image")
async def image_record(request: ImageRequest):
    """拍照录入"""
    try:
        # 实际应用中会调用工作流
        return {
            "success": True,
            "message": "拍照录入成功",
            "extracted_data": {
                "type": "sale",
                "items": [{"name": "蓝色牛仔裤", "quantity": 2, "price": 199}],
                "total": 398
            },
            "confidence": 0.88
        }
    except Exception as e:
        logger.error(f"拍照录入失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stores")
async def get_stores():
    """获取门店列表"""
    return {
        "stores": [
            {"id": "store_001", "name": "中山路店", "address": "中山路128号"},
            {"id": "store_002", "name": "人民广场店", "address": "人民广场地下B1"},
            {"id": "store_003", "name": "万达广场店", "address": "万达广场3楼"},
        ]
    }


@app.get("/api/records")
async def get_records(
    page: int = 1,
    page_size: int = 20,
    record_type: Optional[str] = None,
    store_id: Optional[str] = None
):
    """获取历史记录"""
    # 模拟数据
    records = [
        {
            "id": "rec_001",
            "time": "2026-05-24 14:30:00",
            "type": "sale",
            "product": "红色连衣裙",
            "store_id": "store_001",
            "store_name": "中山路店",
            "amount": 299
        },
        {
            "id": "rec_002",
            "time": "2026-05-24 11:20:00",
            "type": "sale",
            "product": "蓝色牛仔裤 x2",
            "store_id": "store_002",
            "store_name": "人民广场店",
            "amount": 398
        },
        {
            "id": "rec_003",
            "time": "2026-05-24 09:15:00",
            "type": "purchase",
            "product": "新款T恤 x50",
            "store_id": "store_001",
            "store_name": "中山路店",
            "amount": -2500
        },
    ]
    
    return {
        "records": records,
        "total": len(records),
        "page": page,
        "page_size": page_size
    }


# 挂载静态文件
if os.path.exists(ASSETS_DIR):
    app.mount("/static", StaticFiles(directory=ASSETS_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
