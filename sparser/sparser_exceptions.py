class SparserError(Exception):
    pass


class SparserSyntaxError(SparserError, SyntaxError):
    pass


class SparserValueError(SparserError, ValueError):
    pass


class SparserUnexpectedError(SparserError, AssertionError):
    pass
