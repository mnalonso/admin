import json
from typing import Any, Callable, Dict, Tuple


class Request:
    def __init__(self) -> None:
        self.args: Dict[str, Any] = {}
        self.headers: Dict[str, Any] = {}


request = Request()


class SimpleResponse:
    def __init__(self, data: Any, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def get_json(self) -> Any:
        return self._data


class TestClient:
    def __init__(self, app: "Flask") -> None:
        self.app = app

    def get(self, path: str, query_string: Dict[str, Any] | None = None, headers: Dict[str, str] | None = None):
        request.args = query_string or {}
        request.headers = headers or {}
        handler = self.app.routes.get((path, "GET"))
        if handler is None:
            return SimpleResponse({"error": "Not Found"}, status_code=404)
        result = handler()
        if isinstance(result, tuple):
            data, status = result
        else:
            data, status = result, 200
        return SimpleResponse(data, status_code=status)


def jsonify(data: Any) -> Any:
    return data


class Flask:
    def __init__(self, name: str):
        self.name = name
        self.routes: Dict[Tuple[str, str], Callable] = {}
        self.logger = self

    def setLevel(self, *_):
        pass

    def info(self, *_, **__):
        pass

    def exception(self, *_, **__):
        pass

    def route(self, rule: str, methods=None):
        methods = methods or ["GET"]

        def decorator(func: Callable):
            for method in methods:
                self.routes[(rule, method)] = func
            return func

        return decorator

    def test_client(self) -> TestClient:
        return TestClient(self)

    def run(self, host: str = "0.0.0.0", port: int = 5000, debug: bool = False):  # pragma: no cover
        pass


__all__ = ["Flask", "jsonify", "request"]
