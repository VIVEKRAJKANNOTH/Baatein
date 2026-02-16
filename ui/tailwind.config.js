/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                indigo: {
                    950: '#0B1F3A',
                },
                teal: {
                    500: '#2A9D8F',
                },
                saffron: {
                    400: '#F4A261',
                },
                ivory: '#FAF7F0',
            },
            fontFamily: {
                sans: ['Inter', 'sans-serif'],
            },
        },
    },
    plugins: [],
}
