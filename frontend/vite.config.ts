import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// https://vitejs.dev/config/
// The API target is configurable via env var VITE_API_TARGET.
// - In local dev (outside Docker): defaults to "http://localhost:8000"
// - Inside Docker Compose: set VITE_API_TARGET=http://backend:8000
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_TARGET || "http://localhost:8000";

  const apiRoutes = [
    "/status",
    "/health",
    "/discovery",
    "/contracts",
    "/registry",
    "/foundry",
    "/memory",
    "/mold-factory",
    "/agents",
    "/foresight",
    "/publishing",
  ];

  const proxyConfig: Record<string, string> = {};
  for (const route of apiRoutes) {
    proxyConfig[route] = apiTarget;
  }

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      port: 5173,
      host: "0.0.0.0",
      proxy: proxyConfig,
    },
  };
});
