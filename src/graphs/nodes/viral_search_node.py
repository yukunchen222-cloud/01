"""
爆款视频搜索节点
根据素材关键词搜索抖音、快手等平台的爆款短剧视频
"""
import os
import json
import logging
from typing import List, Dict, Any

from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from coze_coding_dev_sdk import SearchClient

from graphs.state import ViralSearchInput, ViralSearchOutput

# 配置日志
logger = logging.getLogger(__name__)


def viral_search_node(
    state: ViralSearchInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ViralSearchOutput:
    """
    title: 爆款视频搜索
    desc: 根据素材关键词在抖音、快手等平台搜索同类爆款短剧视频
    
    Process:
    1. 构建搜索查询词（结合短剧类型和关键词）
    2. 在指定平台搜索爆款视频
    3. 收集视频数据（标题、播放量、点赞等）
    4. 筛选高质量爆款视频
    
    integrations: Web搜索
    """
    ctx = runtime.context
    keywords = state.drama_keywords
    drama_type = state.drama_type
    
    logger.info(f"开始搜索爆款视频，关键词: {keywords}, 类型: {drama_type}")
    
    # 构建搜索查询
    search_queries = []
    
    # 1. 平台+类型搜索
    search_queries.append(f"抖音 {drama_type} 短剧 爆款 热门")
    
    # 2. 关键词组合搜索
    if keywords:
        keyword_str = " ".join(keywords[:3])
        search_queries.append(f"{keyword_str} 短剧 抖音 高播放")
    
    # 3. 爆款公式搜索
    search_queries.append(f"{drama_type} 短剧 完结 热播 推荐")
    
    # 执行搜索
    viral_videos: List[Dict[str, Any]] = []
    search_client = SearchClient(ctx=ctx)
    
    for query in search_queries[:2]:  # 限制搜索次数
        try:
            logger.info(f"执行搜索: {query}")
            
            # 搜索抖音相关内容
            response = search_client.search(
                query=query,
                search_type="web",
                count=10,
                need_summary=True,
                sites="douyin.com,kuaishou.com",  # 限定抖音和快手
                time_range="1w"  # 最近一周
            )
            
            if response and response.web_items:
                for item in response.web_items:
                    video_info: Dict[str, Any] = {
                        "title": item.title or "",
                        "url": item.url or "",
                        "snippet": item.snippet or "",
                        "summary": item.summary or "",
                        "site_name": item.site_name or "",
                        "publish_time": item.publish_time or "",
                        "source": "搜索结果"
                    }
                    viral_videos.append(video_info)
                    
        except Exception as e:
            logger.warning(f"搜索失败 '{query}': {e}")
            continue
    
    # 去重和筛选
    seen_urls = set()
    unique_videos = []
    for video in viral_videos:
        url = video.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_videos.append(video)
    
    # 按相关性排序（简化处理，实际应该有更复杂的排序逻辑）
    # 这里我们保留前15个结果
    top_videos = unique_videos[:15]
    
    # 生成搜索摘要
    search_summary = f"共搜索到 {len(top_videos)} 个相关爆款视频，涵盖平台：抖音、快手"
    
    logger.info(f"搜索完成，找到 {len(top_videos)} 个有效视频")
    
    return ViralSearchOutput(
        viral_videos=top_videos,
        search_summary=search_summary
    )
