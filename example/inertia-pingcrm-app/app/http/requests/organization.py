class OrganizationListRequest:
    def __init__(self, search: str = "", page: int = 1, limit: int = 10):
        self.search = search
        self.page = page
        self.limit = limit
