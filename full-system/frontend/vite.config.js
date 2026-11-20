import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// The browser only ever talks to this server. Requests to /api are forwarded to
// the FastAPI backend, which stays private on 127.0.0.1. No secrets (HF_TOKEN,
// GROQ_API_KEY, JWT_SECRET) ever live in frontend code.
const apiProxy = {
  "/api": {
    target: process.env.VITE_BACKEND_URL || "http://127.0.0.1:8000",
    changeOrigin: true,
    xfwd: true, // pass the visitor's IP (X-Forwarded-For) so audit logs show the real device
    rewrite: (path) => path.replace(/^\/api/, ""),
  },
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    strictPort: true,
    proxy: apiProxy,
  },
  // `npm run serve` (production build) — used for sharing on the local network.
  preview: {
    host: true, // listen on all network interfaces so other devices on the Wi-Fi can connect
    port: 5174,
    strictPort: true,
    // IP addresses are always allowed; also allow <name>.local (Wi-Fi) and the tunnel domains: Cloudflare quick
    // tunnels, and localhost.run (used on networks that block Cloudflare, e.g. some campus Wi-Fi).
    allowedHosts: [".local", ".trycloudflare.com", ".lhr.life"],
    proxy: apiProxy,
  },
});
