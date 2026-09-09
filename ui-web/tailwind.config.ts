import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        sovereign: {
          bg: '#0B0F14',
          card: '#11161D',
          card2: '#161D26',
          card3: '#1E2630',
          text: '#E6EDF3',
          muted: '#8B949E',
          success: '#10B981',
          warning: '#F59E0B',
          error: '#EF4444',
          info: '#22D3EE',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderColor: {
        hairline: 'rgba(255, 255, 255, 0.1)',
      },
    },
  },
  plugins: [],
} satisfies Config;
