import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: "0.0.0.0",
    proxy: {
      "/status": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/discovery": "http://localhost:8000",
      "/contracts": "http://localhost:8000",
      "/registry": "http://localhost:8000",
      "/foundry": "http://localhost:8000",
      "/memory": "http://localhost:8000",
      "/mold-factory": "http://localhost:8000",
      "/agents": "http://localhost:8000",
      "/foresight": "http://localhost:8000",
      "/publishing": "http://localhost:8000",
    },
  },
});
