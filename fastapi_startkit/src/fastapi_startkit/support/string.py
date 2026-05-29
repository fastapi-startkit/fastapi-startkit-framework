import re


class Stringable:
    def __init__(self, text: str):
        self.text = text

    def __str__(self) -> str:
        return self.text

    def trim(self, suffix: str) -> "Stringable":
        return Stringable(Str.trim(self.text, suffix))

    def slugify(self) -> "Stringable":
        return Stringable(Str.slugify(self.text))

    def camel_case(self) -> "Stringable":
        return Stringable(Str.camel_case(self.text))

    def snake_case(self) -> "Stringable":
        return Stringable(Str.snake_case(self.text))


class Str:
    @classmethod
    def of(cls, text: str) -> "Stringable":
        return Stringable(text)

    @classmethod
    def slugify(cls, text: str) -> str:
        """Strip all non-alphanumeric characters and lowercase."""
        return re.sub(r"[^a-z0-9]", "", text.lower())

    @classmethod
    def trim(cls, text: str, word: str) -> str:
        """Remove all occurrences of a word from the string (case-insensitive)."""
        return re.sub(re.escape(word), "", text, flags=re.IGNORECASE).strip("_").strip()

    @classmethod
    def camel_case(cls, text: str) -> str:
        """Convert a string to camelCase."""
        words = re.split(r"[-_\s]+", text)
        return words[0].lower() + "".join(word.capitalize() for word in words[1:])

    @classmethod
    def snake_case(cls, text: str) -> str:
        """Convert a string to snake_case."""
        text = re.sub(r"[-\s]+", "_", text)
        text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
        text = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", text)
        return text.lower()
