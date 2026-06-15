import type { Config } from "tailwindcss";

// 色板来自 ui-ux-pro-max「Data-Dense Dashboard」设计系统
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#1E40AF", fg: "#FFFFFF" },
        secondary: "#3B82F6",
        accent: "#D97706",
        background: "#F8FAFC",
        foreground: "#1E3A8A",
        muted: "#E9EEF6",
        border: "#DBEAFE",
        destructive: "#DC2626",
        success: "#15803D",
        warning: "#B45309",
        surface: "#FFFFFF",
      },
      fontFamily: {
        sans: ["Fira Sans", "system-ui", "sans-serif"],
        mono: ["Fira Code", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(30,64,175,0.06), 0 1px 3px rgba(30,64,175,0.10)",
      },
      borderRadius: { xl: "0.875rem" },
    },
  },
  plugins: [],
};

export default config;
