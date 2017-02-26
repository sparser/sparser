class SparserError(Exception):
    pass


class SparserSyntaxError(SparserError, SyntaxError):
    pass


class SparserValueError(SparserError, ValueError):
    pass
