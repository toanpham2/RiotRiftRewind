/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx,js,jsx}"],
  theme: {
    extend: {
      colors: {
        lolBg: "#0b0f13",
        lolCard: "#0f1419",
        lolBlue: "#18a0fb",
        lolBlueDeep: "#2237a7",
        lolGold: "#c9a86a",
      },
      boxShadow: {
        lolOuter: "0 0 20px rgba(201,168,106,.25)",
        lolInset: "inset 0 0 10px rgba(201,168,106,.15)",
      },
      fontFamily: {
        display: ['"Cinzel"', "serif"],
        ui: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
