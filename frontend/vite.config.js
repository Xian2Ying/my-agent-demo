import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // 把 /api 请求转发到 Python 后端，前端代码里直接 fetch('/api/chat') 即可
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
