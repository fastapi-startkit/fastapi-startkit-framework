from fastapi_startkit.mcp import Response, Tool
from pydantic import BaseModel

notes: list[str] = []


class ListNotesTool(Tool):
    name = "list_notes"
    description = "List every saved note."
    scopes = ["notes:read"]

    async def handle(self, arguments: dict) -> Response:
        return Response.structure({"notes": notes})


class AddNoteInput(BaseModel):
    text: str


class AddNoteTool(Tool):
    name = "add_note"
    description = "Save a new note."
    scopes = ["notes:write"]

    def schema(self) -> type[BaseModel]:
        return AddNoteInput

    async def handle(self, arguments: dict) -> Response:
        note = AddNoteInput(**arguments)
        notes.append(note.text)
        return Response.text(f"Saved note #{len(notes)}.")
