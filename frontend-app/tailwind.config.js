/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#071a33",
        electric: "#315efb",
        mist: "#f5f7fb",
        line: "#e4eaf3",
      },
      boxShadow: {
        soft: "0 18px 50px rgba(7, 26, 51, 0.10)",
      },
      keyframes: {
        "fade-up": { from: { opacity: "0", transform: "translateY(12px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
      animation: { "fade-up": "fade-up 500ms ease-out both" },
    },
  },
  plugins: [],
};
