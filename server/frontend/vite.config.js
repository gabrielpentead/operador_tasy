import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

/**
 * O build sai para ../static/app/ e o Flask serve esse diretório em /app.
 * Isso mantém UM único serviço em produção: continua sendo "python run.py".
 * A rota / (Jinja) segue intacta até a virada de chave.
 */
export default defineConfig({
  plugins: [react()],
  base: '/static/app/',
  build: {
    outDir: path.resolve(__dirname, '../static/app'),
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5173,
    // Em desenvolvimento, encaminha API e WebSocket para o Flask
    proxy: {
      '/api': { target: 'http://localhost:5000', changeOrigin: true },
      '/socket.io': { target: 'http://localhost:5000', ws: true, changeOrigin: true },
    },
  },
})
