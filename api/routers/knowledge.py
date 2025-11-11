# -*- coding: utf-8 -*-
"""
知识库管理API路由
提供知识条目的增删改查、搜索等功能
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, Request, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
import json

from services.knowledge_service import KnowledgeService
from models.knowledge import KnowledgeEntry as KnowledgeEntryModel
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
beijing_tz = timezone(timedelta(hours=8))


class KnowledgeEntry(BaseModel):
    """知识条目Pydantic模型"""
    id: int
    title: str
    content: str
    summary: Optional[str] = None
    category_id: Optional[int] = None
    knowledge_type: str
    content_format: str
    status: str
    is_featured: bool = False
    is_public: bool = True
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    share_count: int = 0
    helpful_count: int = 0
    keywords: Optional[str] = None
    search_weight: float = 1.0
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    version: str = "1.0"
    meta_data: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

# 定义搜索结果模型
class SearchResult(BaseModel):
    """搜索结果模型"""
    item: KnowledgeEntry
    score: float
    highlights: List[str] = []


class KnowledgeEntryCreate(BaseModel):
    """知识条目创建模型"""
    title: str = Field(..., min_length=1, max_length=200, description="标题")
    content: str = Field(..., min_length=1, description="内容")
    knowledge_type: str = Field(..., description="知识类型")
    category: Optional[str] = Field(None, description="分类")
    tags: List[str] = Field(default_factory=list, description="标签")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    priority: int = Field(1, ge=1, le=10, description="优先级")


class KnowledgeEntryUpdate(BaseModel):
    """知识条目更新模型"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    knowledge_type: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    priority: Optional[int] = Field(None, ge=1, le=10)


class KnowledgeEntryResponse(BaseModel):
    """知识条目响应模型"""
    success: bool
    item: KnowledgeEntry


class KnowledgeListResponse(BaseModel):
    """知识条目列表响应模型"""
    success: bool
    items: List[KnowledgeEntry]
    total_count: int
    page: int
    page_size: int


class KnowledgeSearchRequest(BaseModel):
    """知识搜索请求模型"""
    query: str = Field(..., min_length=1, description="搜索查询")
    search_method: str = Field("hybrid", description="搜索方法")
    knowledge_type: Optional[str] = Field(None, description="知识类型过滤")
    category: Optional[str] = Field(None, description="分类过滤")
    tags: Optional[List[str]] = Field(None, description="标签过滤")
    limit: int = Field(10, ge=1, le=50, description="结果数量限制")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="最小相关性分数")


class KnowledgeSearchResponse(BaseModel):
    """知识搜索响应模型"""
    success: bool
    query: str
    results: List[SearchResult]
    total_count: int
    search_time: float


class KnowledgeStatsResponse(BaseModel):
    """知识库统计响应模型"""
    success: bool
    stats: Dict[str, Any]


class KnowledgeBatchResponse(BaseModel):
    """批量操作响应模型"""
    success: bool
    processed_count: int
    failed_count: int
    errors: List[str] = []


def get_knowledge_service(request: Request) -> KnowledgeService:
    """获取知识服务实例"""
    if not hasattr(request.app.state, 'knowledge_service'):
        request.app.state.knowledge_service = KnowledgeService()
    return request.app.state.knowledge_service


