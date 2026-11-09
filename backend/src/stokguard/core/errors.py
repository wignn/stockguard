class DomainError(Exception):
    def __init__(self, code: str, status: int, message: str, fields: dict[str, str] | None = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message
        self.fields = fields
