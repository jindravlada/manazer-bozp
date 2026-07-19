"""Společná politika editace záložek koordinace (UX-COORD-6b)."""

from __future__ import annotations

from collections.abc import Callable


class CoordinationTabEditPolicyMixin:
    """Mixin pro záložky: read-only režim a guard při stavu Připraveno k vydání."""

    _content_editable: bool = True
    _before_mutate: Callable[[], bool] | None = None

    def set_content_editable(
        self,
        editable: bool,
        *,
        before_mutate: Callable[[], bool] | None = None,
    ) -> None:
        self._content_editable = editable
        self._before_mutate = before_mutate
        update = getattr(self, "_update_action_buttons", None)
        if callable(update):
            update()

    def allow_mutate(self) -> bool:
        if not getattr(self, "_content_editable", True):
            return False
        guard = getattr(self, "_before_mutate", None)
        if callable(guard) and not guard():
            return False
        return True
