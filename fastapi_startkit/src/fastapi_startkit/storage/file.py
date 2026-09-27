import hashlib

from .helper import get_extension


class File:
    def __init__(self, content, filename: str | None = None):
        self.content = content
        self.filename = filename

    def path(self):
        pass

    def extension(self):
        return get_extension(self._require_filename())

    def name(self):
        return self.filename

    def stream(self):
        return self.content

    def hash_path_name(self):
        return f"{self.hash_name()}{self.extension()}"

    def hash_name(self):
        return hashlib.sha1(bytes(self._require_filename(), "utf-8")).hexdigest()

    def _require_filename(self) -> str:
        if self.filename is None:
            raise ValueError(f"{self.__class__.__name__} has no filename")
        return self.filename

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name()})"
