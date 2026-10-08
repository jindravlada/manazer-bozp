"""Dialog přehledů vypořádání zjištění z dokončených prověrek BOZP."""

from __future__ import annotations

from core.shared.constants import SETTLEMENT_SOURCE_PROVERKY
from moduly.audity.ui.prehled_vyporadani_dialog import (
    PrehledVyporadaniDialog,
    SettlementOverviewProfile,
)
from moduly.proverky.constants import MODULE_NAME, SETTLEMENT_OVERVIEW_DIALOG_TITLE
from moduly.proverky.sluzby.prehled_vyporadani_export_service import (
    inspection_scope_warning,
    prehled_vyporadani_proverky_export_service,
)

_IMMUTABLE_CONFIRMATION = (
    "Přehled bude uložen jako neměnný historický snímek.\n"
    "Pozdější úpravy zjištění, úkolů ani prověrek tento přehled nezmění."
)

PROVERKY_SETTLEMENT_PROFILE = SettlementOverviewProfile(
    source_type=SETTLEMENT_SOURCE_PROVERKY,
    module_name=MODULE_NAME,
    dialog_title=SETTLEMENT_OVERVIEW_DIALOG_TITLE,
    record_column="Prověrka",
    confirmation=_IMMUTABLE_CONFIRMATION,
    scope_warning=inspection_scope_warning,
    export_service=prehled_vyporadani_proverky_export_service,
    plain_reference=True,
)


class PrehledVyporadaniProverkyDialog(PrehledVyporadaniDialog):
    def __init__(self, parent=None):
        super().__init__(parent, profile=PROVERKY_SETTLEMENT_PROFILE)
