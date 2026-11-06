# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10", "pygments>=2.17"]
# ///
import os
import sys
from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pygments.lexers import get_lexer_for_filename
from pygments.styles import get_style_by_name
from pygments.token import Comment, Keyword, Name, Operator, Punctuation, Text

WIDTH, HEIGHT = 1600, 900
GRADIENT = ("#a13d17", "#f27a4c")
DOT_GAP = 32
DOT_RADIUS = 2
DOT_COLOR = (255, 255, 255, 34)
SHADOW = (60, 15, 0, 150)
STYLE = get_style_by_name("github-dark")
CARD = STYLE.background_color
CARD_BORDER = "#30363d"
TITLE_COLOR = "#8b949e"
TITLE_SIZE = 22
WINDOW_BUTTONS = ("#ff5f57", "#febc2e", "#28c840")
BUTTON_RADIUS = 9
TITLE_BAR = 56
PADDING = 64
LINE_HEIGHT = 1.9
MAX_FONT_SIZE = 40
MIN_FONT_SIZE = 16
ITALIC_TOKENS = (Comment, Keyword, Operator.Word)
FONT_DIRS = [
    Path(os.environ.get("TWEET_FONT_DIR", Path.home() / "Library" / "Fonts")),
    Path("/Library/Fonts"),
]
FALLBACK_FONT = Path(__file__).parent / "fonts" / "JetBrainsMono-Regular.ttf"

Span = tuple[str, str, bool]


def font_file(name: str) -> Path:
    for directory in FONT_DIRS:
        if (directory / name).exists():
            return directory / name
    return FALLBACK_FONT


REGULAR = font_file("DankMono-Regular.otf")
ITALIC = font_file("DankMono-Italic.otf")


def refined(tokens: list[tuple], shell: bool) -> list[tuple]:
    result = []
    command_expected = True
    for index, (token_type, value) in enumerate(tokens):
        following = next((v for _, v in tokens[index + 1 :] if v.strip()), "")
        is_call = token_type in (
            Name,
            Name.Builtin,
            Name.Other,
        ) and following.startswith("(")
        is_command = (
            shell and command_expected and token_type in Text and bool(value.strip())
        )
        if token_type is Name.Namespace:
            token_type = Name
        elif token_type in Operator and value == ".":
            token_type = Punctuation
        elif is_call or is_command:
            token_type = Name.Function
        if value.strip():
            command_expected = False
        if "\n" in value:
            command_expected = True
        result.append((token_type, value))
    return result


def span(token_type, text: str) -> Span:
    color = STYLE.style_for_token(token_type)["color"] or "e6edf3"
    slanted = any(token_type in parent for parent in ITALIC_TOKENS)
    return text, f"#{color}", slanted


def tokenized_lines(path: Path) -> list[list[Span]]:
    lexer = get_lexer_for_filename(path.name, stripnl=False)
    tokens = list(lexer.get_tokens(path.read_text().rstrip("\n")))
    shell = path.suffix == ".sh"
    lines: list[list[Span]] = [[]]
    for token_type, value in refined(tokens, shell):
        for index, part in enumerate(value.split("\n")):
            if index:
                lines.append([])
            if part:
                lines[-1].append(span(token_type, part))
    if not lines[-1]:
        lines.pop()
    return lines


def columns_of(lines: list[list[Span]]) -> int:
    return max(sum(len(text) for text, _, _ in line) for line in lines)


def fitting_size(lines: list[list[Span]]) -> int:
    columns = columns_of(lines)
    for size in range(MAX_FONT_SIZE, MIN_FONT_SIZE - 1, -1):
        advance = ImageFont.truetype(str(REGULAR), size).getlength("M")
        width = advance * columns + PADDING * 2
        height = size * LINE_HEIGHT * len(lines) + PADDING * 2 + TITLE_BAR
        if width <= WIDTH - 320 and height <= HEIGHT - 120:
            return size
    return MIN_FONT_SIZE


