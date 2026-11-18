import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#1a141d",
          soft: "#5c535e",
          faint: "#756b77",
        },
        paper: "#fffdfb",
        surface: {
          DEFAULT: "#f7f2f5",
          blush: "#fcf4f8",
        },
        line: {
          DEFAULT: "#ebe0e6",
          soft: "#f4ecf1",
        },
        brand: {
          50: "#fcf4f8",
          100: "#fae6ef",
          200: "#f5c6da",
          300: "#ffb8ca",
          400: "#f17992",
          500: "#ed596f",
          600: "#bd346c",
          700: "#9c286f",
          800: "#7a1d57",
          900: "#511441",
        },
        plum: {
          DEFAULT: "#240c21",
          surface: "#32132e",
          soft: "#d7c7d1",
        },
      },
      boxShadow: {
        "mezer-sm": "0 2px 8px rgba(33, 15, 29, 0.04), 0 1px 2px rgba(33, 15, 29, 0.02)",
        card: "0 12px 32px -4px rgba(45, 16, 40, 0.06), 0 4px 12px -2px rgba(45, 16, 40, 0.03)",
        "card-hover":
          "0 20px 40px -4px rgba(45, 16, 40, 0.10), 0 8px 16px -2px rgba(45, 16, 40, 0.04)",
        brand: "0 10px 24px -6px rgba(156, 40, 111, 0.38)",
        phone:
          "0 32px 72px -16px rgba(29, 10, 26, 0.32), 0 16px 32px -8px rgba(29, 10, 26, 0.14)",
      },
      borderRadius: {
        "mezer-sm": "0.85rem",
        "mezer-md": "1.35rem",
        "mezer-lg": "2rem",
      },
    },
  },
  plugins: [],
};

export default config;
