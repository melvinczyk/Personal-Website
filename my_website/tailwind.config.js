/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
      './templates/**/*.html'
  ],
  theme: {
    extend: {
        backgroundImage: {
            'radial-gradient': 'radial-gradient(circle, #00ff00, #000000)'
        },
    },
  },
  plugins: [
  require("daisyui")
  ],

  daisyui: {
    themes: [
        "forest"
    ],
  },
}

