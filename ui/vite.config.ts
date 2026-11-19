import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: { dedupe: ['react', 'react-dom'] },
  server: {
    port: Number(process.env.PND_UI_PORT || 3000),
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${process.env.PND_API_PORT || 8000}`,
        changeOrigin: true,
        ws: true,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            // Suppress ECONNABORTED — fires when a browser tab closes mid-proxy
            if ((err as NodeJS.ErrnoException).code === 'ECONNABORTED') return
            console.error('[proxy]', err.message)
          })
        },
      },
    },
  },
})
