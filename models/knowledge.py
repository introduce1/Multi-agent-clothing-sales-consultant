# -*- coding: utf-8 -*-
"""
知识库相关数据模型
包括知识条目、分类、标签和搜索索引
"""
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Float, Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from .database import Base

beijing_tz = timezone(timedelta(hours=8))

# 知识条目和标签的多对多关联表
knowledge_tags = Table(
    'knowledge_tags',
    Base.metadata,
    Column('knowledge_id', Integer, ForeignKey('knowledge_entries.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('knowledge_tags_table.id'), primary_key=True)
)


class KnowledgeStatus(str, Enum):
    """知识条目状态枚举"""
    DRAFT = "draft"             # 草稿
    REVIEW = "review"           # 待审核
    PUBLISHED = "published"     # 已发布
    ARCHIVED = "archived"       # 已归档
    DELETED = "deleted"         # 已删除


class KnowledgeType(str, Enum):
    """知识类型枚举"""
    FAQ = "faq"                 # 常见问题
    TUTORIAL = "tutorial"       # 教程
    POLICY = "policy"           # 政策规定
    PRODUCT = "product"         # 产品信息
    TROUBLESHOOTING = "troubleshooting"  # 故障排除
    ANNOUNCEMENT = "announcement"  # 公告通知


class ContentFormat(str, Enum):
    """内容格式枚举"""
    TEXT = "text"               # 纯文本
    MARKDOWN = "markdown"       # Markdown
    HTML = "html"               # HTML
    JSON = "json"               # JSON结构化数据


class KnowledgeCategory(Base):
    """知识分类模型"""
    __tablename__ = "knowledge_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey("knowledge_categories.id"))
    
    # 分类属性
    icon = Column(String(100))              # 图标
    color = Column(String(20))              # 颜色
    sort_order = Column(Integer, default=0)  # 排序
    is_active = Column(Boolean, default=True)
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    updated_at = Column(DateTime, default=lambda: datetime.now(beijing_tz), onupdate=lambda: datetime.now(beijing_tz))
    
    # 元数据
    meta_data = Column(JSON)
    
    # 关联关系
    parent = relationship("KnowledgeCategory", remote_side=[id])
    children = relationship("KnowledgeCategory", back_populates="parent")
    knowledge_entries = relationship("KnowledgeEntry", back_populates="category")
    
    @hybrid_property
    def full_path(self):
        """完整路径"""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name
    
    @hybrid_property
    def entry_count(self):
        """知识条目数量"""
        return len([entry for entry in self.knowledge_entries if entry.status == KnowledgeStatus.PUBLISHED])
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parent_id": self.parent_id,
            "icon": self.icon,
            "color": self.color,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "full_path": self.full_path,
            "entry_count": self.entry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class KnowledgeTag(Base):
    """知识标签模型"""
    __tablename__ = "knowledge_tags_table"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)
    color = Column(String(20))              # 标签颜色
    usage_count = Column(Integer, default=0)  # 使用次数
    is_active = Column(Boolean, default=True)
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    updated_at = Column(DateTime, default=lambda: datetime.now(beijing_tz), onupdate=lambda: datetime.now(beijing_tz))
    
    # 关联关系
    knowledge_entries = relationship("KnowledgeEntry", secondary=knowledge_tags, back_populates="tags")
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "usage_count": self.usage_count,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class KnowledgeEntry(Base):
    """知识条目模型"""
    __tablename__ = "knowledge_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    content = Column(Text, nullable=False)
    summary = Column(Text)                  # 摘要
    
    # 分类和类型
    category_id = Column(Integer, ForeignKey("knowledge_categories.id"))
    knowledge_type = Column(String(20), default=KnowledgeType.FAQ)
    content_format = Column(String(20), default=ContentFormat.TEXT)
    
    # 状态信息
    status = Column(String(20), default=KnowledgeStatus.DRAFT)
    is_featured = Column(Boolean, default=False)  # 是否精选
    is_public = Column(Boolean, default=True)     # 是否公开
    
    # 作者信息
    author_id = Column(String(50))
    author_name = Column(String(100))
    reviewer_id = Column(String(50))
    reviewer_name = Column(String(100))
    
    # 统计信息
    view_count = Column(Integer, default=0)       # 浏览次数
    like_count = Column(Integer, default=0)       # 点赞次数
    share_count = Column(Integer, default=0)      # 分享次数
    helpful_count = Column(Integer, default=0)    # 有用次数
    
    # 搜索相关
    keywords = Column(Text)                       # 关键词
    search_weight = Column(Float, default=1.0)   # 搜索权重
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    updated_at = Column(DateTime, default=lambda: datetime.now(beijing_tz), onupdate=lambda: datetime.now(beijing_tz))
    published_at = Column(DateTime)
    reviewed_at = Column(DateTime)
    
    # 版本信息
    version = Column(String(20), default="1.0")
    previous_version_id = Column(Integer, ForeignKey("knowledge_entries.id"))
    
    # 元数据
    meta_data = Column(JSON)
    
    # 关联关系
    category = relationship("KnowledgeCategory", back_populates="knowledge_entries")
    tags = relationship("KnowledgeTag", secondary=knowledge_tags, back_populates="knowledge_entries")
    previous_version = relationship("KnowledgeEntry", remote_side=[id])
    search_indices = relationship("KnowledgeSearchIndex", back_populates="knowledge_entry", cascade="all, delete-orphan")
    
    @hybrid_property
    def is_published(self):
        """是否已发布"""
        return self.status == KnowledgeStatus.PUBLISHED
    
    @hybrid_property
    def engagement_score(self):
        """参与度评分"""
        return (self.view_count * 0.1 + 
                self.like_count * 2 + 
                self.share_count * 3 + 
                self.helpful_count * 5)
    
    @hybrid_property
    def tag_names(self):
        """标签名称列表"""
        return [tag.name for tag in self.tags]
    
    def increment_view(self):
        """增加浏览次数"""
        self.view_count += 1
    
    def increment_like(self):
        """增加点赞次数"""
        self.like_count += 1
    
    def increment_helpful(self):
        """增加有用次数"""
        self.helpful_count += 1
    
    def to_dict(self, include_content=True):
        """转换为字典"""
        result = {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "category_id": self.category_id,
            "knowledge_type": self.knowledge_type,
            "content_format": self.content_format,
            "status": self.status,
            "is_featured": self.is_featured,
            "is_public": self.is_public,
            "author_name": self.author_name,
            "reviewer_name": self.reviewer_name,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "share_count": self.share_count,
            "helpful_count": self.helpful_count,
            "engagement_score": self.engagement_score,
            "keywords": self.keywords,
            "search_weight": self.search_weight,
            "version": self.version,
            "tags": self.tag_names,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None
        }
        
        if include_content:
            result["content"] = self.content
            
        return result


class KnowledgeSearchIndex(Base):
    """知识搜索索引模型"""
    __tablename__ = "knowledge_search_indices"
    
    id = Column(Integer, primary_key=True, index=True)
    knowledge_entry_id = Column(Integer, ForeignKey("knowledge_entries.id"))
    
    # 索引内容
    indexed_content = Column(Text, nullable=False)  # 索引化的内容
    content_type = Column(String(20))               # 内容类型 (title, content, keywords)
    
    # 搜索权重
    weight = Column(Float, default=1.0)
    
    # 语言信息
    language = Column(String(10), default="zh")
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    updated_at = Column(DateTime, default=lambda: datetime.now(beijing_tz), onupdate=lambda: datetime.now(beijing_tz))
    
    # 关联关系
    knowledge_entry = relationship("KnowledgeEntry", back_populates="search_indices")
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "knowledge_entry_id": self.knowledge_entry_id,
            "indexed_content": self.indexed_content,
            "content_type": self.content_type,
            "weight": self.weight,
            "language": self.language,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class KnowledgeFeedback(Base):
    """知识反馈模型"""
    __tablename__ = "knowledge_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    knowledge_entry_id = Column(Integer, ForeignKey("knowledge_entries.id"))
    
    # 反馈信息
    user_id = Column(String(50))
    feedback_type = Column(String(20))  # helpful, not_helpful, suggestion, error
    rating = Column(Integer)            # 评分 1-5
    comment = Column(Text)              # 评论
    
    # 联系信息
    contact_email = Column(String(100))
    
    # 状态信息
    is_processed = Column(Boolean, default=False)
    processor_id = Column(String(50))
    process_notes = Column(Text)
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    processed_at = Column(DateTime)
    
    # 元数据
    meta_data = Column(JSON)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "knowledge_entry_id": self.knowledge_entry_id,
            "user_id": self.user_id,
            "feedback_type": self.feedback_type,
            "rating": self.rating,
            "comment": self.comment,
            "contact_email": self.contact_email,
            "is_processed": self.is_processed,
            "processor_id": self.processor_id,
            "process_notes": self.process_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None
        }