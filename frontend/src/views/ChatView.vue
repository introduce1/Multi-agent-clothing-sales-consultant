<template>
  <div class="chat-view">
    <!-- 顶部导航栏 -->
    <div class="top-navigation">
      <div class="nav-brand">
        <img src="../assets/customer-avatar.png" alt="小衣助手" class="nav-logo" />
        <span class="brand-name">小衣助手</span>
      </div>
      <div class="nav-menu">
        <router-link to="/" class="nav-item" :class="{ active: $route.path === '/' }">
          💬 智能客服
        </router-link>
      </div>
    </div>
    
    <!-- 主体聊天容器 -->
    <div class="chat-main-container">
      <!-- 左侧联系人列表 -->
      <div class="contacts-sidebar">
        <div class="sidebar-header">
          <h3>联系人</h3>
        </div>
        <div class="contact-list">
          <div class="contact-item active">
            <div class="contact-avatar">
              <img src="../assets/customer-avatar.png" alt="小衣助手" />
            </div>
            <div class="contact-info">
              <div class="contact-name">小衣助手</div>
              <div class="contact-status">
                <span v-if="connectionStatus === 'connected'">在线</span>
                <span v-else-if="connectionStatus === 'connecting'">连接中...</span>
                <span v-else>离线</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 右侧聊天区域 -->
      <div class="chat-main">
      <div class="chat-header">
        <div class="header-content">
          <div class="chat-title">
            <img src="../assets/customer-avatar.png" alt="小衣助手" class="header-avatar" />
            <div class="title-info">
              <h2>小衣助手 - 智能服装顾问</h2>
              <div class="status-text">
                <span v-if="connectionStatus === 'connected'" class="status-tag status-success">已连接</span>
                <span v-else-if="connectionStatus === 'connecting'" class="status-tag status-warning">连接中...</span>
                <span v-else class="status-tag status-danger">未连接</span>
                <span v-if="currentAgent" class="agent-tag">{{ getAgentDisplayName(currentAgent) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="messages-container" ref="messagesContainer">
        <div class="messages-list">
          <div 
            v-for="(message, index) in messages" 
            :key="index" 
            :class="['message-item', `message-${message.role}`]"
          >
            <div v-if="message.role === 'ai'" class="message-avatar">
              <img src="../assets/customer-avatar.png" alt="小衣助手" class="avatar-img" />
            </div>
            <div class="message-content">
              <div 
                :class="['message-bubble', { 'error': message.error }]"
                v-html="formatMessage(message.content)"
              ></div>
              <div class="message-time">{{ formatTime(message.timestamp) }}</div>
            </div>
            <div v-if="message.role === 'user'" class="message-avatar">
              <div class="avatar-img user-avatar"></div>
            </div>
          </div>
          
          <div v-if="isTyping" class="message-item message-ai">
            <div class="message-avatar">
              <img src="../assets/customer-avatar.png" alt="小衣助手" class="avatar-img" />
            </div>
            <div class="message-content">
              <div class="message-bubble">
                <div class="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="input-area">
        <div class="input-container">
          <form class="input-wrapper" @submit.prevent="sendMessage">
            <textarea
              v-model="userInput"
              placeholder="请输入您的问题..."
              class="message-input"
              rows="2"
              @keydown.enter.exact.prevent="handleEnterKey"
              @keydown.enter.shift.prevent="handleShiftEnter"
            ></textarea>
            <div class="input-actions">
              <button 
                type="submit" 
                class="send-button"
                aria-label="发送"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>
              </button>
            </div>
          </form>
        </div>
        
        <div class="quick-actions">
          <button class="action-button" @click="clearChat">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
            </svg>
            清空对话
          </button>
          <button v-if="connectionStatus !== 'connected'" class="action-button" @click="connectWebSocket">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
            </svg>
            重新连接
          </button>
        </div>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'

// 响应式数据
const userInput = ref('')
const messages = ref([])
const isTyping = ref(false)
const connectionStatus = ref('disconnected')
const messagesContainer = ref(null)
const ws = ref(null)
const sessionId = ref(null)
const currentAgent = ref(null)

// 计算属性
const isConnected = computed(() => connectionStatus.value === 'connected')
const canSendMessage = computed(() => {
  // 仅依据输入内容判断是否可发送，避免 isTyping 异常导致按钮不可用
  return userInput.value.trim().length > 0
})

// 智能体名称映射
const getAgentDisplayName = (agentId) => {
  const agentNames = {
    'reception_agent': '🏪 接待专员',
    'sales_agent': '🛍️ 销售顾问', 
    'order_agent': '📦 订单专员',
    'knowledge_agent': '📚 知识专家',
    'styling_agent': '👗 搭配师'
  }
  return agentNames[agentId] || agentId
}

// WebSocket连接
const connectWebSocket = () => {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    return
  }
  
  connectionStatus.value = 'connecting'
  // 使用相对路径，让Vite代理处理WebSocket连接
  const wsUrl = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsHost = window.location.host
  ws.value = new WebSocket(`${wsUrl}//${wsHost}/ws`)
  
  ws.value.onopen = () => {
    connectionStatus.value = 'connected'
    // AI会主动介绍自己，不需要额外的系统消息
  }
  
  ws.value.onmessage = (event) => {
    isTyping.value = false
    const data = JSON.parse(event.data)
    
    // 更新sessionId
    if (data.session_id) {
      sessionId.value = data.session_id
    }
    
    // 更新当前智能体信息
    if (data.current_agent) {
      currentAgent.value = data.current_agent
    }
    
    // 根据消息类型处理
    if (data.type === 'bot_response') {
      addMessage('ai', data.message)
    } else if (data.type === 'connection') {
      // 连接成功消息，不显示
    } else if (data.type === 'message_received') {
      // 消息接收确认，不显示
    } else if (data.type === 'error') {
      addMessage('system', data.message, true)
    } else {
      // 其他类型消息，显示为AI消息
      addMessage('ai', data.message || '收到未知类型消息')
    }
  }
  
  ws.value.onclose = () => {
    connectionStatus.value = 'disconnected'
    addMessage('system', '连接已断开', true)
  }
  
  ws.value.onerror = (error) => {
    connectionStatus.value = 'disconnected'
    addMessage('system', '连接错误，请重试', true)
  }
}

// 添加消息
const addMessage = (role, content, error = false) => {
  messages.value.push({
    role,
    content: content || '', // 确保content不为undefined
    timestamp: new Date(),
    error
  })
  scrollToBottom()
}

// 发送消息
const sendMessage = () => {
  const message = userInput.value.trim()
  
  // 检查消息是否为空
  if (!message) {
    return
  }
  
  // 添加用户消息并清空输入框
  addMessage('user', message)
  userInput.value = ''
  
  // 如果WebSocket连接正常，发送到服务器
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    // 发送正确格式的消息，包含type字段
    ws.value.send(JSON.stringify({ 
      type: 'message',
      message: message,
      session_id: sessionId.value || null
    }))
    isTyping.value = true
  } else {
    // 如果没有连接，显示模拟回复
    isTyping.value = true
    setTimeout(() => {
      isTyping.value = false
      addMessage('ai', '您好！我是小衣助手。由于服务器未连接，这是一个模拟回复。请启动后端服务器以获得完整功能。')
    }, 600)
  }
}

