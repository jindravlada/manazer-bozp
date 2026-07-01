from core.modules.module_definition import ModuleDefinition
from moduly.audity.constants import MODULE_DESCRIPTION, MODULE_KEY, MODULE_NAME
from moduly.audity.ui.audity_page import AudityPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key=MODULE_KEY,
        name=MODULE_NAME,
        description=MODULE_DESCRIPTION,
        page_factory=AudityPage,
        enabled=True,
    )
