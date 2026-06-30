from collections.abc import Callable
from dataclasses import dataclass

from core.shared.constants import ENTITY_ACCIDENT, ENTITY_AUDITY, ENTITY_MU_INVESTIGATION
from core.shared.sluzby.finding_service import finding_service

# Cílové chování navigace pro ENTITY_ACCIDENT
ACCIDENT_OPEN_RECORD = "record"
ACCIDENT_OPEN_INVESTIGATION = "investigation"


@dataclass(frozen=True)
class SourceRoute:
    module_key: str
    opener: Callable[[object, int], None]


class SourceNavigator:
    def __init__(self):
        self._host = None
        self._routes: dict[str, SourceRoute] = {}
        self._register_default_routes()

    def configure(self, host) -> None:
        self._host = host

    def register(
        self,
        entity_type: str,
        module_key: str,
        opener: Callable[[object, int], None],
    ) -> None:
        self._routes[entity_type] = SourceRoute(module_key=module_key, opener=opener)

    def can_open(self, entity_type: str, entity_id: int | None) -> bool:
        if not isinstance(entity_id, int) or entity_id <= 0:
            return False
        if self._host is None:
            return False

        route = self._routes.get(entity_type)
        if route is None:
            return False

        return self._host._page_widgets.get(route.module_key) is not None

    def open(
        self,
        entity_type: str,
        entity_id: int,
        *,
        accident_target: str = ACCIDENT_OPEN_INVESTIGATION,
    ) -> bool:
        if self._host is None:
            return False

        route = self._routes.get(entity_type)
        if route is None:
            return False

        page = self._host._page_widgets.get(route.module_key)
        if page is None:
            return False

        self._host._show(route.module_key)
        if entity_type == ENTITY_ACCIDENT and accident_target == ACCIDENT_OPEN_RECORD:
            page.open_accident(entity_id)
        else:
            route.opener(page, entity_id)
        return True

    def open_finding(self, finding_id: int) -> bool:
        """
        Otevře zdrojový modul pro dané zjištění.

        Výběr konkrétního zjištění v dialogu zdroje zatím není implementován.
        """
        finding = finding_service.get_by_id(finding_id)
        if finding is None:
            return False

        return self.open(finding.entity_type, finding.entity_id)

    def _register_default_routes(self) -> None:
        self.register(
            ENTITY_AUDITY,
            "audity",
            lambda page, entity_id: page.open_audit(entity_id),
        )
        # Skutečné vyšetřování úrazu vede do Vyšetřování MU; administrativa zůstává v dialogu úrazu.
        self.register(
            ENTITY_ACCIDENT,
            "kniha_urazu",
            lambda page, entity_id: page.open_mu_investigation(entity_id),
        )
        self.register(
            ENTITY_MU_INVESTIGATION,
            "vysetrovani_mu",
            lambda page, entity_id: page.open_investigation(entity_id),
        )
        # Další typy: source_navigator.register(ENTITY_PROVERKY, "proverky", opener)


source_navigator = SourceNavigator()
