import typography from "@tailwindcss/typography";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // SanadAI brand: professional navy with a gold accent.
        navy: { DEFAULT: "#1E3A8A", deep: "#15306B", tint: "#EEF2FB" },
        gold: "#C99A2E",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [typography],
};