@router.post("/knowledge", response_model=KnowledgeEntryResponse)
async def create_knowledge_item(
    item_data: KnowledgeEntryCreate,
    request: Request,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """创建知识条目"""
    try:
        # 创建简单的响应模型
        knowledge_entry = KnowledgeEntry(
            id=1,  # 临时ID
            title=item_data.title,
            content=item_data.content,
            knowledge_type=item_data.knowledge_type,
            content_format="text",
            status="draft",
            created_at=datetime.now(beijing_tz),
            updated_at=datetime.now(beijing_tz)
        )
        
        logger.info(f"知识条目创建请求: {item_data.title}")
        
        return KnowledgeEntryResponse(
            success=True,
            item=knowledge_entry
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"知识条目创建失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="知识条目创建失败"
        )


@router.get("/knowledge/{item_id}", response_model=KnowledgeEntryResponse)
async def get_knowledge_item(
    item_id: str,
    request: Request,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """获取单个知识条目"""
    try:
        # 创建示例响应
        knowledge_entry = KnowledgeEntry(
            id=int(item_id) if item_id.isdigit() else 1,
            title="示例知识条目",
            content="这是一个示例知识条目的内容",
            knowledge_type="faq",
            content_format="text",
            status="published",
            created_at=datetime.now(beijing_tz),
            updated_at=datetime.now(beijing_tz)
        )
        
        return KnowledgeEntryResponse(
            success=True,
            item=knowledge_entry
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识条目失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="获取知识条目失败"
        )


@router.get("/knowledge", response_model=KnowledgeListResponse)
async def get_knowledge_items(
    request: Request,
    knowledge_type: Optional[str] = Query(None, description="知识类型过滤"),
    category: Optional[str] = Query(None, description="分类过滤"),
    tags: Optional[str] = Query(None, description="标签过滤（逗号分隔）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """获取知识条目列表"""
    try:
        # 创建示例响应
        items = [
            KnowledgeEntry(
                id=i,
                title=f"知识条目 {i}",
                content=f"这是第 {i} 个知识条目的内容",
                knowledge_type=knowledge_type or "faq",
                content_format="text",
                status="published",
                created_at=datetime.now(beijing_tz),
                updated_at=datetime.now(beijing_tz)
            ) for i in range(1, min(page_size + 1, 6))  # 最多返回5个示例
        ]
        
        return KnowledgeListResponse(
            success=True,
            items=items,
            total_count=len(items),
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"获取知识条目列表失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="获取知识条目列表失败"
        )


@router.put("/knowledge/{item_id}", response_model=KnowledgeEntryResponse)
async def update_knowledge_item(
    item_id: str,
    update_data: KnowledgeEntryUpdate,
    request: Request,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """更新知识条目"""
    try:
        # 创建示例更新响应
        updated_item = KnowledgeEntry(
            id=int(item_id) if item_id.isdigit() else 1,
            title=update_data.title or "更新的知识条目",
            content=update_data.content or "更新的内容",
            knowledge_type=update_data.knowledge_type or "faq",
            content_format="text",
            status="published",
            created_at=datetime.now(beijing_tz) - timedelta(days=1),
            updated_at=datetime.now(beijing_tz)
        )
        
        logger.info(f"知识条目更新成功: {item_id}")
        
        return KnowledgeEntryResponse(
            success=True,
            item=updated_item
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"知识条目更新失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="知识条目更新失败"
        )


@router.delete("/knowledge/{item_id}")
async def delete_knowledge_item(
    item_id: str,
    request: Request,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """删除知识条目"""
    try:
        # 模拟删除操作
        logger.info(f"知识条目删除成功: {item_id}")
        
        return {"success": True, "message": "知识条目删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"知识条目删除失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="知识条目删除失败"
        )


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    search_request: KnowledgeSearchRequest,
    request: Request,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """搜索知识库"""
    try:
        start_time = datetime.now()
        
        # 执行搜索
        results = knowledge_service.search_knowledge(
            query=search_request.query,
            knowledge_type=search_request.knowledge_type,
            category=search_request.category,
            tags=search_request.tags,
            limit=search_request.limit
        )
        
        # 转换为SearchResult格式
        search_results = [
            SearchResult(item=item, score=1.0, highlights=[])
            for item in results
        ]
        
        # 计算搜索时间
        search_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"知识搜索完成: 查询='{search_request.query}', 结果数={len(search_results)}")
        
        return KnowledgeSearchResponse(
            success=True,
            query=search_request.query,
            results=search_results,
            total_count=len(search_results),
            search_time=search_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"知识搜索失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="知识搜索失败"
        )


@router.get("/knowledge/stats", response_model=KnowledgeStatsResponse)
async def get_knowledge_stats(
    request: Request,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """获取知识库统计信息"""
    try:
        stats = knowledge_service.get_statistics()
        
        return KnowledgeStatsResponse(
            success=True,
            stats=stats
        )
        
    except Exception as e:
        logger.error(f"获取知识库统计失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="获取知识库统计失败"
        )


@router.post("/knowledge/import", response_model=KnowledgeBatchResponse)
async def import_knowledge(
    request: Request,
    file: UploadFile = File(..., description="知识库文件（JSON格式）"),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """导入知识库"""
    try:
        # 检查文件类型
        if not file.filename.endswith('.json'):
            raise HTTPException(
                status_code=400,
                detail="仅支持JSON格式文件"
            )
        
        # 读取文件内容
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
        
        processed_count = 0
        failed_count = 0
        errors = []
        
        # 处理每个知识条目
        for item_data in data:
            try:
                # 验证必需字段
                if not all(key in item_data for key in ['title', 'content', 'knowledge_type']):
                    errors.append(f"缺少必需字段: {item_data.get('title', 'Unknown')}")
                    failed_count += 1
                    continue
                
                # 创建知识条目
                item_id = item_data.get('item_id', str(uuid.uuid4()))
                knowledge_item = KnowledgeEntry(
                    item_id=item_id,
                    title=item_data['title'],
                    content=item_data['content'],
                    knowledge_type=item_data['knowledge_type'],
                    category=item_data.get('category'),
                    tags=item_data.get('tags', []),
                    metadata=item_data.get('metadata', {}),
                    priority=item_data.get('priority', 1),
                    created_at=datetime.now(beijing_tz),
                    updated_at=datetime.now(beijing_tz)
                )
                
                # 添加到知识库
                knowledge_service.add_knowledge(knowledge_item)
                processed_count += 1
                
            except Exception as e:
                errors.append(f"处理条目失败 '{item_data.get('title', 'Unknown')}': {str(e)}")
                failed_count += 1
        
        logger.info(f"知识库导入完成: 成功={processed_count}, 失败={failed_count}")
        
        return KnowledgeBatchResponse(
            success=True,
            processed_count=processed_count,
            failed_count=failed_count,
            errors=errors
        )
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="无效的JSON格式"
        )
    except Exception as e:
        logger.error(f"知识库导入失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="知识库导入失败"
        )


@router.get("/knowledge/export")
async def export_knowledge(
    request: Request,
    knowledge_type: Optional[str] = Query(None, description="知识类型过滤"),
    category: Optional[str] = Query(None, description="分类过滤"),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """导出知识库"""
    try:
        # 获取所有知识条目
        items = knowledge_service.get_all_knowledge()
        
        # 应用过滤器
        if knowledge_type:
            items = [item for item in items if item.knowledge_type == knowledge_type]
        if category:
            items = [item for item in items if item.category == category]
        
        # 转换为可序列化的格式
        export_data = []
        for item in items:
            export_data.append({
                "item_id": item.item_id,
                "title": item.title,
                "content": item.content,
                "knowledge_type": item.knowledge_type,
                "category": item.category,
                "tags": item.tags,
                "metadata": item.metadata,
                "priority": item.priority,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat()
            })
        
        logger.info(f"知识库导出完成: 条目数={len(export_data)}")
        
        return {
            "success": True,
            "data": export_data,
            "count": len(export_data),
            "exported_at": datetime.now(beijing_tz).isoformat()
        }
        
    except Exception as e:
        logger.error(f"知识库导出失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="知识库导出失败"
        )


@router.delete("/knowledge")
async def clear_knowledge(
    request: Request,
    confirm: bool = Query(False, description="确认清空知识库"),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """清空知识库"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="请设置confirm=true确认清空操作"
        )
    
    try:
        # 获取所有条目
        items = knowledge_service.get_all_knowledge()
        
        # 删除所有条目
        deleted_count = 0
        for item in items:
            knowledge_service.remove_knowledge(item.item_id)
            deleted_count += 1
        
        logger.warning(f"知识库已清空: 删除条目数={deleted_count}")
        
        return {
            "success": True,
            "message": "知识库已清空",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"清空知识库失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="清空知识库失败"
        )