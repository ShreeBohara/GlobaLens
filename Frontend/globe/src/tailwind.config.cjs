// tailwind.config.js
module.exports = {
  // ...
  theme: {
    extend: {
      colors: {
        neon: '#39FF14', // Or your specific neon hex code
      },
      // If you want to use it with ring or other utilities
      ringColor: theme => ({
        ...theme('colors'), // inherit default ring colors
        'neon': '#39FF14', // your neon color
      }),
      // To make it available for borders, it should work if defined in 'colors'
      // but sometimes specificity or configuration for variants is needed.
    },
  },
  // ...
};