import { useState, useRef, useEffect } from "react"
import { createParser, type EventSourceMessage } from "eventsource-parser"

type Message = {
    role: "user" | "assistant"
    content: string
}

type ChatProps = {
    title?: string
    endpoint?: string
    placeholder?: string
    emptyState?: string
}

export default function Chat({
    title = "Chat",
    endpoint = "/chat/stream",
    placeholder = "Type a message...",
    emptyState = "Send a message to start chatting.",
}: ChatProps) {
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState("")
    const [loading, setLoading] = useState(false)
    const bottomRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [messages])

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

            const append = (text: string) =>
                setMessages(prev => {
                    const updated = [...prev]
                    updated[updated.length - 1] = {
                        role: "assistant",
                        content: updated[updated.length - 1].content + text,
                    }
                    return updated
                })

            // SSE frames: deltas carry model tokens; tool_response frames carry tool output.
            const parser = createParser({
                onEvent: (event: EventSourceMessage) => {
                    const frame = JSON.parse(event.data)
                    if (frame.type === "delta") append(frame.text)
                    else if (frame.type === "tool_response") append(frame.content)
                },
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
                        <div className={`max-w-sm px-4 py-2 rounded-2xl whitespace-pre-wrap ${
                            msg.role === "user"
                                ? "bg-blue-500 text-white"
                                : "bg-gray-100 text-gray-800"
                        }`}>
                            {msg.content || (loading && i === messages.length - 1 ? "▋" : "")}
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