// 处理Enter键
const handleEnterKey = () => {
  sendMessage()
}

// 处理Shift+Enter键
const handleShiftEnter = () => {
  userInput.value += '\n'
}

// 清空对话
const clearChat = () => {
  messages.value = []
}

// 格式化消息
// 先清理 Markdown 里的 emoji 和多余括号，还原成标准 [text](url)
const cleanMarkdownLink = (text) => {
  // 将 [text](url) 或 [text](🔗 url) 转换为纯 url 文本；去掉所有括号与说明文字
  // 也处理全角括号样式（例如：（🔗 url））
  return text
    .replace(/\[([^\]]+)\]\(\s*(?:🔗\s*)?(https?:\/\/[^\s\)]+)\s*\)/g, '$2')
    .replace(/（\s*(?:🔗\s*)?(https?:\/\/[^\s\)]+)\s*）/g, '$1')
}

// 只把裸 URL 包成 <a>，文字/emoji 一律不包
const urlToLink = (text) => {
  return text.replace(
    /(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" class="external-link">$1</a>'
  )
}

// 统一入口：先清理 Markdown，再把裸 URL 转成可点链接
const formatMessage = (content) => {
  if (!content) return ''
  // 清理 Markdown 链接，只保留 URL
  let cleaned = cleanMarkdownLink(content)
  // 转换 URL 为可点击链接
  cleaned = urlToLink(cleaned)
  // 按连续空行分段（2 个及以上换行）
  const paragraphs = cleaned.split(/\n{2,}/)
  const html = paragraphs.map(p => `<div class="msg-para">${p.replace(/\n/g, '<br>')}</div>`).join('')
  return html
}

// 格式化时间
const formatTime = (timestamp) => {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 滚动到底部
const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 组件挂载时连接WebSocket
onMounted(() => {
  connectWebSocket()
})
</script>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f8f9fa;
}

/* 顶部导航栏样式 */
.top-navigation {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 12px 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  z-index: 100;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-logo {
  width: 32px;
  height: 32px;
  border-radius: 50%;
}

.brand-name {
  font-size: 1.2rem;
  font-weight: bold;
}

.nav-menu {
  display: flex;
  gap: 20px;
}

.nav-item {
  color: white;
  text-decoration: none;
  padding: 8px 16px;
  border-radius: 20px;
  transition: all 0.3s ease;
  font-size: 14px;
  font-weight: 500;
}

.nav-item:hover {
  background: rgba(255,255,255,0.2);
  color: white;
}

.nav-item.active {
  background: rgba(255,255,255,0.3);
  color: white;
}

/* 主体布局调整 */
.chat-main-container {
  display: flex;
  flex: 1;
  overflow: hidden; /* 只在容器层隐藏横向溢出 */
  min-width: 0;     /* 允许子项在横向上收缩 */
}

.chat-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f8f9fa;
}

/* 左侧联系人列表 */
.contacts-sidebar {
  width: 280px;
  flex: 0 0 280px;   /* 固定侧栏宽度，不参与收缩 */
  background: #2e3238;
  border-right: 1px solid #3a3f45;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 20px 16px;
  background: #2a2d33;
  border-bottom: 1px solid #3a3f45;
}

.sidebar-header h3 {
  color: #ffffff;
  font-size: 16px;
  font-weight: 500;
  margin: 0;
}

.contact-list {
  flex: 1;
  overflow-y: auto;
}

.contact-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.contact-item:hover {
  background: #3a3f45;
}

.contact-item.active {
  background: #4a90e2;
}

.contact-avatar {
  margin-right: 12px;
}

.contact-avatar img {
  width: 40px;
  height: 40px;
  border-radius: 50%;
}

.contact-info {
  flex: 1;
}

.contact-name {
  color: #ffffff;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
}

.contact-status {
  color: #9ca3af;
  font-size: 12px;
}

/* 右侧聊天区域 */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  /* 允许在父级 flex 中正确收缩，避免被左侧固定宽度挤出视口 */
  min-width: 0;
}

