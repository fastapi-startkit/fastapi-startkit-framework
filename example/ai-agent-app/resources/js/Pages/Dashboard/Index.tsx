interface Props {
    message: string
}

export default function Index({ message }: Props) {
    return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
            <div className="text-center">
                <h1 className="text-4xl font-bold text-gray-900 mb-4">AI Agent App</h1>
                <p className="text-gray-600">{message}</p>
            </div>
        </div>
    )
}
