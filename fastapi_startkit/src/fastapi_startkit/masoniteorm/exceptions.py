class ModelNotFoundException(Exception):
    is_http_exception = True

    def __init__(self, message="Model Not Found"):
        super().__init__(message)
        self.message = message

    def get_response(self):
        return self.message

    def get_status(self):
        return 404