.chat-header {
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  padding: 16px 20px;
}

.header-content {
  display: flex;
  align-items: center;
}

.chat-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
}

.title-info h2 {
  font-size: 16px;
  font-weight: 500;
  margin: 0 0 4px 0;
  color: #1f2937;
}

.status-text {
  font-size: 12px;
}

.status-tag {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
}

.status-success {
  background: #f0f9ff;
  color: #059669;
  border: 1px solid #a7f3d0;
}

.status-warning {
  background: #fffbeb;
  color: #d97706;
  border: 1px solid #fde68a;
}

.status-danger {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}

.agent-tag {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  background: #e0f2fe;
  color: #0277bd;
  margin-left: 8px;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden; /* 禁止横向滚动，避免内容把右侧挤出 */
  padding: 16px 20px;
  background: #f9fafb;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-item {
  display: flex;
  gap: 12px;
  max-width: 80%;
}

.message-user {
  flex-direction: row-reverse;
  align-self: flex-end;
}

.message-ai {
  align-self: flex-start;
}

.message-avatar {
  flex-shrink: 0;
}

.avatar-img {
  width: 36px;
  height: 36px;
  border-radius: 50%;
}

.user-avatar {
  background-image: url('@/assets/user-avatar.png');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.message-user .message-content {
  align-items: flex-end;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 18px;
  word-wrap: break-word;
  line-height: 1.5;
  max-width: 100%;
  position: relative;
}

/* 段落卡片化 */
.msg-para {
  margin: 8px 0;
}
.msg-para:first-child { margin-top: 0; }
.msg-para:last-child  { margin-bottom: 0; }

.message-user .message-bubble {
  background: #4a90e2;
  color: white;
  border-bottom-right-radius: 6px;
}

.message-ai .message-bubble {
  background: white;
  border: 1px solid #e5e7eb;
  color: #374151;
  border-bottom-left-radius: 6px;
}

.message-system .message-bubble {
  background: #fef3c7;
  border: 1px solid #f59e0b;
  color: #92400e;
}

.message-bubble.error {
  background: #fee2e2;
  border: 1px solid #f87171;
  color: #dc2626;
}

.message-time {
  font-size: 11px;
  color: #9ca3af;
  padding: 0 4px;
}

.input-area {
  background: white;
  border-top: 1px solid #e5e7eb;
  padding: 16px 20px;
}

.input-container {
  margin-bottom: 12px;
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px 12px;
}

.message-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  padding: 8px 0;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  font-family: inherit;
}

