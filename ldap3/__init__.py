ALL_ATTRIBUTES = "*"
SUBTREE = "SUBTREE"


class LDAPSocketOpenError(Exception):
    pass


class Server:
    def __init__(self, uri: str, connect_timeout: int | None = None):
        self.uri = uri
        self.connect_timeout = connect_timeout


class DummyStandard:
    def paged_search(
        self,
        search_base,
        search_filter,
        search_scope,
        attributes,
        paged_size,
        generator,
        time_limit,
    ):
        return []


class DummyExtend:
    def __init__(self):
        self.standard = DummyStandard()


class Connection:
    def __init__(
        self,
        server: Server,
        user: str | None = None,
        password: str | None = None,
        receive_timeout: int | None = None,
        auto_bind: bool = False,
    ):
        self.server = server
        self.user = user
        self.password = password
        self.receive_timeout = receive_timeout
        self.auto_bind = auto_bind
        self.extend = DummyExtend()

    def unbind(self):
        return True


__all__ = [
    "Connection",
    "LDAPSocketOpenError",
    "Server",
    "SUBTREE",
    "ALL_ATTRIBUTES",
]
