from core.modules.module_definition import ModuleDefinition
from moduly.smlouvy_ozo.constants import (
    MODULE_DESCRIPTION,
    MODULE_KEY,
    MODULE_NAME,
)
from moduly.smlouvy_ozo.ui.smlouvy_ozo_page import SmlouvyOzoPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key=MODULE_KEY,
        name=MODULE_NAME,
        description=MODULE_DESCRIPTION,
        page_factory=SmlouvyOzoPage,
        enabled=True,
    )
