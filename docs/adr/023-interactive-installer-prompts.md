# 023. Interactive installer prompts

- Date: 2026-10-19
- Status: Accepted

## Problem

`fastapi-startkit init` asks its questions with Cleo's numbered prompts:

```text
App? Pick one or both, comma-separated [web     HTTP server with FastAPI routes]:
 [ 0] web     HTTP server with FastAPI routes
 [ 1] worker  TaskIQ background jobs on Redis
 >
```

Users type indexes such as `0,1`, the default is repeated in full inside the brackets, and the short titles (`Database?`, `Frontend?`) do not say what each option sets up. The wizard is the first thing a new user sees, and the reference experience is Laravel Prompts: a boxed question, arrow keys to move, space to toggle, enter to submit, and the answer collapsed into the box afterwards.

## Alternatives

1. **questionary (prompt_toolkit).** Mature select and checkbox prompts, including Windows, but adds questionary, prompt_toolkit and wcwidth to the core package that every application installs, and renders a plain list rather than a box.
2. **questionary behind an `installer` extra.** Keeps the core lean, but the uvx and `install.sh` entry points must request the extra and two prompt paths have to be maintained.
3. **A small module in the installer.** `termios`/`tty` from the standard library put the terminal in cbreak mode; ANSI sequences draw and redraw a box. No dependency. Unix only, with the existing Cleo prompts as the fallback.

## Decision

Option 3. The installer gets `installer/prompts.py` with Laravel Prompts-style `text`, `select`, `multiselect` and `confirm`. When the command's input stream and standard output are both terminals and `termios` is available, those prompts are used; otherwise (Windows, piped input, `CommandTester`) the same questions go through Cleo's numbered prompts, so scripted input and existing tests keep working.

Questions become full sentences and every option carries a hint describing what it generates:

| Question | Options |
|---|---|
| Where should the project be created? | free text, placeholder `example-project` |
| Which services should your application run? | Web — HTTP server with FastAPI routes and a health check; Worker — TaskIQ background jobs with a Redis broker |
| Which database will your application use? | None — no ORM or migrations; SQLite — file-based, no server required; PostgreSQL — asyncpg driver; MySQL — aiomysql driver |
| Which frontend would you like to install? | None — API only; React — Inertia, React, TypeScript and Tailwind; Vue — Inertia, Vue, TypeScript and Tailwind |
| Create the application with these settings? | Yes / No |

## Implementation

- `Choice(value, label, hint)` describes an option; the command maps answers back to the existing `InstallOptions` values (`web`/`worker`/`both`, `none`/`sqlite`/…), so `--app`, `--database` and `--frontend` are unchanged.
- `Terminal` owns the TTY: on entry it saves the `termios` attributes, switches to cbreak mode (Ctrl-C still raises `KeyboardInterrupt`) and hides the cursor; on exit it restores both. `draw()` moves the cursor up over the previous frame (`ESC[nF`, `ESC[J`) and writes the new one.
- `Prompter` holds the key handling and rendering. Rendering is pure: a frame is a list of strings built by `box()`, which pads by visible width, truncates long rows with `…`, and caps the width at the terminal's columns so redraw line counts stay correct. Arrow keys and `j`/`k` move, space toggles in multiselect, enter submits, multiselect refuses an empty answer with a footer message. After submission the box is redrawn once, collapsed to the answer.
- Colours follow Laravel Prompts (cyan accent, grey inactive rows) and are disabled when `NO_COLOR` is set.
- `ClassicPrompts` implements the same four methods with Cleo's `ask`, `choice` and `confirm`, showing the hint next to each label.
- `InitCommand` picks one of the two at the start of an interactive run and prints `Cancelled.` and exits 1 on Ctrl-C.

## Validation

- Unit tests drive `Prompter` with a scripted terminal: moving, wrapping, toggling, the empty multiselect guard, text editing with backspace and the default, and the collapsed frame after submission.
- `box()` tests cover padding with ANSI colour codes, truncation and `NO_COLOR`.
- A pseudo-terminal test runs `fastapi-startkit init --dry-run` under `pty`, sends arrow keys, space and enter, and checks the resulting plan, proving cbreak mode, redraws and terminal restoration on a real TTY.
- Existing `CommandTester` tests continue to pass through `ClassicPrompts` with numbered input.
