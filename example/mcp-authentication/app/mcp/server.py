from fastapi_startkit.mcp import Server

from app.mcp.tools import AddNoteTool, ListNotesTool


class NotesServer(Server):
    name = "notes"
    description = "Read and write notes."

    def tools(self):
        return [ListNotesTool, AddNoteTool]
