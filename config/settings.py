# -*- coding: utf-8 -*-
"""
系统配置文件
定义应用程序的各种配置参数
"""
import os
from pathlib import Path
from typing import Dict, Any, List

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 基础配置
class BaseConfig:
    """基础配置类"""
    
    # 应用信息
    APP_NAME = "小衣助手"
    APP_VERSION = "1.0.0"
    APP_DESCRIPTION = "基于多智能体架构的智能服装销售顾问系统"
    
    # 服务器配置
    HOST = os.getenv("HOST", "localhost")
    PORT = int(os.getenv("PORT", 8000))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", str(PROJECT_ROOT / "logs" / "customer_service.log"))
    LOG_MAX_SIZE = int(os.getenv("LOG_MAX_SIZE", 10 * 1024 * 1024))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 5))
    
    # 数据库配置
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT}/data/customer_service.db")
    DATABASE_ECHO = os.getenv("DATABASE_ECHO", "false").lower() == "true"
    
    # Redis配置
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
    
    # 安全配置
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    
    # CORS配置
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_HEADERS = ["*"]
    
    # LLM配置 - 简化为只使用GPT-4o模型
    LLM_CONFIG = {
        # OpenAI配置 - 只保留GPT-4o
        "openai": {
            "api_key": "sk-3f5UEVi1sTqlAsznXQyvFH1Gii3IodN3edQpRnradi4wn4Cu",
            "base_url": "https://api.chatanywhere.tech/v1",
            "organization": None,
            "timeout": 30,
            "max_retries": 3,
            "models": {
                "gpt-4o": {
                    "name": "GPT-4o",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                    "cost_per_1k_tokens": {"input": 0.005, "output": 0.015}
                }
            }
        }
    }
    
    # 智能体模型分配策略 - 统一使用GPT-4o
    AGENT_MODEL_CONFIG = {
        "reception_agent": {
            "primary_model": "openai/gpt-4o",
            "fallback_model": "openai/gpt-4o",
            "temperature": 0.7,
            "max_tokens": 1000,
            "system_prompt": "你是一个专业的客服接待员，负责热情接待客户并准确识别客户意图。"
        },
        "smart_collaboration_system": {
            "primary_model": "openai/gpt-4o",
            "fallback_model": "openai/gpt-4o",
            "temperature": 0.2,
            "max_tokens": 1200,
            "system_prompt": "你是智能体协作分析与编排专家。请仅输出严格的JSON，字段包括 task_complexity、required_capabilities、recommended_agents（每项含 agent_id、role、priority、parallel 可选）、collaboration_mode、workflow_template、estimated_duration、task_priority、success_probability、fallback_agent、special_requirements。不要输出除JSON外的任何文本。"
        },
        "collaboration_analyzer": {
            "primary_model": "openai/gpt-4o",
            "fallback_model": "openai/gpt-4o",
            "temperature": 0.2,
            "max_tokens": 1200,
            "system_prompt": "你是智能体协作分析专家。请仅输出严格的JSON，字段包括 task_complexity、required_capabilities、recommended_agents（每项含 agent_id、role、priority、parallel 可选）、collaboration_mode、workflow_template、estimated_duration、task_priority、success_probability、fallback_agent、special_requirements。不要输出除JSON外的任何文本。"
        },
        "knowledge_agent": {
            "primary_model": "openai/gpt-4o",
            "fallback_model": "openai/gpt-4o",
            "temperature": 0.3,
            "max_tokens": 1500,
            "system_prompt": "你是一个知识库专家，能够准确检索和提供产品相关信息。"
        },
        "sales_agent": {
            "primary_model": "openai/gpt-4o",
            "fallback_model": "openai/gpt-4o",
            "temperature": 0.8,
            "max_tokens": 2000,
            "system_prompt": "你是一个专业的销售顾问，能够理解客户需求并提供个性化的产品推荐。"
        },
        "order_agent": {
            "primary_model": "openai/gpt-4o",
            "fallback_model": "openai/gpt-4o",
            "temperature": 0.5,
            "max_tokens": 1200,
            "system_prompt": "你是一个订单处理专员，能够高效处理订单相关问题和售后服务。"
        },
        "styling_agent": {
            "primary_model": "openai/gpt-4o",
            "fallback_model": "openai/gpt-4o",
            "temperature": 0.7,
            "max_tokens": 1500,
            "system_prompt": "你是一个时尚搭配专家，能够根据客户需求提供专业的穿搭建议和风格推荐。"
        }
    }

    # 智能体配置
    AGENT_CONFIG = {
        "reception_agent": {
            "name": "客服接待智能体",
            "description": "负责客户接待、意图识别和初步分流",
            "enabled": True,
            "max_concurrent": 100,
            "timeout": 30
        },
        "smart_collaboration_system": {
            "name": "智能协同系统",
            "description": "负责多智能体协作分析、编排与任务分配",
            "enabled": True,
            "max_concurrent": 100,
            "timeout": 30
        },
        "knowledge_agent": {
            "name": "知识库智能体", 
            "description": "负责产品知识查询和问题解答",
            "enabled": True,
            "max_concurrent": 50,
            "timeout": 20
        },
        "sales_agent": {
            "name": "销售顾问智能体",
            "description": "负责销售咨询和产品推荐",
            "enabled": True,
            "max_concurrent": 30,
            "timeout": 25
        },
        "order_agent": {
            "name": "订单处理智能体",
            "description": "负责订单查询、处理和售后服务",
            "enabled": True,
            "max_concurrent": 40,
            "timeout": 35
        }
    }
    
    # 路由配置
    ROUTING_CONFIG = {
        "default_agent": "reception_agent",
        "fallback_agent": "reception_agent",
        "max_routing_attempts": 3,
        "routing_timeout": 10
    }
    
    # 性能配置
    PERFORMANCE_CONFIG = {
        "max_sessions": 1000,
        "session_timeout": 1800,  # 30分钟
        "cleanup_interval": 300,  # 5分钟
        "metrics_retention_days": 30
    }
    
    # 业务配置
    BUSINESS_CONFIG = {
        "default_language": "zh-CN",
        "supported_languages": ["zh-CN", "en-US"],
        "max_message_length": 2000,
        "max_context_messages": 20,
        "confidence_threshold": 0.7
    }


