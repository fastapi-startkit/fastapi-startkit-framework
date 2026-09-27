from typing import Any, Callable

class Loader:
    @staticmethod
    def get_modules(files_or_directories: str | list[str], raise_exception: bool = False) -> dict[str, Any]:
        """Get a list of Python modules found (recursively) in the given list of files or directories.
        If raise_exception is enabled it will raise an exception in case of error during loading a module."""
    @staticmethod
    def find(
        class_instance: type,
        paths: str | list[str],
        class_name: str,
        raise_exception: bool = False,
    ) -> type | None: ...
    @staticmethod
    def find_all(class_instance: type, paths: str | list[str], raise_exception: bool = False) -> dict[str, type]: ...
    @staticmethod
    def get_object(path_or_module: str | Any, object_name: str, raise_exception: bool = False) -> Any:
        """Load the given object from a Python module located at path and returns a default value if
        not found. If no object name is provided, returns the loaded module."""
        ...
    @staticmethod
    def get_objects(
        path_or_module: str | Any,
        filter_method: Callable[[Any], bool] | None = None,
        raise_exception: bool = False,
    ) -> dict[str, Any] | None:
        """Returns a dictionary of objects from the given path (file or dotted). The dictionary can
        be filtered if a given callable is given."""
        ...
    @staticmethod
    def get_parameters(module_or_path: str | Any) -> dict[str, Any]: ...
