# 多智能体服装销售顾问

一个基于多智能体架构的服装销售顾问，支持智能对话、订单处理、知识库管理等功能。

## 🚀 功能特性

### 核心功能
- **多智能体协作**: 支持接待、销售、订单、知识、搭配等多个专业智能体
- **智能路由**: 基于意图识别的精确智能体路由
- **智能对话**: 基于大语言模型的自然语言理解和生成
- **知识库管理**: 支持FAQ、产品信息、政策文档等知识管理
- **订单处理**: 完整的订单生命周期管理
- **客户管理**: 客户信息、画像、交互历史管理
- **搭配建议**: 专业的服装搭配和风格推荐

### 技术特性
- **异步架构**: 基于FastAPI的高性能异步Web框架
- **微服务设计**: 模块化的智能体架构，易于扩展
- **实时通信**: WebSocket支持实时对话
- **数据分析**: 完整的性能监控和业务分析
- **多渠道接入**: 支持Web、移动端
- **智能协作**: 支持多智能体并行、串行、咨询等多种协作模式

## 🏗️ 系统架构
<img width="644" height="670" alt="image" src="https://github.com/user-attachments/assets/d0ef5555-6bc5-439d-99d6-dd8cfce70923" />

## 🛠️ 安装部署

### 环境要求
- Python 3.8+
- PostgreSQL 12+ (可选，默认使用SQLite)
- Redis 6+ (可选，用于缓存)

### 快速开始


1. **安装依赖**
```bash
pip install -r requirements.txt
```

2. **配置环境变量**
```bash
cp .env.example .env

```

3. **初始化数据库**
```bash
python -c "from models.database import init_db; init_db()"
```

4. **启动服务**
```bash
python main.py
或使用uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

5. **访问服务**
- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

## 🔧 配置说明

### 环境变量配置

创建 `.env` 文件并配置以下变量：

```env
 应用配置
APP_NAME=多智能体服装销售顾问
APP_VERSION=1.0.0
DEBUG=true
SECRET_KEY=your-secret-key

数据库配置
DATABASE_URL=sqlite:///./customer_service.db
或使用PostgreSQL
DATABASE_URL=postgresql://user:password@localhost/dbname

Redis配置
REDIS_URL=redis://localhost:6379/0

AI模型配置
OPENAI_API_KEY=your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1

日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

## 📚 API文档

### 主要接口

#### 对话接口
- `POST /api/chat/send` - 发送消息
- `GET /api/chat/sessions` - 获取会话列表
- `GET /api/chat/sessions/{session_id}` - 获取特定会话详情
- `WebSocket /api/chat/stream` - 实时对话
- `GET /api/chat/suggestions` - 获取对话建议

#### 智能体管理
- `GET /api/agents` - 获取智能体列表
- `GET /api/agents/{agent_id}` - 获取智能体详情
- `GET /api/agents/{agent_id}/stats` - 获取智能体性能统计
- `POST /api/agents/{agent_id}/restart` - 重启智能体

#### 会话管理
- `GET /api/sessions` - 获取所有会话
- `GET /api/sessions/{session_id}` - 获取会话详情
- `PUT /api/sessions/{session_id}` - 更新会话状态
- `DELETE /api/sessions/{session_id}` - 删除会话

#### 分析统计
- `GET /api/analytics/overview` - 获取概览数据
- `GET /api/analytics/performance` - 获取性能分析
- `GET /api/analytics/business` - 获取业务分析
- `GET /api/analytics/collaboration` - 获取协作分析

#### 产品管理
- `GET /api/products` - 获取产品列表
- `GET /api/products/{product_id}` - 获取产品详情
- `GET /api/products/search` - 搜索产品


## 📊 监控和日志

### 日志配置
系统使用 `loguru` 进行日志记录，支持：
- 结构化日志输出
- 日志轮转和压缩
- 多级别日志过滤
- 性能监控日志

### 性能监控
- Prometheus指标导出
- 系统资源监控
- 业务指标统计
- 告警规则配置




