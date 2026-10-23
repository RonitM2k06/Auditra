/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eefcf9',
          100: '#d5f7f0',
          200: '#aef0e2',
          300: '#75e3d0',
          400: '#38ceb9',
          500: '#0F9D91',
          600: '#0B7C72',
          700: '#0c645d',
          800: '#0e504a',
          900: '#10433e',
        },
        navy: {
          950: '#0a0f1d',
          900: '#101B2D',
          850: '#152238',
          800: '#1a2b47',
          700: '#263b5e',
        },
        surface: {
          base: '#F6F8FB',
          card: '#FFFFFF',
          muted: '#F1F4F9',
          border: '#E4E7EC',
        },
        dark: {
          primary: '#111827',
          secondary: '#182230',
          muted: '#667085',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
