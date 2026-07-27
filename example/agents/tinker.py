from app.agents.job_search_graph import build

graph = build().compile()

print(graph.get_graph().draw_mermaid())
