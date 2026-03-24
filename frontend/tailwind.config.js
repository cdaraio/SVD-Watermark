/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
      },
      colors: {
        // Cyber-security accent — neon green
        cyber: "#00FF66",
        "cyber-dim": "rgba(0,255,102,0.12)",
        // Ultra-dark panel surfaces
        panel: "#0A0A0A",
        "panel-border": "#1F1F1F",
        "panel-hover": "#111111",
      },
      boxShadow: {
        // Neon green glow for primary action buttons
        cyber:    "0 0 18px rgba(0,255,102,0.45), 0 0 40px rgba(0,255,102,0.12)",
        "cyber-sm": "0 0 8px rgba(0,255,102,0.3)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in": {
          from: { opacity: "0", transform: "translateX(-8px)" },
          to:   { opacity: "1", transform: "translateX(0)" },
        },
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 6px rgba(0,255,102,0.2)"  },
          "50%":       { boxShadow: "0 0 22px rgba(0,255,102,0.55)" },
        },
      },
      animation: {
        "fade-in":    "fade-in 0.3s ease both",
        "slide-in":   "slide-in 0.25s ease both",
        "pulse-glow": "pulse-glow 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