.message-input:disabled {
  background: #f5f5f5;
  color: #999;
}

.send-button {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: #4a90e2;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
  pointer-events: auto;
  z-index: 2;
}

.send-button:hover:not(:disabled) {
  background: #357abd;
}

.send-button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.action-button {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  border-radius: 6px;
  font-size: 14px;
  transition: color 0.2s, background-color 0.2s;
}

.action-button:hover {
  color: #4a90e2;
  background: #f3f4f6;
}

.input-actions {
  display: flex;
  align-items: center;
}

.quick-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.quick-actions .el-button {
  color: #6b7280;
}

.quick-actions .el-button:hover {
  color: #4a90e2;
}

/* 产品推荐样式 */
.product-link {
  color: #4a90e2;
  text-decoration: none;
  font-weight: 500;
  padding: 4px 8px;
  background: rgba(74, 144, 226, 0.1);
  border-radius: 12px;
  display: inline-block;
  margin: 2px;
  transition: all 0.3s ease;
}

.product-link:hover {
  background: rgba(74, 144, 226, 0.2);
  color: #2563eb;
}

.product-card {
  display: flex;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  margin: 8px 0;
  padding: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  max-width: 300px;
}

.product-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
  transform: translateY(-2px);
}

.product-image {
  width: 80px;
  height: 80px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
}

.product-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.product-info {
  flex: 1;
  margin-left: 12px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.product-name {
  font-weight: 600;
  color: #1f2937;
  font-size: 14px;
  margin-bottom: 4px;
}

.product-price {
  color: #ef4444;
  font-weight: bold;
  font-size: 16px;
  margin-bottom: 4px;
}

.product-action {
  color: #6b7280;
  font-size: 12px;
}

/* 淘宝产品卡片特殊样式 */
.product-card.taobao-product {
  border: 2px solid #ff6900;
  background: linear-gradient(135deg, #fff 0%, #fff5f0 100%);
}

.product-card.taobao-product:hover {
  border-color: #ff4500;
  box-shadow: 0 4px 16px rgba(255, 105, 0, 0.2);
}

.taobao-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  background: #ff6900;
  color: white;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 8px;
  font-weight: bold;
}

.product-image {
  position: relative;
}

/* 外部链接样式 */
.external-link {
  color: #3b82f6;
  text-decoration: none;
  padding: 4px 8px;
  border-radius: 6px;
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.2);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  transition: all 0.2s ease;
  word-break: break-all;
  max-width: 100%;
}

.external-link:hover {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.3);
  text-decoration: none;
  transform: translateY(-1px);
}

.external-link:active {
  transform: translateY(0);
}

.typing-indicator {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: 4px 0;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #9ca3af;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(1) {
  animation-delay: -0.32s;
}

.typing-indicator span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .contacts-sidebar {
    width: 240px;
  }
  
  .message-item {
    max-width: 90%;
  }
  
  .chat-header {
    padding: 12px 16px;
  }
  
  .messages-container {
    padding: 12px 16px;
  }
  
  .input-area {
    padding: 12px 16px;
  }
}

@media (max-width: 640px) {
  .contacts-sidebar {
    display: none;
  }
  
  .chat-view {
    flex-direction: column;
  }
}
</style>