from langchain_core.messages import AIMessage, HumanMessage

from app.agents.chat import RouterAgent


class TestRouterAgent:
    def test_the_router_agent(self):
        with RouterAgent.record("record_stream.json") as agent:
            agent.prompt("hello")
            agent.assert_text_response()
            agent.assert_tool_not_called(["job_search_tool"])
            agent.assert_response_judged(
                model="gpt-3.5-turbo",
                expectation="The llm should respond with greetings",
            )
            agent.assert_response_time_lt(5)

            agent.prompt("suggest python developer jobs")
            agent.assert_tool_called("job_search_tool", lambda tool: tool.name == "job_search_tool")

    def test_the_router_with_initial_messages(self):
        with RouterAgent.record(
            "record_stream.json",
            messages=[
                HumanMessage(content="Hi"),
                AIMessage(content="Hello, How can I help you?"),
            ],
        ) as agent:
            agent.prompt("suggest python developer jobs")
            agent.assert_tool_called("job_search_tool", lambda tool: tool.name == "job_search_tool")
