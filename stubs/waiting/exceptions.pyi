from typing import Any

class TimeoutExpired(Exception):
    def __init__(self, timeout_seconds: Any, what: Any) -> None: ...

class IllegalArgumentError(ValueError): ...

class NestedStopIteration(Exception):
    exc_info: Any = ...
    def __init__(self, exc_info: Any) -> None: ...
    def reraise(self) -> None: ...
