from core.modules.module_definition import ModuleDefinition
from moduly.kniha_urazu.ui.kniha_urazu_page import KnihaUrazuPage


def get_module_definition():
    return ModuleDefinition(
        key="kniha_urazu",
        name="Kniha úrazů",
        description="Evidence pracovních úrazů",
        page_factory=KnihaUrazuPage,
        enabled=True,
    )
