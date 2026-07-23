import fastapi from "fastapi-vite-plugin"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
    plugins: [
        fastapi({
            input: "resources/js/app.tsx",
            refresh: true,
        }),
        react(),
        tailwindcss()
    ],
})
