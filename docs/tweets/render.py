# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10", "pygments>=2.17"]
# ///
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pygments.lexers import get_lexer_for_filename
from pygments.token import Comment, Keyword, Name, Number, Operator, String

WIDTH, HEIGHT = 1600, 900
BACKGROUND = "#4255ff"
CARD = "#0d1117"
CARD_BORDER = "#30363d"
TEXT = "#e6edf3"
PADDING = 64
LINE_HEIGHT = 1.9
MAX_FONT_SIZE = 40
MIN_FONT_SIZE = 16
FONT_DIRS = [
    Path(os.environ.get("TWEET_FONT_DIR", Path.home() / "Library" / "Fonts")),
    Path("/Library/Fonts"),
]
FALLBACK_FONT = Path(__file__).parent / "fonts" / "JetBrainsMono-Regular.ttf"


def font_file(name: str) -> Path:
    for directory in FONT_DIRS:
        if (directory / name).exists():
            return directory / name
    return FALLBACK_FONT


REGULAR = font_file("DankMono-Regular.otf")
ITALIC = font_file("DankMono-Italic.otf")

ITALIC_TOKENS = (Comment, Keyword, Operator.Word)
PALETTE = [
    (Comment, "#8b949e"),
    (Keyword, "#ff7b72"),
    (Operator.Word, "#ff7b72"),
    (Name.Function, "#d2a8ff"),
    (Name.Decorator, "#d2a8ff"),
    (Name.Class, "#79c0ff"),
    (Name.Builtin, "#79c0ff"),
    (String, "#a5d6ff"),
    (Number, "#79c0ff"),
]


def color_for(token_type) -> str:
    for parent, color in PALETTE:
        if token_type in parent:
            return color
    return TEXT


def is_italic(token_type) -> bool:
    return any(token_type in parent for parent in ITALIC_TOKENS)


def tokenized_lines(path: Path) -> list[list[tuple[str, str, bool]]]:
    lexer = get_lexer_for_filename(path.name, stripnl=False)
    lines: list[list[tuple[str, str, bool]]] = [[]]
    for token_type, value in lexer.get_tokens(path.read_text().rstrip("\n")):
        for index, part in enumerate(value.split("\n")):
            if index:
                lines.append([])
            if part:
                lines[-1].append((part, color_for(token_type), is_italic(token_type)))
    if not lines[-1]:
        lines.pop()
    return lines


def fitting_size(lines: list[list[tuple[str, str, bool]]]) -> int:
    columns = max(sum(len(text) for text, _, _ in line) for line in lines)
    for size in range(MAX_FONT_SIZE, MIN_FONT_SIZE - 1, -1):
        width = (
            ImageFont.truetype(str(REGULAR), size).getlength("M") * columns
            + PADDING * 2
        )
        height = size * LINE_HEIGHT * len(lines) + PADDING * 2
        if width <= WIDTH - 320 and height <= HEIGHT - 160:
            return size
    return MIN_FONT_SIZE


def render(source: Path, target: Path) -> None:
    lines = tokenized_lines(source)
    size = fitting_size(lines)
    font = ImageFont.truetype(str(REGULAR), size)
    italic = ImageFont.truetype(str(ITALIC), size)
    advance = font.getlength("M")
    line_height = font.size * LINE_HEIGHT
    columns = max(sum(len(text) for text, _, _ in line) for line in lines)
    card_width = int(advance * columns + PADDING * 2)
    card_height = int(
        line_height * len(lines) + PADDING * 2 - (line_height - font.size)
    )
    left = (WIDTH - card_width) // 2
    top = (HEIGHT - card_height) // 2
    box = (left, top, left + card_width, top + card_height)

    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    shadow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (box[0], box[1] + 24, box[2], box[3] + 24), 28, fill=(0, 0, 40, 120)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(36))
    image.paste(shadow, mask=shadow)

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(box, 24, fill=CARD, outline=CARD_BORDER, width=2)
    for row, line in enumerate(lines):
        x = left + PADDING
        y = top + PADDING + row * line_height
        for text, color, slanted in line:
            draw.text((x, y), text, font=italic if slanted else font, fill=color)
            x += advance * len(text)

    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, optimize=True)


def main(thread: Path) -> None:
    for source in sorted((thread / "cards").iterdir()):
        target = thread / "images" / f"{source.stem}.png"
        render(source, target)
        print(target)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
