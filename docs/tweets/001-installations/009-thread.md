# Tweet 9/10

AI agents are classes too. Give them instructions, tools and a pydantic schema, and fake their responses in tests 🤖

Card: `app/agents/support_agent.py`

```python
@provider("openai")
class SupportAgent(Agent):
    def instructions(self) -> str:
        return "You answer questions about customer orders."

    def tools(self):
        return [order_status]

    def schema(self):
        return OrderStatus

with SupportAgent.fake(['{"order_id": 1042, "status": "shipped"}']):
    await SupportAgent().prompt("Where is it?")
```
