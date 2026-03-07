/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // HypnoAI dark theme — deep blues and muted grays (§14.5)
        surface: {
          50: "#f0f4f8",
          100: "#d9e2ec",
          200: "#bcccdc",
          300: "#9fb3c8",
          400: "#829ab1",
          500: "#627d98",
          600: "#486581",
          700: "#334e68",
          800: "#243b53",
          900: "#102a43",
          950: "#0a1f33",
        },
        accent: {
          DEFAULT: "#7eb5e8",
          hover: "#9dc8f0",
          muted: "#4a7fa8",
        },
        warm: {
          DEFAULT: "#c9a86c",
          muted: "#8a6d3f",
        },
        success: "#68d391",
        warning: "#f6e05e",
        danger: "#fc8181",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
