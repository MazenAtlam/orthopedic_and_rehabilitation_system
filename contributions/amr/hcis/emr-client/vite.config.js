import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const proxy = {
  '/api': {
    target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:5000',
    changeOrigin: false,
  },
};

export default defineConfig({
  plugins: [react()],
  preview: { proxy },
  server: {
    proxy,
    host: true,
    port: 5174,
    strictPort: true,
    watch: { usePolling: process.env.CHOKIDAR_USEPOLLING === 'true' },
  },
});