class DevelopmentConfig(BaseConfig):
    """开发环境配置"""
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    DATABASE_ECHO = True


class ProductionConfig(BaseConfig):
    """生产环境配置"""
    DEBUG = False
    LOG_LEVEL = "INFO"
    DATABASE_ECHO = False
    
    # 生产环境安全配置
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "https://yourdomain.com").split(",")


# 配置映射
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig
}

# 获取当前环境配置
ENV = os.getenv("ENV", "development")
Config = config_map.get(ENV, DevelopmentConfig)

# 智能体能力配置
AGENT_CAPABILITIES = {
    "reception_agent": {
        "intent_recognition": {
            "name": "意图识别",
            "description": "识别用户意图和需求",
            "enabled": True,
            "confidence_threshold": 0.8
        },
        "emotion_analysis": {
            "name": "情感分析",
            "description": "分析用户情感状态",
            "enabled": True,
            "confidence_threshold": 0.7
        },
        "routing": {
            "name": "智能路由",
            "description": "将用户请求路由到合适的智能体",
            "enabled": True,
            "confidence_threshold": 0.9
        }
    },
    "knowledge_agent": {
        "semantic_search": {
            "name": "语义搜索",
            "description": "基于语义的知识检索",
            "enabled": True,
            "confidence_threshold": 0.75
        },
        "knowledge_retrieval": {
            "name": "知识检索",
            "description": "从知识库中检索相关信息",
            "enabled": True,
            "confidence_threshold": 0.8
        },
        "solution_recommendation": {
            "name": "解决方案推荐",
            "description": "推荐解决方案",
            "enabled": True,
            "confidence_threshold": 0.7
        }
    },
    "sales_agent": {
        "opportunity_identification": {
            "name": "机会识别",
            "description": "识别销售机会",
            "enabled": True,
            "confidence_threshold": 0.8
        },
        "personalized_recommendation": {
            "name": "个性化推荐",
            "description": "基于客户画像的个性化推荐",
            "enabled": True,
            "confidence_threshold": 0.75
        },
        "quote_generation": {
            "name": "报价生成",
            "description": "生成产品报价",
            "enabled": True,
            "confidence_threshold": 0.9
        }
    },
    "order_agent": {
        "order_creation": {
            "name": "订单创建",
            "description": "创建新订单",
            "enabled": True,
            "confidence_threshold": 0.95
        },
        "order_tracking": {
            "name": "订单跟踪",
            "description": "跟踪订单状态",
            "enabled": True,
            "confidence_threshold": 0.9
        },
        "payment_processing": {
            "name": "支付处理",
            "description": "处理支付相关事务",
            "enabled": True,
            "confidence_threshold": 0.95
        },
        "after_sales_service": {
            "name": "售后服务",
            "description": "提供售后服务支持",
            "enabled": True,
            "confidence_threshold": 0.8
        }
    }
}

