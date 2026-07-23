import '../css/app.css'
import { createInertiaApp } from "@inertiajs/react"
import { createRoot } from "react-dom/client"

// @ts-ignore
const appName = import.meta.env.VITE_APP_NAME || "My App"

await createInertiaApp({
    title: title => `${title} - ${appName}`,
    resolve: name => {
        // @ts-ignore
        const pages = import.meta.glob('./pages/**/*.tsx', { eager: true })
        return pages[`./pages/${name}.tsx`]
    },
    setup({ el, App, props }) {
        createRoot(el).render(<App {...props} />)
    },
    progress: {
        color: "#F87415",
    },
})
