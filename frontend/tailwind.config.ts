import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f4fa",
          100: "#dbe5f3",
          200: "#bacfe8",
          300: "#8eb1db",
          400: "#5b8eca",
          500: "#3770b7",
          600: "#275798",
          700: "#1f447a",
          800: "#1b3964",
          900: "#183053",
          950: "#0b1220",
        },
        navy: {
          850: "#131d33",
          900: "#0f172a",
          950: "#0b111e",
        },
        compliance: {
          satisfied: {
            bg: "#ecfdf5",
            border: "#a7f3d0",
            text: "#065f46",
            accent: "#10b981",
          },
          violation: {
            bg: "#fef2f2",
            border: "#fecaca",
            text: "#991b1b",
            accent: "#ef4444",
          },
          notverified: {
            bg: "#fffbeb",
            border: "#fde68a",
            text: "#92400e",
            accent: "#f59e0b",
          },
          conflict: {
            bg: "#f5f3ff",
            border: "#ddd6fe",
            text: "#5b21b6",
            accent: "#8b5cf6",
          },
        },
      },
      boxShadow: {
        subtle: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
        card: "0 1px 3px 0 rgba(0, 0, 0, 0.08), 0 1px 2px -1px rgba(0, 0, 0, 0.08)",
        "card-hover": "0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04)",
        dropdown: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
