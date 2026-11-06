# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10", "pygments>=2.17", "svgelements>=1.9"]
# ///
import os
import sys
from functools import cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from pygments.lexers import get_lexer_for_filename
from pygments.token import Comment, Keyword, Name, Number, Operator, String
from svgelements import SVG, Close, Line, Move
from svgelements import Path as SvgPath

WIDTH, HEIGHT = 1600, 900
GRADIENT = ("#a13d17", "#f27a4c")
LOGO = Path(__file__).parent / "logo.svg"
LOGO_SIZE = 96
LOGO_GAP = 190
LOGO_ALPHA = 0.1
SHADOW = (60, 15, 0, 150)
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


def outline(path: SvgPath) -> list[tuple[float, float]]:
    points = []
    for segment in path:
        if isinstance(segment, (Move, Line, Close)):
            points.append(segment.end)
        else:
            points.extend(segment.point(step / 16) for step in range(1, 17))
    return [(point.x, point.y) for point in points if point is not None]


def logo_mask(size: int) -> Image.Image:
    supersample = 4
    svg = SVG.parse(str(LOGO))
    left, top, right, bottom = svg.bbox()
    factor = size * supersample / max(right - left, bottom - top)
    mask = Image.new("1", (size * supersample, size * supersample), 0)
    for element in svg.elements():
        if not isinstance(element, SvgPath):
            continue
        for subpath in element.as_subpaths():
            points = [
                ((x - left) * factor, (y - top) * factor)
                for x, y in outline(SvgPath(subpath))
            ]
            if len(points) < 3:
                continue
            layer = Image.new("1", mask.size, 0)
            ImageDraw.Draw(layer).polygon(points, fill=1)
            mask = ImageChops.logical_xor(mask, layer)
    return mask.convert("L").resize((size, size), Image.Resampling.LANCZOS)


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
    mark = logo_mask(LOGO_SIZE).point(lambda value: int(value * LOGO_ALPHA))
    white = Image.new("RGB", mark.size, "white")
    for row, y in enumerate(range(-LOGO_SIZE // 2, HEIGHT, LOGO_GAP // 2)):
        shift = LOGO_GAP // 2 if row % 2 else 0
        for x in range(-LOGO_SIZE + shift, WIDTH, LOGO_GAP):
            image.paste(white, (x, y), mark)
    return image


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

    image = background().copy()
    shadow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (box[0], box[1] + 24, box[2], box[3] + 24), 28, fill=SHADOW
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
