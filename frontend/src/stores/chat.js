import { defineStore } from 'pinia'
import { chatAPI } from '../services/api'

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [],
    currentSessionId: null,
    isLoading: false,
    isConnected: false,
    systemInfo: null
  }),

  getters: {
    // 获取当前会话的消息
    currentMessages: (state) => state.messages,
    
    // 检查是否正在加载
    loading: (state) => state.isLoading,
    
    // 检查连接状态
    connected: (state) => state.isConnected
  },

  actions: {
    // 发送消息
    async sendMessage(content) {
      if (!content.trim()) return

      // 添加用户消息到列表
      const userMessage = {
        id: Date.now(),
        content: content,
        sender: 'user',
        timestamp: new Date().toLocaleTimeString(),
        type: 'text'
      }
      this.messages.push(userMessage)

      this.isLoading = true

      try {
        // 调用API发送消息
        const response = await chatAPI.sendMessage(content, this.currentSessionId)
        
        // 更新会话ID
        if (response.session_id) {
          this.currentSessionId = response.session_id
        }

        // 添加AI回复到消息列表
        const aiMessage = {
          id: response.message_id || Date.now() + 1,
          content: response.response || '抱歉，我暂时无法回复',
          sender: 'ai',
          timestamp: new Date().toLocaleTimeString(),
          type: 'text'
        }
        this.messages.push(aiMessage)

      } catch (error) {
        console.error('发送消息失败:', error)
        
        // 添加错误消息
        const errorMessage = {
          id: Date.now() + 1,
          content: '抱歉，消息发送失败，请稍后重试',
          sender: 'system',
          timestamp: new Date().toLocaleTimeString(),
          type: 'error'
        }
        this.messages.push(errorMessage)
      } finally {
        this.isLoading = false
      }
    },

    // 清空聊天记录
    clearMessages() {
      this.messages = []
      this.currentSessionId = null
    },

    // 检查系统连接状态
    async checkConnection() {
      try {
        await chatAPI.healthCheck()
        this.isConnected = true
      } catch (error) {
        this.isConnected = false
        console.error('连接检查失败:', error)
      }
    },

    // 获取系统信息
    async getSystemInfo() {
      try {
        const info = await chatAPI.getSystemInfo()
        this.systemInfo = info
        this.isConnected = true
      } catch (error) {
        console.error('获取系统信息失败:', error)
        this.isConnected = false
      }
    },

    // 初始化聊天
    async initChat() {
      await this.checkConnection()
      await this.getSystemInfo()
      
      // 添加欢迎消息
      if (this.isConnected) {
        const welcomeMessage = {
          id: 'welcome',
          content: '您好！我是小衣助手，有什么可以帮助您的吗？',
          sender: 'ai',
          timestamp: new Date().toLocaleTimeString(),
          type: 'text'
        }
        this.messages.push(welcomeMessage)
      }
    }
  }
})