from core.modules.module_definition import ModuleDefinition
from moduly.proverky.constants import MODULE_DESCRIPTION, MODULE_KEY, MODULE_NAME
from moduly.proverky.ui.proverky_page import ProverkyPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key=MODULE_KEY,
        name=MODULE_NAME,
        description=MODULE_DESCRIPTION,
        page_factory=ProverkyPage,
        enabled=True,
    )
