import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:5001',   // localhost 는 Windows 에서 IPv6 를 먼저 시도해 요청마다 0.2초 늦다
    },
  },
})
