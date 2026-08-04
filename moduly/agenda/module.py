from core.modules.module_definition import ModuleDefinition
from moduly.agenda.constants import MODULE_KEY, MODULE_NAME
from moduly.agenda.ui.agenda_page import AgendaPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key=MODULE_KEY,
        name=MODULE_NAME,
        description="Společný přehled úkolů a událostí.",
        page_factory=AgendaPage,
        enabled=True,
    )
