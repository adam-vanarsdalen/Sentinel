/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        sentinel: {
          purple: '#7C3AED',
          'purple-light': '#A78BFA',
          dark: '#0F0F1A',
          panel: '#1A1A2E',
          border: '#2D2D4A',
        },
      },
    },
  },
  plugins: [],
}
