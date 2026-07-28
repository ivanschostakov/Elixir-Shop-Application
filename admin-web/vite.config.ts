import { defineConfig, loadEnv } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "")
  const backendTarget = env.ADMIN_API_PROXY_TARGET || "http://127.0.0.1:8000"

  return {
    plugins: [react()],
    server: {
      host: "0.0.0.0",
      port: 4173,
      proxy: {
        "/api": {
          target: backendTarget,
          changeOrigin: true,
        },
        "/media": {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
    },
  }
})
