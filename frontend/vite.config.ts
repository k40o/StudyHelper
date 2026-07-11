import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `base: "./"` makes the built asset paths relative, so FastAPI can serve the
// dist/ folder from any mount point. In dev, /api is proxied to the backend.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    port: 5173,
    host: true, // expose on LAN so an iPad can reach the dev server too
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
