/** @type {import('tailwindcss').Config} */
module.exports = {
  // Классы берутся только из шаблонов: динамических имён классов в JS нет,
  // поэтому purge по этому пути безопасен и даёт минимальный CSS.
  content: ["./templates/**/*.html"],
  darkMode: "class",
  theme: {
    extend: {
      // Совпадает с дизайн-канвасом «Автокредит — публичный сайт» (Task 1) и
      // с app/tailwind.config.js в CRM — единый визуальный язык платформы.
      colors: {
        darkbg: "#0F172A",
        cardbg: "#1E293B",
      },
    },
  },
  plugins: [],
};
