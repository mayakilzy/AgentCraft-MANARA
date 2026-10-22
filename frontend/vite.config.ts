import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // MANARA-UI-PAGE02-PRE-ACCEPTANCE-01: use 127.0.0.1 (not localhost) for
  // the dev proxy target — some dev environments resolve localhost to IPv6
  // ::1 first, while the dev backend only listens on IPv4. Setting
  // VITE_API_TARGET overrides this for non-default backend hosts.
  const apiTarget = env.VITE_API_TARGET || "http://127.0.0.1:8000";

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

  // Vite proxy expects an object with `target`, not a bare string
  const proxyConfig: Record<string, { target: string; changeOrigin: boolean }> = {};
  for (const route of apiRoutes) {
    proxyConfig[route] = { target: apiTarget, changeOrigin: true };
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
