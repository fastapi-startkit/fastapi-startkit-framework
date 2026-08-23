import pytest

from fastapi_startkit.exceptions.exceptions import LoaderNotFound
from fastapi_startkit.loader.Loader import Loader, parameters_filter


MODULE_SOURCE = """
from collections import UserList


class Dog(UserList):
    pass


class Cat(UserList):
    pass


SPEED = 5


def bark():
    return "woof"
"""


@pytest.fixture
def module_dir(tmp_path):
    """A directory (no dots in the path) containing a single loadable module."""
    pkg = tmp_path / "zoo_pkg"
    pkg.mkdir()
    (pkg / "zoo.py").write_text(MODULE_SOURCE)
    return str(pkg)


@pytest.fixture
def module_file(module_dir):
    return f"{module_dir}/zoo.py"


class TestGetModules:
    def test_returns_loaded_modules_keyed_by_name(self, module_dir):
        modules = Loader().get_modules(module_dir)
        assert "zoo" in modules
        assert hasattr(modules["zoo"], "Dog")

    def test_accepts_single_path_or_list(self, module_dir):
        loader = Loader()
        assert loader.get_modules([module_dir]).keys() == loader.get_modules(module_dir).keys()


class TestFind:
    def test_find_returns_matching_class(self, module_dir):
        from collections import UserList

        dog = Loader().find(UserList, [module_dir], "Dog")
        assert dog.__name__ == "Dog"

    def test_find_returns_none_when_missing(self, module_dir):
        from collections import UserList

        assert Loader().find(UserList, [module_dir], "Nope") is None

    def test_find_raises_when_missing_and_requested(self, module_dir):
        from collections import UserList

        with pytest.raises(LoaderNotFound):
            Loader().find(UserList, [module_dir], "Nope", raise_exception=True)


class TestFindAll:
    def test_find_all_returns_subclasses(self, module_dir):
        from collections import UserList

        classes = Loader().find_all(UserList, [module_dir])
        assert {"Dog", "Cat"} <= set(classes.keys())

    def test_find_all_raises_when_none_found(self, module_dir):
        class Unrelated:
            pass

        loader = Loader()
        with pytest.raises(LoaderNotFound):
            loader.find_all(Unrelated, [module_dir], raise_exception=True)

    def test_find_all_empty_without_raise(self, module_dir):
        class Unrelated:
            pass

        assert Loader().find_all(Unrelated, [module_dir]) == {}


class TestGetObjects:
    def test_get_object_from_path(self, module_file):
        assert Loader().get_object(module_file, "SPEED") == 5

    def test_get_objects_from_path(self, module_file):
        objects = Loader().get_objects(module_file)
        assert "Dog" in objects
        assert "bark" in objects

    def test_get_objects_with_filter(self, module_file):
        objects = Loader().get_objects(module_file, filter_method=lambda o: callable(o))
        assert "bark" in objects
        assert "SPEED" not in objects

    def test_get_objects_from_module_instance(self, module_file):
        loader = Loader()
        module = loader.get_object(module_file, None)
        objects = loader.get_objects(module)
        assert "Dog" in objects

    def test_get_objects_missing_module_returns_none(self, tmp_path):
        assert Loader().get_objects(f"{tmp_path}/does_not_exist.py") is None


class TestGetParameters:
    def test_returns_non_dunder_members(self, module_file):
        params = Loader().get_parameters(module_file)
        assert "SPEED" in params
        assert "Dog" in params
        assert not any(name.startswith("__") for name in params)


class TestParametersFilter:
    def test_rejects_dunder(self):
        assert parameters_filter("__init__", object()) is False
        assert parameters_filter("value", 1) is True
