from packages.agent import Agent, model, provider


@provider("google")
@model("gemini-2.5-flash-lite")
class ChatAgent(Agent):
    def messages(self):
        return [{"role": "system", "content": "You are a helpful assistant."}]
