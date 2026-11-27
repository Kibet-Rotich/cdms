import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies API calls to Django, so the browser sees one origin (no CORS setup needed).
const target = process.env.VITE_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target, changeOrigin: true },
      "/fhir": { target, changeOrigin: true },
      "/admin": { target, changeOrigin: true },
      "/static": { target, changeOrigin: true },
    },
  },
});
