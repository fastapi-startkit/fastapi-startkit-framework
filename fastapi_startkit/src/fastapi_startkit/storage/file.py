import hashlib

from .helper import get_extension


class File:
    """A stored file.

    ``content`` means different things depending on where the File came from.
    Construct one yourself (to ``put``/``store`` it) and it holds the body. Get
    one back from a driver's ``get_files`` listing and it holds no body at all,
    because listing every body is expensive on S3 and undecodable for binary
    files on disk — what it holds there is driver-specific:

    - local/fake: ``None``. Read the body with ``driver.get(join(directory, file.name()))``.
    - s3: the boto3 ``ObjectSummary``, so ``file.stream().key`` recovers the
      full key that ``name()`` strips the prefix off of.

    ``name()`` is the one thing that means the same on every driver: the bare
    filename, with no directory prefix.
    """

    def __init__(self, content, filename=None):
        self.content = content
        self.filename = filename

    def path(self):
        pass

    def extension(self):
        return get_extension(self.filename)

    def name(self):
        return self.filename

    def stream(self):
        return self.content

    def hash_path_name(self):
        return f"{self.hash_name()}{self.extension()}"

    def hash_name(self):
        return hashlib.sha1(bytes(self.name(), "utf-8")).hexdigest()

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name()})"
