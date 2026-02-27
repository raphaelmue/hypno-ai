import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig(async () => ({
  plugins: [react()],
  // Prevent vite from obscuring Rust errors
  clearScreen: false,
  // Tauri expects a fixed port; fail if it's not available
  server: {
    port: 1420,
    strictPort: true,
    watch: {
      // Ignore Rust files so only frontend changes trigger HMR
      ignored: ["**/src-tauri/**"],
    },
  },
}));
