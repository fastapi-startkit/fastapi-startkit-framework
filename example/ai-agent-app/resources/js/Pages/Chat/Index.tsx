import { useState, useRef, useEffect } from "react"

interface Message {
    role: "user" | "assistant"
    content: string
}

export default function Index() {
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState("")
    const [loading, setLoading] = useState(false)
    const bottomRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [messages, loading])

    async function send() {
        const text = input.trim()
        if (!text || loading) return

        setMessages(prev => [...prev, { role: "user", content: text }])
        setInput("")
        setLoading(true)

        try {
            const res = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text }),
            })
            const data = await res.json()
            setMessages(prev => [...prev, { role: "assistant", content: data.reply }])
        } catch {
            setMessages(prev => [...prev, { role: "assistant", content: "Something went wrong. Please try again." }])
        } finally {
            setLoading(false)
        }
    }

    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            send()
        }
    }

    return (
        <div className="flex flex-col h-screen bg-gray-50">
            {/* Header */}
            <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center">
                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                </div>
                <div>
                    <h1 className="text-sm font-semibold text-gray-900">AI Assistant</h1>
                    <p className="text-xs text-gray-500">Powered by Claude</p>
                </div>
            </header>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
                {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-center gap-3">
                        <div className="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center">
                            <svg className="w-6 h-6 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                            </svg>
                        </div>
                        <p className="text-gray-500 text-sm">Send a message to start the conversation.</p>
                    </div>
                )}

                {messages.map((msg, i) => (
                    <div key={i} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
                        {/* Avatar */}
                        <div className={`w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-medium ${
                            msg.role === "user"
                                ? "bg-indigo-600 text-white"
                                : "bg-gray-200 text-gray-600"
                        }`}>
                            {msg.role === "user" ? "U" : "AI"}
                        </div>

                        {/* Bubble */}
                        <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                            msg.role === "user"
                                ? "bg-indigo-600 text-white rounded-tr-sm"
                                : "bg-white text-gray-800 border border-gray-200 rounded-tl-sm"
                        }`}>
                            {msg.content}
                        </div>
                    </div>
                ))}

                {/* Typing indicator */}
                {loading && (
                    <div className="flex gap-3">
                        <div className="w-7 h-7 rounded-full bg-gray-200 flex-shrink-0 flex items-center justify-center text-xs font-medium text-gray-600">
                            AI
                        </div>
                        <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1 items-center">
                            <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
                            <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                            <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
                        </div>
                    </div>
                )}

                <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="bg-white border-t border-gray-200 px-4 py-4">
                <div className="flex items-end gap-3 max-w-3xl mx-auto">
                    <textarea
                        className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent max-h-40 overflow-y-auto"
                        placeholder="Message AI Assistant…"
                        rows={1}
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={loading}
                    />
                    <button
                        onClick={send}
                        disabled={!input.trim() || loading}
                        className="w-10 h-10 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors flex-shrink-0"
                    >
                        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                        </svg>
                    </button>
                </div>
                <p className="text-center text-xs text-gray-400 mt-2">Press Enter to send · Shift+Enter for new line</p>
            </div>
        </div>
    )
}
