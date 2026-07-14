from core.modules.module_definition import ModuleDefinition
from moduly.rizeni_rizik.constants import MODULE_DESCRIPTION, MODULE_KEY, MODULE_NAME
from moduly.rizeni_rizik.ui.rizeni_rizik_page import RizeniRizikPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key=MODULE_KEY,
        name=MODULE_NAME,
        description=MODULE_DESCRIPTION,
        page_factory=RizeniRizikPage,
        enabled=True,
    )
