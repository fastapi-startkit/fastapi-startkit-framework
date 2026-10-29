import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import fastapi from 'fastapi-vite-plugin'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
    plugins: [
        fastapi({ input: 'resources/js/app.ts', refresh: true }),
        vue(),
        tailwindcss(),
    ],
})
