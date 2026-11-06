import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api/* is forwarded to the FastAPI backend, so the browser never needs CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
