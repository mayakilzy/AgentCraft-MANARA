/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'manara-canvas': '#F7F8F6',
        'manara-ink': '#19334A',
        'manara-teal': '#2C7380',
        'manara-brass': '#BB9362',
        'manara-mist': '#E8EFF1',
      },
    },
  },
  plugins: [],
};
