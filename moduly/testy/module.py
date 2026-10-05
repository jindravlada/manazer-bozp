from core.modules.module_definition import ModuleDefinition
from moduly.testy.constants import MODULE_DESCRIPTION, MODULE_KEY, MODULE_NAME
from moduly.testy.ui.testy_page import TestyPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key=MODULE_KEY,
        name=MODULE_NAME,
        description=MODULE_DESCRIPTION,
        page_factory=TestyPage,
        enabled=True,
    )
