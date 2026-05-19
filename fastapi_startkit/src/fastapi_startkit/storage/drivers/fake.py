import shutil
import tempfile

from .local import LocalDriver


class FakeDriver(LocalDriver):
    def __init__(self, application, disk_name: str = "default"):
        super().__init__(application)
        self._disk_name = disk_name
        self._root = tempfile.mkdtemp(prefix=f"storage_fake_{disk_name}_")
        self.options = {"root": self._root}

    def set_options(self, options):
        # Ignore — never overwrite the fake temp root with real disk config.
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cleanup()

    def cleanup(self):
        shutil.rmtree(self._root, ignore_errors=True)

    def assert_exists(self, paths, content=None):
        if isinstance(paths, str):
            paths = [paths]

        for path in paths:
            assert self.exists(path), f"Storage::fake({self._disk_name!r}): failed asserting that [{path!r}] exists."
            if content is not None:
                actual = self.get(path)
                assert actual == content, (
                    f"Storage::fake({self._disk_name!r}): "
                    f"content of [{path!r}] does not match.\n"
                    f"  expected: {content!r}\n"
                    f"  actual:   {actual!r}"
                )

        return self

    def assert_missing(self, paths):
        if isinstance(paths, str):
            paths = [paths]

        for path in paths:
            assert self.missing(path), (
                f"Storage::fake({self._disk_name!r}): failed asserting that [{path!r}] is missing."
            )

        return self

    def assert_count(self, count: int, directory: str = ""):
        files = self.get_files(directory)
        assert len(files) == count, (
            f"Storage::fake({self._disk_name!r}): "
            f"expected {count} file(s) in [{directory or '/'}], "
            f"found {len(files)}: {[f.name for f in files]}"
        )
        return self

    def assert_directory_empty(self, directory: str = ""):
        return self.assert_count(0, directory)
