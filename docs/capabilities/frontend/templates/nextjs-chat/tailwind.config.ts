import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        agent: {
          bubble: "#1f2937",
          user: "#2563eb",
        },
      },
    },
  },
  plugins: [],
};

export default config;
