/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  // FLASHCART_API_URL may come from the shell or a local .env file (never bundled: no VITE_ prefix).
  const env = loadEnv(mode, ".", "FLASHCART_");
  const apiTarget = env.FLASHCART_API_URL ?? "http://127.0.0.1:8000";

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      strictPort: true,
      // Same-origin in development (mirrors CloudFront in production), so no CORS and SameSite=Strict
      // refresh cookies work exactly as they will when deployed.
      proxy: {
        "/api": { target: apiTarget },
        "/healthz": { target: apiTarget },
      },
    },
    preview: { port: 4173, strictPort: true, proxy: { "/api": { target: apiTarget } } },
    build: {
      sourcemap: false,
      target: "es2022",
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      css: false,
    },
  };
});