# 工作流配置
WORKFLOW_CONFIG = {
    "customer_onboarding": {
        "name": "客户入驻流程",
        "description": "新客户的完整服务流程",
        "steps": [
            {"agent": "reception_agent", "action": "greeting"},
            {"agent": "reception_agent", "action": "intent_recognition"},
            {"agent": "knowledge_agent", "action": "provide_info"},
            {"agent": "sales_agent", "action": "opportunity_assessment"}
        ]
    },
    "order_processing": {
        "name": "订单处理流程",
        "description": "完整的订单处理流程",
        "steps": [
            {"agent": "reception_agent", "action": "order_intent_recognition"},
            {"agent": "order_agent", "action": "order_creation"},
            {"agent": "order_agent", "action": "payment_processing"},
            {"agent": "order_agent", "action": "order_confirmation"}
        ]
    },
    "problem_resolution": {
        "name": "问题解决流程",
        "description": "客户问题的解决流程",
        "steps": [
            {"agent": "reception_agent", "action": "problem_identification"},
            {"agent": "knowledge_agent", "action": "solution_search"},
            {"agent": "order_agent", "action": "after_sales_support"}
        ]
    }
}

# API配置
API_CONFIG = {
    "title": Config.APP_NAME,
    "description": Config.APP_DESCRIPTION,
    "version": Config.APP_VERSION,
    "docs_url": "/docs" if Config.DEBUG else None,
    "redoc_url": "/redoc" if Config.DEBUG else None,
    "openapi_url": "/openapi.json" if Config.DEBUG else None
}

# 中间件配置
MIDDLEWARE_CONFIG = {
    "cors": {
        "allow_origins": Config.CORS_ORIGINS,
        "allow_methods": Config.CORS_METHODS,
        "allow_headers": Config.CORS_HEADERS,
        "allow_credentials": True
    },
    "gzip": {
        "minimum_size": 1000
    },
    "trusted_host": {
        "allowed_hosts": ["*"] if Config.DEBUG else ["yourdomain.com"]
    }
}

# 监控配置
MONITORING_CONFIG = {
    "health_check_interval": 60,  # 秒
    "performance_metrics_interval": 300,  # 5分钟
    "alert_thresholds": {
        "response_time": 5.0,  # 秒
        "error_rate": 0.05,  # 5%
        "memory_usage": 0.8,  # 80%
        "cpu_usage": 0.8  # 80%
    }
}

# 缓存配置
CACHE_CONFIG = {
    "default_ttl": 3600,  # 1小时
    "knowledge_cache_ttl": 7200,  # 2小时
    "session_cache_ttl": 1800,  # 30分钟
    "analytics_cache_ttl": 300  # 5分钟
}

# Settings类定义
class Settings(BaseConfig):
    """应用设置类"""
    
    def __init__(self):
        super().__init__()
        # 确保必要的目录存在
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        directories = [
            PROJECT_ROOT / "logs",
            PROJECT_ROOT / "data",
            PROJECT_ROOT / "uploads",
            PROJECT_ROOT / "static"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    @property
    def agent_config(self):
        """获取智能体配置"""
        return AGENT_CONFIG
    
    @property
    def routing_config(self):
        """获取路由配置"""
        return ROUTING_CONFIG
    
    @property
    def performance_config(self):
        """获取性能配置"""
        return PERFORMANCE_CONFIG
    
    @property
    def business_config(self):
        """获取业务配置"""
        return BUSINESS_CONFIG
    
    @property
    def middleware_config(self):
        """获取中间件配置"""
        return MIDDLEWARE_CONFIG
    
    @property
    def monitoring_config(self):
        """获取监控配置"""
        return MONITORING_CONFIG
    
    @property
    def cache_config(self):
        """获取缓存配置"""
        return CACHE_CONFIG

# 全局设置实例
_settings = None

def get_settings() -> Settings:
    """获取设置实例（单例模式）"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

# 为了向后兼容，创建一个默认的settings实例
settings = get_settings()