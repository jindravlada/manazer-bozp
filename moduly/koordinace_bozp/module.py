from core.modules.module_definition import ModuleDefinition
from moduly.koordinace_bozp.constants import (
    MODULE_DESCRIPTION,
    MODULE_KEY,
    MODULE_NAME,
)
from moduly.koordinace_bozp.ui.koordinace_bozp_page import KoordinaceBozpPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key=MODULE_KEY,
        name=MODULE_NAME,
        description=MODULE_DESCRIPTION,
        page_factory=KoordinaceBozpPage,
        enabled=True,
    )
