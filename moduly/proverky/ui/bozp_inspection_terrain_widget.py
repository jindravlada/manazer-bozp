"""Záložka Terén — stejný editor jako Kontrolované oblasti + tisk checklistu."""

from moduly.proverky.constants import VERIFICATION_TYPE_TERRAIN
from moduly.proverky.ui.bozp_inspection_areas_widget import BozpInspectionAreasWidget


class BozpInspectionTerrainWidget(BozpInspectionAreasWidget):
    """Tenký obal pro zpětnou kompatibilitu importů a testů."""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            verification_type=VERIFICATION_TYPE_TERRAIN,
            show_checklist_button=True,
        )

    @property
    def verification_type_changed(self):
        return self.knowledge_widget.section_widget.verification_type_changed
