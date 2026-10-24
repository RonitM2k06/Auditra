/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Warm neutral "ink on paper" scale used for all structural UI.
        ink: {
          50: '#F9FAFB',
          100: '#F2F5F8',
          200: '#E4E7EC',
          300: '#D0D5DD',
          400: '#98A2B3',
          500: '#667085',
          600: '#475467',
          700: '#344054',
          800: '#1D2939',
          900: '#172033',
        },
        line: '#E4E7EC',
        paper: '#F6F8FB',
        navy: { 700: '#22324a', 800: '#162235', 900: '#111C2E', 950: '#111827' },
        // Single accent, reserved for approval / positive outcomes.
        pine: {
          50: '#E8F7F4',
          100: '#CCEFE8',
          200: '#99DCD1',
          500: '#0F9488',
          600: '#0F9488',
          700: '#0B7D73',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', '"Segoe UI"', 'Roboto', 'sans-serif'],
        serif: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', '"SF Mono"', '"Cascadia Code"', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
