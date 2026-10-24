/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Warm neutral "ink on paper" scale used for all structural UI.
        ink: {
          50: '#f7f6f4',
          100: '#efede9',
          200: '#e2dfd9',
          300: '#cbc7bf',
          400: '#a19c92',
          500: '#77726a',
          600: '#5a564f',
          700: '#403d38',
          800: '#2a2825',
          900: '#1b1a18',
        },
        line: '#e6e3dd',
        paper: '#fbfaf8',
        // Single accent, reserved for approval / positive outcomes.
        pine: {
          50: '#eef5f1',
          100: '#d6e8dd',
          200: '#b0d2bf',
          500: '#2f7a5b',
          600: '#266650',
          700: '#1d4f3e',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', '"Segoe UI"', 'Roboto', 'sans-serif'],
        serif: ['"Source Serif 4"', '"Source Serif Pro"', '"Iowan Old Style"', 'Charter', '"Palatino Linotype"', 'Georgia', 'serif'],
        mono: ['ui-monospace', '"SF Mono"', '"Cascadia Code"', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
