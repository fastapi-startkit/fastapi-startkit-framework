from typing import TYPE_CHECKING

from .can_override_config import CanOverrideConfig
from .can_override_default_options import CanOverrideOptionsDefault

if TYPE_CHECKING:
    from fastapi_startkit import Application


class Command(CanOverrideOptionsDefault, CanOverrideConfig):
    container: "Application"

    def set_container(self, container: "Application") -> None:
        self.container = container
