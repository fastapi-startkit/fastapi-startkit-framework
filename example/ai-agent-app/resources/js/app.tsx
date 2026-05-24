import '../css/app.css'
import { createInertiaApp } from "@inertiajs/react"
import { createRoot } from "react-dom/client"

const appName = import.meta.env.VITE_APP_NAME || "AI Agent App"

await createInertiaApp({
    title: title => `${title} - ${appName}`,
    resolve: name => {
        const pages = import.meta.glob('./Pages/**/*.tsx', { eager: true })
        return pages[`./Pages/${name}.tsx`]
    },
    setup({ el, App, props }) {
        createRoot(el).render(<App {...props} />)
    },
    progress: {
        color: "#6366f1",
    },
})
