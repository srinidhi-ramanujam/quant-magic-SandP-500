/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#6366f1", // indigo-500 - softer, more professional
          light: "#818cf8",   // indigo-400
          dark: "#4f46e5",    // indigo-600
        },
        chat: {
          user: {
            from: "#4f46e5",  // indigo-600 gradient start
            to: "#3b82f6",    // blue-500 gradient end
          },
          response: {
            bg: "#1e293b",    // slate-800
            accent: "#6366f1", // indigo-500 - matches brand
          },
        },
      },
    },
  },
  plugins: [],
};
