import textwrap

from fastapi_startkit.mcp import Argument, Prompt, Response


class CodeReviewPrompt(Prompt):
    """Generate a code-review prompt for a given language."""

    name = "code_review"
    title = "Code Review"
    description = "Generates a structured code-review prompt for the specified programming language."

    def arguments(self):
        return [
            Argument(name="language", description="Programming language to review (e.g. Python, TypeScript)", required=True),
            Argument(name="focus", description="Optional focus area (e.g. security, performance, readability)", required=False),
        ]

    async def handle(self, arguments: dict) -> Response:
        language = arguments.get("language", "code")
        focus = arguments.get("focus", "")
        focus_line = f" Focus especially on {focus}." if focus else ""
        prompt_text = textwrap.dedent(f"""
            You are an expert {language} code reviewer.{focus_line}

            Please review the provided code and give structured feedback covering:
            1. Correctness — does the code do what it intends?
            2. Readability — is the code easy to understand and maintain?
            3. Performance — are there obvious inefficiencies?
            4. Security — are there any security concerns?
            5. Suggested improvements — concrete, actionable next steps.
        """).strip()
        return Response.text(prompt_text)
