from studio import Studio, Take

TAG = "lesson-13"
INSTALL = ["uv sync -q", "uv run python artisan db:migrate"]

CURL = """curl -X POST http://127.0.0.1:8000/api/projects/1/issues \\
  -H "Content-Type: application/json" \\
  -d '{"title": "Add a pricing page", "reporter_id": 2}'"""

FIRST_ISSUE = (
    "curl -s -o /dev/null -X POST http://127.0.0.1:8000/api/projects/1/issues "
    "-H 'Content-Type: application/json' "
    "-d '{\"title\": \"Homepage hero image is blurry\", \"reporter_id\": 1}'"
)

NEW_ISSUE = "Show prices in euros"


def point(studio: Studio, selector: str, rest: float, inset: float | None = None, steps: int = 25) -> None:
    box = studio.page.locator(selector).first.bounding_box()
    x = box["x"] + (inset if inset is not None else box["width"] / 2)
    studio.page.mouse.move(x, box["y"] + box["height"] / 2, steps=steps)
    studio.wait(rest)


def welcome(studio: Studio) -> None:
    studio.cue("welcome")
    studio.wait(10.8)
    studio.cue("domain")
    point(studio, "h1", 1.2, inset=110)
    point(studio, "article:has-text('APP-1') p.text-xs >> nth=0", 2.6, inset=26)
    for column in ("To Do", "In Progress", "In Review", "Done"):
        point(studio, f"h2:text-is('{column}')", 1.0, inset=48)
    studio.cue("stack")
    studio.page.mouse.move(1180, 820, steps=60)
    studio.wait(13.6)
    studio.cue("tdd")
    studio.wait(9.4)


def curl(studio: Studio) -> None:
    studio.cue("intro")
    studio.line(20, end=False)
    studio.terminal()
    studio.wait(7.0)
    studio.cue("type-curl")
    studio.run(CURL, settle=0.5, pace=0.035)
    studio.cue("response")
    studio.shot("response")
    studio.wait(8.6)
    studio.cue("transitions")
    studio.wait(9.6)


def board(studio: Studio) -> None:
    studio.cue("board")
    studio.wait(6.4)
    studio.click("input[placeholder=\"What's the issue?\"]")
    studio.cue("type-title")
    studio.type(NEW_ISSUE, 0.07)
    studio.wait(0.5)
    studio.click("button:has-text('Add')")
    card = f"article:has-text('{NEW_ISSUE}')"
    studio.page.locator(card).wait_for()
    studio.cue("added")
    studio.shot("added")
    studio.wait(4.8)
    studio.click(f"{card} button:has-text('In Progress')")
    studio.page.locator(f"{card} button:has-text('In Review')").wait_for()
    studio.cue("moved")
    studio.wait(3.2)
    studio.page.locator(f"{card} button:has-text('In Review')").hover()
    studio.shot("moved")
    studio.wait(6.2)


def ideas(studio: Studio) -> None:
    studio.cue("providers")
    studio.line(22, end=False)
    studio.wait(13.1)
    studio.open("config/issues.py")
    studio.cue("config")
    studio.wait(8.0)
    studio.terminal()
    studio.run("uv run python artisan", settle=1.2)
    studio.cue("artisan")
    studio.shot("artisan")
    studio.wait(6.4)
    studio.press("ControlOrMeta+k", 0.3)
    studio.run("ls databases/migrations", settle=0.5)
    studio.cue("outro")
    studio.shot("outro")
    studio.wait(9.6)


TAKES = [
    Take(
        name="welcome",
        tag=TAG,
        perform=welcome,
        setup=[*INSTALL, "uv run python artisan db:seed", "npm install --silent", "npm run build"],
        browser="/projects/2/board",
    ),
    Take(
        name="curl",
        tag=TAG,
        perform=curl,
        open="routes/api.py",
        setup=[*INSTALL, "uv run python artisan db:seed user", "uv run python artisan db:seed project"],
        ready=[FIRST_ISSUE],
        server=True,
    ),
    Take(
        name="board",
        tag=TAG,
        perform=board,
        setup=[*INSTALL, "uv run python artisan db:seed", "npm install --silent", "npm run build"],
        browser="/projects/1/board",
    ),
    Take(
        name="ideas",
        tag=TAG,
        perform=ideas,
        open="bootstrap/application.py",
        panel=0.6,
        setup=INSTALL,
    ),
]
