from .Facade import Facade


class Redis(metaclass=Facade):
    key = "redis"
