/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        altitude: "#E8EFF7",
        navy: "#0A1B3D",
        "navy-soft": "#16306B",
        steel: "#5A6A85",
        signal: "#FFC629",
        mist: "#C9D6E6",
        alert: "#B8301F",
        ok: "#1F7A52",
      },
      fontFamily: {
        display: ['"Archivo"', '"Arial Narrow"', "Arial", "sans-serif"],
        sans: ['"Public Sans"', "system-ui", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};