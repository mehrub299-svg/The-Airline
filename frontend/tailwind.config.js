const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Theme-aware tokens: values live as CSS variables in src/index.css
        page: token("page"),
        surface: token("surface"),
        ink: token("ink"),
        muted: token("muted"),
        line: token("line"),
        brand: token("brand"),
        "brand-hover": token("brand-hover"),
        onbrand: token("onbrand"),
        signal: token("signal"),
        alert: token("alert"),
        ok: token("ok"),

        // Legacy tokens: still used by the current workspace screens until the assembly step
        altitude: "#E8EFF7",
        navy: "#0A1B3D",
        "navy-soft": "#16306B",
        steel: "#5A6A85",
        mist: "#C9D6E6",
      },
      fontFamily: {
        display: ['"Archivo"', '"Arial Narrow"', "Arial", "sans-serif"],
        sans: ['"Public Sans"', "system-ui", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};