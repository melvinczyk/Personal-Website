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
    require("daisyui"),
    require('@tailwindcss/forms'),
    require('@tailwindcss/aspect-ratio'),
    require('@tailwindcss/typography'),
    require('@tailwindcss/container-queries')
  ],

  daisyui: {
    themes: [
        "forest"
    ],
  },
}

