/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0F1117',
        card: '#1A1D27',
        accent: '#6C63FF',
        success: '#00C896',
        warning: '#FFB800',
        danger: '#FF4757',
        border: '#2A2D3E',
      },
    },
  },
  plugins: [],
}
