import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        ink: '#0a0a0a',
        paper: '#f8f8f8',
        fog: '#e8e8e8',
      },
      boxShadow: {
        frame: '0 0 0 1px #111, 0 12px 30px rgba(0,0,0,0.08)',
      },
      animation: {
        drift: 'drift 8s linear infinite',
      },
      keyframes: {
        drift: {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(40px)' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
