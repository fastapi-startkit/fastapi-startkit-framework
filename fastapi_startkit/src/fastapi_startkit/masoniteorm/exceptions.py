from fastapi_startkit.exceptions import HttpException


class ModelNotFoundException(HttpException):
    def __init__(self, message="Model Not Found"):
        super().__init__(message)
        self.message = message

    def get_response(self):
        return self.message

    def get_status(self):
        return 404


class LazyLoadingViolation(Exception):
    def __init__(self, model: object, relation: str | None):
        self.model = type(model).__name__
        self.relation = relation
        super().__init__(
            f"Attempted to lazy load [{relation}] on model [{self.model}]. "
            f'Eager load it with {self.model}.with_("{relation}") or await the model\'s load("{relation}") first.'
        )
