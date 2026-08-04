from core.modules.module_definition import ModuleDefinition
from moduly.schuzky.constants import MODULE_KEY, MODULE_NAME
from moduly.schuzky.ui.schuzky_page import SchuzkyPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key=MODULE_KEY,
        name=MODULE_NAME,
        description="Evidence událostí jako samostatných záznamů.",
        page_factory=SchuzkyPage,
        enabled=True,
    )
