"""
知识库服务模块
负责知识检索、FAQ匹配、技术文档查询等功能
"""

import json
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SearchType(Enum):
    """搜索类型"""
    FAQ = "faq"
    TECHNICAL = "technical"
    PRODUCT = "product"
    COMPETITOR = "competitor"
    ALL = "all"

@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    title: str
    content: str
    category: str
    confidence: float
    source: str
    tags: List[str]
    related_items: List[str] = None

@dataclass
class KnowledgeItem:
    """知识项"""
    id: str
    title: str
    content: str
    category: str
    tags: List[str]
    confidence: float
    created_at: datetime
    updated_at: datetime

class KnowledgeService:
    """知识库服务"""
    
    def __init__(self, knowledge_base_path: str = "data/knowledge_base"):
        self.knowledge_base_path = knowledge_base_path
        self.faq_data = {}
        self.technical_data = {}
        self.product_data = {}
        self.competitor_data = {}
        self._load_knowledge_base()
    
    def _load_knowledge_base(self):
        """加载知识库数据"""
        try:
            # 加载FAQ数据
            faq_path = os.path.join(self.knowledge_base_path, "faq_database.json")
            if os.path.exists(faq_path):
                with open(faq_path, 'r', encoding='utf-8') as f:
                    self.faq_data = json.load(f)
            
            # 加载技术文档数据
            tech_path = os.path.join(self.knowledge_base_path, "technical_docs.json")
            if os.path.exists(tech_path):
                with open(tech_path, 'r', encoding='utf-8') as f:
                    self.technical_data = json.load(f)
            
            # 加载产品数据
            product_path = os.path.join(self.knowledge_base_path, "product_catalog.json")
            if os.path.exists(product_path):
                with open(product_path, 'r', encoding='utf-8') as f:
                    self.product_data = json.load(f)
            
            # 加载竞品分析数据
            competitor_path = os.path.join(self.knowledge_base_path, "competitor_analysis.json")
            if os.path.exists(competitor_path):
                with open(competitor_path, 'r', encoding='utf-8') as f:
                    self.competitor_data = json.load(f)
                    
            logger.info("知识库数据加载完成")
            
        except Exception as e:
            logger.error(f"加载知识库数据失败: {e}")
    
    async def search_knowledge(self, query: str, search_type: SearchType = SearchType.ALL, 
                             limit: int = 5) -> List[SearchResult]:
        """搜索知识库"""
        results = []
        
        try:
            if search_type in [SearchType.FAQ, SearchType.ALL]:
                faq_results = await self._search_faq(query, limit)
                results.extend(faq_results)
            
            if search_type in [SearchType.TECHNICAL, SearchType.ALL]:
                tech_results = await self._search_technical(query, limit)
                results.extend(tech_results)
            
            if search_type in [SearchType.PRODUCT, SearchType.ALL]:
                product_results = await self._search_product(query, limit)
                results.extend(product_results)
            
            if search_type in [SearchType.COMPETITOR, SearchType.ALL]:
                competitor_results = await self._search_competitor(query, limit)
                results.extend(competitor_results)
            
            # 按置信度排序并限制结果数量
            results.sort(key=lambda x: x.confidence, reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"搜索知识库失败: {e}")
            return []
    
    async def _search_faq(self, query: str, limit: int) -> List[SearchResult]:
        """搜索FAQ"""
        results = []
        query_lower = query.lower()
        
        for category in self.faq_data.get("faq_categories", []):
            for faq in category.get("questions", []):
                # 计算匹配度
                confidence = self._calculate_confidence(query_lower, faq)
                
                if confidence > 0.3:  # 置信度阈值
                    result = SearchResult(
                        id=faq["id"],
                        title=faq["question"],
                        content=faq["answer"],
                        category=category["category"],
                        confidence=confidence,
                        source="FAQ",
                        tags=faq.get("keywords", []),
                        related_items=faq.get("related_products", [])
                    )
                    results.append(result)
        
        return results
    
    async def _search_technical(self, query: str, limit: int) -> List[SearchResult]:
        """搜索技术文档"""
        results = []
        query_lower = query.lower()
        
        for category in self.technical_data.get("technical_categories", []):
            for doc in category.get("documents", []):
                # 计算匹配度
                confidence = self._calculate_tech_confidence(query_lower, doc)
                
                if confidence > 0.3:
                    result = SearchResult(
                        id=doc["id"],
                        title=doc["title"],
                        content=doc["content"],
                        category=category["category"],
                        confidence=confidence,
                        source="技术文档",
                        tags=doc.get("tags", [])
                    )
                    results.append(result)
        
        return results
    
    async def _search_product(self, query: str, limit: int) -> List[SearchResult]:
        """搜索产品信息"""
        results = []
        query_lower = query.lower()
        
        for product in self.product_data.get("products", []):
            # 计算匹配度
            confidence = self._calculate_product_confidence(query_lower, product)
            
            if confidence > 0.3:
                result = SearchResult(
                    id=product["id"],
                    title=product["name"],
                    content=self._format_product_content(product),
                    category="产品信息",
                    confidence=confidence,
                    source="产品目录",
                    tags=product.get("features", [])
                )
                results.append(result)
        
        return results
    
    async def _search_competitor(self, query: str, limit: int) -> List[SearchResult]:
        """搜索竞品分析"""
        results = []
        query_lower = query.lower()
        
        for competitor in self.competitor_data.get("competitor_analysis", []):
            # 检查是否匹配竞品名称
            if competitor["competitor"].lower() in query_lower:
                result = SearchResult(
                    id=f"COMP_{competitor['competitor']}",
                    title=f"{competitor['competitor']}竞品分析",
                    content=self._format_competitor_content(competitor),
                    category="竞品分析",
                    confidence=0.9,
                    source="竞品分析",
                    tags=["竞品", "对比"]
                )
                results.append(result)
        
        return results
    
    def _calculate_confidence(self, query: str, faq: Dict) -> float:
        """计算FAQ匹配置信度"""
        confidence = 0.0
        
        # 检查问题标题匹配
        question_lower = faq["question"].lower()
        if query in question_lower:
            confidence += 0.8
        
        # 检查关键词匹配
        keywords = [kw.lower() for kw in faq.get("keywords", [])]
        for keyword in keywords:
            if keyword in query:
                confidence += 0.3
        
        # 检查答案内容匹配
        answer_lower = faq["answer"].lower()
        if query in answer_lower:
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _calculate_tech_confidence(self, query: str, doc: Dict) -> float:
        """计算技术文档匹配置信度"""
        confidence = 0.0
        
        # 检查标题匹配
        title_lower = doc["title"].lower()
        if query in title_lower:
            confidence += 0.7
        
        # 检查标签匹配
        tags = [tag.lower() for tag in doc.get("tags", [])]
        for tag in tags:
            if tag in query:
                confidence += 0.4
        
        # 检查内容匹配
        content_lower = doc["content"].lower()
        if query in content_lower:
            confidence += 0.3
        
        return min(confidence, 1.0)
    
    def _calculate_product_confidence(self, query: str, product: Dict) -> float:
        """计算产品匹配置信度"""
        confidence = 0.0
        
        # 检查产品名称匹配
        name_lower = product["name"].lower()
        if query in name_lower:
            confidence += 0.8
        
        # 检查功能特性匹配
        features = [f.lower() for f in product.get("features", [])]
        for feature in features:
            if feature in query or query in feature:
                confidence += 0.3
        
        # 检查描述匹配
        description_lower = product.get("description", "").lower()
        if query in description_lower:
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _format_product_content(self, product: Dict) -> str:
        """格式化产品内容"""
        content = f"产品名称：{product['name']}\n"
        content += f"描述：{product.get('description', '')}\n"
        content += f"价格：{product.get('pricing', {}).get('professional', '请咨询')}\n"
        
        if product.get("features"):
            content += f"主要功能：{', '.join(product['features'])}\n"
        
        if product.get("use_cases"):
            content += f"适用场景：{', '.join(product['use_cases'])}\n"
        
        return content
    
    def _format_competitor_content(self, competitor: Dict) -> str:
        """格式化竞品分析内容"""
        content = f"竞品：{competitor['competitor']}\n"
        
        if competitor.get("our_advantages"):
            content += "我们的优势：\n"
            for advantage in competitor["our_advantages"]:
                content += f"• {advantage}\n"
        
        return content
    
    async def get_quick_answer(self, query: str) -> Optional[str]:
        """获取快速回答"""
        query_lower = query.lower()
        
        for quick_answer in self.faq_data.get("quick_answers", []):
            if quick_answer["trigger"].lower() in query_lower:
                return quick_answer["response"]
        
        return None
    
    async def check_escalation_trigger(self, query: str) -> bool:
        """检查是否需要升级到人工"""
        query_lower = query.lower()
        
        escalation_triggers = self.faq_data.get("escalation_triggers", [])
        for trigger in escalation_triggers:
            if trigger.lower() in query_lower:
                return True
        
        return False
    
    async def get_related_questions(self, faq_id: str) -> List[Dict]:
        """获取相关问题"""
        related = []
        
        for category in self.faq_data.get("faq_categories", []):
            for faq in category.get("questions", []):
                if faq["id"] == faq_id:
                    # 找到相同类别的其他问题
                    for other_faq in category.get("questions", []):
                        if other_faq["id"] != faq_id:
                            related.append({
                                "id": other_faq["id"],
                                "question": other_faq["question"]
                            })
                    break
        
        return related[:3]  # 返回最多3个相关问题

# 全局知识库服务实例
knowledge_service = KnowledgeService()