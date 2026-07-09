"""Typy callbacků pro automatickou kontrolu změn legislativy."""

from collections.abc import Callable

CheckProgressCallback = Callable[[int, int, str], None]
CheckStatusCallback = Callable[[str], None]
CancelCheckCallback = Callable[[], bool]
