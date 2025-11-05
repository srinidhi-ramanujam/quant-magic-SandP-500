/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#4338ca",
          light: "#6366f1",
          dark: "#312e81",
        },
      },
    },
  },
  plugins: [],
};
