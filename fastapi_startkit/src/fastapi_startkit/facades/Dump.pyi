from typing import Any, List

DumpObject = Any

class Dump:
    """Dumper facade."""

    @staticmethod
    def clear() -> "Dump":
        """Clear all dumped data"""
        ...
    @staticmethod
    def dd(*objects: Any):
        """Dump all provided args and die, raising a DumpException."""
        ...
    @staticmethod
    def dump(*objects: Any):
        """Dump all provided args and continue code execution. This does not raise a DumpException."""
        ...
    @staticmethod
    def get_dumps(ascending: bool = False) -> List[DumpObject]:
        """Get all dumps as Dump objects. If ascending is True, get dumps from oldest to most recents."""
        ...
    @staticmethod
    def last() -> DumpObject:
        """Return last added dump."""
        ...
    @staticmethod
    def get_serialized_dumps(ascending: bool = False) -> List[dict]:
        """Get all dumps as dict. If ascending is True, sort dumps from oldest to most recents."""
        ...
