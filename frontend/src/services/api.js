import axios from 'axios'

// 创建axios实例
const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  config => {
    console.log('发送请求:', config)
    return config
  },
  error => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    console.log('收到响应:', response)
    return response
  },
  error => {
    console.error('响应错误:', error)
    return Promise.reject(error)
  }
)

// API方法
export const chatAPI = {
  // 发送聊天消息
  sendMessage: async (message, sessionId = null) => {
    try {
      const response = await api.post('/chat/', {
        message: message,
        session_id: sessionId
      })
      return response.data
    } catch (error) {
      console.error('发送消息失败:', error)
      throw error
    }
  },

  // 获取系统信息
  getSystemInfo: async () => {
    try {
      const response = await api.get('/')
      return response.data
    } catch (error) {
      console.error('获取系统信息失败:', error)
      throw error
    }
  },

  // 健康检查
  healthCheck: async () => {
    try {
      const response = await api.get('/health')
      return response.data
    } catch (error) {
      console.error('健康检查失败:', error)
      throw error
    }
  }
}

export default api