def gradient() -> Image.Image:
    diagonal = int((WIDTH**2 + HEIGHT**2) ** 0.5) + 2
    ramp = Image.linear_gradient("L").resize((diagonal, diagonal)).rotate(-60)
    offset = ((diagonal - WIDTH) // 2, (diagonal - HEIGHT) // 2)
    ramp = ramp.crop((*offset, offset[0] + WIDTH, offset[1] + HEIGHT))
    start, end = (Image.new("RGB", (WIDTH, HEIGHT), color) for color in GRADIENT)
    return Image.composite(end, start, ramp)


@cache
def background() -> Image.Image:
    image = gradient()
    dots = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dots)
    for y in range(DOT_GAP // 2, HEIGHT, DOT_GAP):
        for x in range(DOT_GAP // 2, WIDTH, DOT_GAP):
            draw.ellipse(
                (x - DOT_RADIUS, y - DOT_RADIUS, x + DOT_RADIUS, y + DOT_RADIUS),
                fill=DOT_COLOR,
            )
    image.paste(dots, mask=dots)
    return image


def draw_shadow(image: Image.Image, box: tuple[int, int, int, int]) -> None:
    shadow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (box[0], box[1] + 24, box[2], box[3] + 24), 28, fill=SHADOW
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(36))
    image.paste(shadow, mask=shadow)


def draw_window_buttons(draw: ImageDraw.ImageDraw, left: int, top: int) -> None:
    center_y = top + TITLE_BAR // 2 + 8
    for index, color in enumerate(WINDOW_BUTTONS):
        center_x = left + 36 + index * 30
        draw.ellipse(
            (
                center_x - BUTTON_RADIUS,
                center_y - BUTTON_RADIUS,
                center_x + BUTTON_RADIUS,
                center_y + BUTTON_RADIUS,
            ),
            fill=color,
        )


def render(source: Path, title: str, target: Path) -> None:
    lines = tokenized_lines(source)
    size = fitting_size(lines)
    font = ImageFont.truetype(str(REGULAR), size)
    italic = ImageFont.truetype(str(ITALIC), size)
    advance = font.getlength("M")
    line_height = size * LINE_HEIGHT
    title_font = ImageFont.truetype(str(REGULAR), TITLE_SIZE)
    title_width = title_font.getlength(title)
    card_width = int(max(advance * columns_of(lines) + PADDING * 2, title_width + 280))
    code_height = line_height * (len(lines) - 1) + size
    card_height = int(TITLE_BAR + code_height + PADDING * 2 - 16)
    left = (WIDTH - card_width) // 2
    top = (HEIGHT - card_height) // 2
    box = (left, top, left + card_width, top + card_height)

    image = background().copy()
    draw_shadow(image, box)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(box, 24, fill=CARD, outline=CARD_BORDER, width=2)
    draw_window_buttons(draw, left, top)
    draw.text(
        (left + card_width / 2, top + TITLE_BAR // 2 + 8),
        title,
        font=title_font,
        fill=TITLE_COLOR,
        anchor="mm",
    )
    for row, line in enumerate(lines):
        x = left + PADDING
        y = top + TITLE_BAR + PADDING - 16 + row * line_height
        for text, color, slanted in line:
            draw.text((x, y), text, font=italic if slanted else font, fill=color)
            x += advance * len(text)

    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, optimize=True)


def title_of(source: Path, card: Path) -> str:
    return "Terminal" if source.suffix == ".sh" else source.relative_to(card).as_posix()


def main(thread: Path) -> None:
    for card in sorted(path for path in (thread / "cards").iterdir() if path.is_dir()):
        sources = sorted(path for path in card.rglob("*") if path.is_file())
        for index, source in enumerate(sources, start=1):
            stem = card.name if len(sources) == 1 else f"{card.name}-{index}"
            target = thread / "images" / f"{stem}.png"
            render(source, title_of(source, card), target)
            print(target)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
