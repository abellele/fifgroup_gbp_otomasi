/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./gbp/templates/**/*.html",
    "./gbp/static/gbp/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#084C75",
          50:  "#f1f6f9",
          100: "#e1ecf2",
          200: "#bed6e3",
          300: "#8ebbd0",
          400: "#579bb9",
          500: "#3680a1",
          600: "#296685",
          700: "#22536d",
          800: "#084C75",
          900: "#173b4d",
        },
        accent: {
          DEFAULT: "#F4D03F",
          50:  "#fefbea",
          100: "#fef4c5",
          200: "#fde88a",
          300: "#fcd44d",
          400: "#F4D03F",
          500: "#eab308",
          600: "#ca8a04",
          700: "#a16207",
          800: "#854d0e",
          900: "#713f12",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Outfit", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      boxShadow: {
        "card": "0 2px 10px -2px rgb(0 0 0 / 0.05), 0 4px 6px -4px rgb(0 0 0 / 0.05)",
        "card-hover": "0 10px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)",
        "glass": "0 8px 32px 0 rgba(0, 0, 0, 0.05)",
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease-out forwards",
        "slide-up": "slideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        fadeIn: { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        slideUp: { "0%": { opacity: "0", transform: "translateY(12px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
      },
    },
  },
  plugins: [],
}
