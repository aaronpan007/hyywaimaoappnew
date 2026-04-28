import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          blue: "#2563EB",
          "blue-light": "#EFF6FF",
          "blue-hover": "#1D4ED8",
        },
        surface: {
          white: "#FFFFFF",
          "side-bg": "#F7F7F8",
          "msg-user": "#F0F0F0",
          "input-bg": "#EEEEEE",
        },
        text: {
          primary: "#1A1A2E",
          secondary: "#6B7280",
          tertiary: "#9CA3AF",
          border: "#E5E7EB",
        },
      },
      fontFamily: {
        system: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "sans-serif",
        ],
      },
      width: {
        sidebar: "220px",
      },
    },
  },
  plugins: [],
};

export default config;
