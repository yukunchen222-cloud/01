"""
商品知识库模块 - 用于商品匹配和NLU识别增强
"""
import os
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ProductKnowledge(BaseModel):
    """商品知识条目"""
    product_id: str = Field(..., description="商品ID")
    sku: str = Field(..., description="款号")
    name: str = Field(..., description="商品名称")
    category: str = Field(default="", description="类目")
    aliases: List[str] = Field(default=[], description="别名/简称")
    keywords: List[str] = Field(default=[], description="关键词")
    cost_price: float = Field(default=0.0, description="进价")
    sale_price: float = Field(default=0.0, description="售价")


class ProductKnowledgeBase:
    """商品知识库管理"""
    
    def __init__(self, org_id: str = "org_default"):
        self.org_id = org_id
        self.products: List[ProductKnowledge] = []
        self._load_products()
    
    def _load_products(self):
        """从数据文件加载商品"""
        products_file = os.path.join(
            os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects"),
            "data/products.json"
        )
        
        if os.path.exists(products_file):
            with open(products_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for p in data.get("products", []):
                    if p.get("org_id") == self.org_id or not p.get("org_id"):
                        # 生成别名和关键词
                        name = p.get("name", "")
                        aliases = self._generate_aliases(name)
                        keywords = self._extract_keywords(name, p.get("category", ""))
                        
                        self.products.append(ProductKnowledge(
                            product_id=p.get("product_id", ""),
                            sku=p.get("sku", ""),
                            name=name,
                            category=p.get("category", ""),
                            aliases=aliases,
                            keywords=keywords,
                            cost_price=p.get("cost_price", 0),
                            sale_price=p.get("sale_price", 0)
                        ))
    
    def _generate_aliases(self, name: str) -> List[str]:
        """生成商品别名"""
        aliases = []
        if not name:
            return aliases
        
        # 简单的别名生成规则
        # 1. 去掉颜色词
        colors = ["黑色", "白色", "红色", "蓝色", "灰色", "粉色", "黄色", "绿色", "紫色", "棕色"]
        for color in colors:
            if name.startswith(color):
                aliases.append(name[len(color):])
        
        # 2. 去掉尺码
        sizes = ["S码", "M码", "L码", "XL码", "XXL码", "大码", "小码"]
        for size in sizes:
            if size in name:
                aliases.append(name.replace(size, "").strip())
        
        return list(set(aliases))
    
    def _extract_keywords(self, name: str, category: str) -> List[str]:
        """提取关键词"""
        keywords = []
        
        # 添加类目
        if category:
            keywords.append(category)
        
        # 提取商品名中的关键词
        clothing_types = ["外套", "连衣裙", "衬衫", "裤子", "牛仔裤", "毛衣", "开衫", "T恤", "裙", "风衣", "大衣", "西装"]
        for ct in clothing_types:
            if ct in name:
                keywords.append(ct)
        
        # 提取颜色
        colors = ["黑色", "白色", "红色", "蓝色", "灰色", "粉色", "黄色", "绿色", "紫色", "棕色"]
        for color in colors:
            if color in name:
                keywords.append(color)
        
        return list(set(keywords))
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        搜索商品
        
        Args:
            query: 搜索词（商品名、SKU、别名等）
            top_k: 返回数量
        
        Returns:
            匹配的商品列表
        """
        query_lower = query.lower().strip()
        results = []
        
        for product in self.products:
            score = 0
            
            # SKU精确匹配
            if product.sku.lower() == query_lower:
                score = 100
            # 名称完全匹配
            elif product.name.lower() == query_lower:
                score = 95
            # 名称包含查询词
            elif query_lower in product.name.lower():
                score = 80
            # SKU包含查询词
            elif query_lower in product.sku.lower():
                score = 75
            # 别名匹配
            else:
                for alias in product.aliases:
                    if query_lower in alias.lower():
                        score = 70
                        break
            
            # 关键词匹配加分
            if score == 0:
                matched_keywords = sum(1 for k in product.keywords if k in query_lower)
                if matched_keywords > 0:
                    score = 50 + matched_keywords * 5
            
            if score > 0:
                results.append({
                    "product_id": product.product_id,
                    "sku": product.sku,
                    "name": product.name,
                    "category": product.category,
                    "cost_price": product.cost_price,
                    "sale_price": product.sale_price,
                    "score": score
                })
        
        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def get_by_sku(self, sku: str) -> Optional[ProductKnowledge]:
        """根据SKU获取商品"""
        for product in self.products:
            if product.sku == sku:
                return product
        return None
    
    def get_by_id(self, product_id: str) -> Optional[ProductKnowledge]:
        """根据ID获取商品"""
        for product in self.products:
            if product.product_id == product_id:
                return product
        return None
    
    def get_all_products(self) -> List[Dict]:
        """获取所有商品"""
        return [p.model_dump() for p in self.products]
    
    def get_categories(self) -> List[str]:
        """获取所有类目"""
        categories = set()
        for product in self.products:
            if product.category:
                categories.add(product.category)
        return sorted(list(categories))
    
    def get_price_range(self, product_name: str = None, category: str = None) -> Dict:
        """
        获取价格范围
        
        Args:
            product_name: 商品名称（模糊匹配）
            category: 类目
        
        Returns:
            价格范围 {min_price, max_price, avg_price}
        """
        prices = []
        
        for product in self.products:
            # 类目过滤
            if category and product.category != category:
                continue
            # 名称过滤
            if product_name and product_name.lower() not in product.name.lower():
                continue
            
            if product.sale_price > 0:
                prices.append(product.sale_price)
        
        if not prices:
            return {"min_price": 0, "max_price": 0, "avg_price": 0}
        
        return {
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": sum(prices) / len(prices)
        }
    
    def enrich_nlu_result(self, items: List[Dict]) -> List[Dict]:
        """
        增强NLU识别结果
        
        Args:
            items: NLU识别的商品列表
        
        Returns:
            增强后的商品列表（添加SKU、价格等信息）
        """
        enriched_items = []
        
        for item in items:
            product_name = item.get("name", "")
            
            # 搜索匹配的商品
            matches = self.search(product_name, top_k=1)
            
            if matches:
                best_match = matches[0]
                enriched_item = {
                    **item,
                    "sku": best_match.get("sku", item.get("sku", "")),
                    "product_id": best_match.get("product_id", ""),
                    "category": best_match.get("category", item.get("category", "")),
                    "unit_price": item.get("price") or best_match.get("sale_price", 0),
                    "cost_price": best_match.get("cost_price", 0),
                    "match_score": best_match.get("score", 0)
                }
            else:
                enriched_item = {
                    **item,
                    "sku": item.get("sku", ""),
                    "match_score": 0
                }
            
            enriched_items.append(enriched_item)
        
        return enriched_items


# 全局实例
_product_kb = None

def get_product_knowledge_base(org_id: str = "org_default") -> ProductKnowledgeBase:
    """获取商品知识库实例"""
    global _product_kb
    if _product_kb is None or _product_kb.org_id != org_id:
        _product_kb = ProductKnowledgeBase(org_id)
    return _product_kb


def search_product(query: str, org_id: str = "org_default") -> List[Dict]:
    """
    搜索商品（便捷函数）
    
    Args:
        query: 搜索词
        org_id: 组织ID
    
    Returns:
        匹配的商品列表
    """
    kb = get_product_knowledge_base(org_id)
    return kb.search(query)
