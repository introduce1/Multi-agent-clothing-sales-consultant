"""
LLM服务模块
提供统一的大语言模型调用接口
"""

import time
import httpx
import asyncio
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass
from openai import AsyncOpenAI

from config.settings import BaseConfig
from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class ChatMessage:
    """聊天消息数据类"""
    role: str  # system, user, assistant
    content: str
    name: Optional[str] = None

@dataclass
class LLMResponse:
    """LLM响应数据类"""
    content: str
    model: str
    provider: str
    usage: Dict[str, int]
    response_time: float
    success: bool
    error: Optional[str] = None

class LLMClient(ABC):
    """LLM客户端抽象基类"""
    
    def __init__(self, provider: str, config: Dict):
        self.provider = provider
        self.config = config
        self.client = None
        self._initialize_client()
    
    @abstractmethod
    def _initialize_client(self):
        """初始化客户端"""
        pass
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> LLMResponse:
        """聊天完成接口"""
        pass

class OpenAIClient(LLMClient):
    """OpenAI客户端实现"""
    
    def _initialize_client(self):
        """初始化OpenAI客户端"""
        self.client = AsyncOpenAI(
            api_key=self.config.get("api_key"),
            base_url=self.config.get("base_url"),
            timeout=self.config.get("timeout", 30),
            max_retries=self.config.get("max_retries", 3)
        )
    
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> LLMResponse:
        """OpenAI聊天完成"""
        start_time = time.time()
        
        try:
            # 转换消息格式
            openai_messages = []
            for msg in messages:
                message_dict = {"role": msg.role, "content": msg.content}
                if msg.name:
                    message_dict["name"] = msg.name
                openai_messages.append(message_dict)
            
            # 调用OpenAI API
            response = await self.client.chat.completions.create(
                model=model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            response_time = time.time() - start_time
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=model,
                provider=self.provider,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                response_time=response_time,
                success=True
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"OpenAI API调用失败: {str(e)}")
            
            return LLMResponse(
                content="",
                model=model,
                provider=self.provider,
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                response_time=response_time,
                success=False,
                error=str(e)
            )



class LLMService:
    """LLM服务管理器"""
    
    def __init__(self):
        self.clients: Dict[str, LLMClient] = {}
        self.config = BaseConfig()
        self._initialize_clients()
    
    def _initialize_clients(self):
        """初始化所有客户端"""
        llm_config = self.config.LLM_CONFIG
        
        # 只初始化OpenAI客户端
        if "openai" in llm_config:
            self.clients["openai"] = OpenAIClient("openai", llm_config["openai"])
    
    def get_client(self, provider: str) -> Optional[LLMClient]:
        """获取指定提供商的客户端"""
        return self.clients.get(provider)
    
    async def chat_completion(
        self,
        provider: str,
        model: str,
        messages: List[Union[ChatMessage, Dict[str, str]]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> LLMResponse:
        """统一的聊天完成接口"""
        client = self.get_client(provider)
        if not client:
            return LLMResponse(
                content="",
                model=model,
                provider=provider,
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                response_time=0,
                success=False,
                error=f"未找到提供商 {provider} 的客户端"
            )
        
        # 转换消息格式
        chat_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                chat_messages.append(ChatMessage(
                    role=msg["role"],
                    content=msg["content"],
                    name=msg.get("name")
                ))
            else:
                chat_messages.append(msg)
        
        return await client.chat_completion(
            messages=chat_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    
    async def _make_chat_completion(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        config: Dict = None
    ) -> str:
        """
        内部方法：调用指定提供商的聊天完成API
        
        Args:
            provider: 提供商名称
            model: 模型名称
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            config: 提供商配置
            
        Returns:
            str: 生成的响应内容
        """
        response = await self.chat_completion(
            provider=provider,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        if response.success:
            return response.content
        else:
            raise Exception(response.error or "LLM调用失败")

    async def get_agent_response(self, agent_name: str, messages: List[Dict[str, str]], context_info: Dict[str, Any] = None) -> LLMResponse:
        """
        获取智能体响应
        
        Args:
            agent_name: 智能体名称
            messages: 消息历史
            context_info: 上下文信息
            
        Returns:
            LLMResponse: 智能体响应对象
        """
        try:
            settings = get_settings()
            
            # 获取智能体配置
            agent_config = settings.AGENT_MODEL_CONFIG.get(agent_name, {})
            if not agent_config:
                logger.warning(f"未找到智能体 {agent_name} 的配置，使用默认配置")
                agent_config = {
                    "primary_model": "openai/gpt-4o-mini",
                    "fallback_model": "openai/gpt-3.5-turbo",
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
            
            # 解析主模型和备用模型
            primary_model = agent_config.get("primary_model", "openai/gpt-4o-mini")
            fallback_model = agent_config.get("fallback_model", "openai/gpt-3.5-turbo")
            
            # 获取模型参数
            temperature = agent_config.get("temperature", 0.7)
            max_tokens = agent_config.get("max_tokens", 1000)
            
            # 构建系统提示
            system_prompt = agent_config.get("system_prompt", "你是一个智能客服助手。")
            if context_info:
                system_prompt += f"\n\n当前上下文信息：{json.dumps(context_info, ensure_ascii=False)}"

            # 如果调用方已经提供了system消息，则避免重复注入，保持指令单一
            has_system = any(m.get("role") == "system" for m in messages)
            full_messages = messages if has_system else [{"role": "system", "content": system_prompt}] + messages
            
            # 尝试使用主模型
            try:
                provider, model = primary_model.split("/", 1)
                model_config = settings.LLM_CONFIG.get(provider, {})
                
                if not model_config:
                    raise ValueError(f"未找到提供商 {provider} 的配置")
                
                response = await self.chat_completion(
                    provider=provider,
                    model=model,
                    messages=full_messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                logger.info(f"智能体 {agent_name} 使用主模型 {primary_model} 成功生成响应")
                return response
                
            except Exception as e:
                logger.warning(f"主模型 {primary_model} 调用失败: {str(e)}，尝试备用模型")
                
                # 尝试使用备用模型
                try:
                    provider, model = fallback_model.split("/", 1)
                    model_config = settings.LLM_CONFIG.get(provider, {})
                    
                    if not model_config:
                        raise ValueError(f"未找到提供商 {provider} 的配置")
                    
                    response = await self.chat_completion(
                        provider=provider,
                        model=model,
                        messages=full_messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    
                    logger.info(f"智能体 {agent_name} 使用备用模型 {fallback_model} 成功生成响应")
                    return response
                    
                except Exception as fallback_error:
                    logger.error(f"备用模型 {fallback_model} 也调用失败: {str(fallback_error)}")
                    raise fallback_error
                    
        except Exception as e:
            logger.error(f"智能体 {agent_name} 响应生成失败: {str(e)}")
            return LLMResponse(
                content=f"抱歉，我暂时无法处理您的请求。请稍后再试。错误信息：{str(e)}",
                model="error",
                provider="error",
                usage={},
                response_time=0.0,
                success=False,
                error=str(e)
            )

# 全局LLM服务实例
llm_service = LLMService()