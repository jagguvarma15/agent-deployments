import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on :3000 (the container/sandbox frontend port). The production
// build is static and served by nginx (see Dockerfile) — also on :3000.
export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 3000 },
  preview: { host: true, port: 3000 },
});
