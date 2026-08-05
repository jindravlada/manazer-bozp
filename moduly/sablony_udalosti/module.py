from core.modules.module_definition import ModuleDefinition
from moduly.sablony_udalosti.constants import MODULE_KEY, MODULE_NAME
from moduly.schuzky.ui.meeting_templates_page import MeetingTemplatesPage


def get_module_definition() -> ModuleDefinition:
    return ModuleDefinition(
        key=MODULE_KEY,
        name=MODULE_NAME,
        description="Správa šablon pro opakované zakládání událostí.",
        page_factory=MeetingTemplatesPage,
        enabled=True,
    )
