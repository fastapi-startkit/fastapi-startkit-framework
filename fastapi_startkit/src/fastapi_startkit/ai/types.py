from collections.abc import AsyncIterator
from typing import Callable

Handler = Callable[[list], AsyncIterator]
Middleware = Callable[[list, Handler], AsyncIterator]
