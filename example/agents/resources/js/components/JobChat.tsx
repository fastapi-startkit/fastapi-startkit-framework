import { useState, useRef, useEffect } from "react"
import { createParser, type EventSourceMessage } from "eventsource-parser"

type Job = {
    id: number
    title: string
    location: string
    company: string
    type: string
}

type Frame =
    | { kind: "delta"; node: string; text: string }
    | { kind: "envelope"; node?: string; type: "tool_response"; data: Job[]; data_type: "json" }
    | { kind: "envelope"; type: "text"; data: string; data_type: "string" }
    | { kind: "interrupt"; type: string; reason: string; message: string }

type Message = {
    role: "user" | "assistant"
    content: string
    jobs?: Job[]
    interrupt?: boolean
}

type JobChatProps = {
    title?: string
    endpoint?: string
    placeholder?: string
    emptyState?: string
}

export default function JobChat({
    title = "Jobs",
    endpoint = "/jobs/stream",
    placeholder = "Search for jobs...",
    emptyState = "Ask me to find jobs.",
}: JobChatProps) {
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState("")
    const [loading, setLoading] = useState(false)
    const bottomRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [messages])

    const patchLast = (patch: (last: Message) => Message) =>
        setMessages(prev => [...prev.slice(0, -1), patch(prev[prev.length - 1])])

    const applyFrame = (frame: Frame) => {
        if (frame.kind === "delta") {
            // The backend streams every node; the router's deltas are raw routing
            // JSON, so this UI chooses not to render them.
            if (frame.node === "router") return
            patchLast(last => ({ ...last, content: last.content + frame.text }))
        } else if (frame.kind === "envelope" && frame.type === "tool_response") {
            patchLast(last => ({ ...last, jobs: frame.data }))
        } else if (frame.kind === "envelope" && frame.type === "text") {
            patchLast(last => ({ ...last, content: frame.data }))
        } else if (frame.kind === "interrupt") {
            patchLast(last => ({ ...last, content: frame.message, interrupt: true }))
        }
    }

    const handleSubmit = async (e: { preventDefault(): void }) => {
        e.preventDefault()
        if (!input.trim() || loading) return

        const userMessage = input.trim()
        setInput("")
        setMessages(prev => [...prev, { role: "user", content: userMessage }])
        setLoading(true)
        setMessages(prev => [...prev, { role: "assistant", content: "" }])

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: userMessage }),
            })

            const reader = response.body?.getReader()
            const decoder = new TextDecoder()
            if (!reader) return

            const parser = createParser({
                onEvent: (event: EventSourceMessage) => applyFrame(JSON.parse(event.data) as Frame),
            })

            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                parser.feed(decoder.decode(value, { stream: true }))
            }
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="flex flex-col h-screen max-w-2xl mx-auto p-4">
            <h1 className="text-xl font-bold mb-4">{title}</h1>

            <div className="flex-1 overflow-y-auto space-y-3 mb-4">
                {messages.length === 0 && (
                    <p className="text-center text-gray-400 mt-8">{emptyState}</p>
                )}
                {messages.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                        <div className="max-w-sm space-y-2">
                            {msg.jobs && msg.jobs.length > 0 && (
                                <div className="space-y-2">
                                    {msg.jobs.map(job => (
                                        <div key={job.id} className="border rounded-xl px-4 py-2 bg-white shadow-sm">
                                            <p className="font-semibold text-gray-800">{job.title}</p>
                                            <p className="text-sm text-gray-500">
                                                {job.company} · {job.location} · {job.type}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            )}
                            {(msg.content || msg.role === "user" || (loading && i === messages.length - 1)) && (
                                <div className={`px-4 py-2 rounded-2xl whitespace-pre-wrap ${
                                    msg.role === "user"
                                        ? "bg-blue-500 text-white"
                                        : msg.interrupt
                                            ? "bg-amber-50 text-amber-900 border border-amber-200"
                                            : "bg-gray-100 text-gray-800"
                                }`}>
                                    {msg.content || (loading && i === messages.length - 1 ? "▋" : "")}
                                </div>
                            )}
                        </div>
                    </div>
                ))}
                <div ref={bottomRef} />
            </div>

            <form onSubmit={handleSubmit} className="flex gap-2">
                <input
                    className="flex-1 border rounded-xl px-4 py-2 outline-none focus:ring-2 focus:ring-blue-400"
                    type="text"
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    placeholder={placeholder}
                    disabled={loading}
                />
                <button
                    type="submit"
                    disabled={loading || !input.trim()}
                    className="bg-blue-500 text-white px-5 py-2 rounded-xl disabled:opacity-50 hover:bg-blue-600 transition-colors"
                >
                    Send
                </button>
            </form>
        </div>
    )
}
