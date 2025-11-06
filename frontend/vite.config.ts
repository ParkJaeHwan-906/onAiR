import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "https://onair.ai.kr", // 백엔드 서버 주소
        changeOrigin: true,
        secure: true, // HTTPS라면 true
      },
    },
  },
});
