from __future__ import annotations

import html
import logging
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from core.export import OdtExportEngine, OdtParagraph, OdtRichContent, open_export_file
from core.services.storage_service import storage_service
from moduly.kniha_urazu.sluzby.accident_export_context_service import (
    AccidentExportContext,
    accident_export_context_service,
)

logger = logging.getLogger(__name__)

_ADDITIONAL_EMPLOYER_FIELDS = (
    ("Název", "dalsi_zamestnavatel_nazev"),
    ("IČO", "dalsi_zamestnavatel_ico"),
    ("Adresa", "dalsi_zamestnavatel_adresa"),
    ("Hlavní/ekonomická činnost", "dalsi_zamestnavatel_cinnost"),
)
_ADDITIONAL_EMPLOYER_HEADING = (
    "Další zaměstnavatel / subjekt, na jehož pracovišti došlo k úrazu"
)

# SHA-256 známých neupravených výchozích šablon Výpisu (před UX2).
_KNOWN_OLD_DEFAULT_SHA256 = frozenset(
    {
        "f3a749298dea6271f0543f5f82bcf286248a997ffe4fc5d21141d83eddf69a27",  # 6005ad4
        "22b71c1bebbd30338d3f5a1264e776c23bd8e83ea21d6870ddfbbe1a860ea45f",  # 265f190 UX1
    }
)

ConfirmReplaceCustom = Callable[[], bool]


@dataclass
class VypisTemplateResolution:
    """Výsledek výběru šablony Výpisu o pracovním úrazu."""

    path: Path
    bundled_path: Path
    sha256: str
    action: str
    backup_path: Path | None = None
    custom: bool = False


class VypisUrazuService:
    """Vygenerování interního výpisu o pracovním úrazu podle vybraného úrazu."""

    TEMPLATE_NAME = "VypisPracovniUraz.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "vypisy"
    TEMPLATE_BACKUP_SUBDIR = "sablony"

    def __init__(self):
        self.engine = OdtExportEngine()
        self.last_template_resolution: VypisTemplateResolution | None = None

    def template_path(self, *, confirm_replace_custom: ConfirmReplaceCustom | bool | None = None) -> Path:
        """
        Pracovní kopie v ~/.local/share/manazer-bozp/templates/exporty/.

        Bundled šablona (zdroje / AppImage ``_MEIPASS``) má přednost jen jako
        zdroj obnovy. Export vždy čte pracovní kopii. Neupravenou známou starou
        výchozí kopii nahradí aktuální výchozí; uživatelskou úpravu nepřepíše
        bez potvrzení.
        """
        return self.prepare_template(confirm_replace_custom=confirm_replace_custom).path

    def prepare_template(
        self,
        *,
        confirm_replace_custom: ConfirmReplaceCustom | bool | None = None,
    ) -> VypisTemplateResolution:
        storage_service.ensure_structure()
        user_path = storage_service.template_file(self.TEMPLATE_SUBDIR, self.TEMPLATE_NAME)
        bundled = storage_service.bundled_template_file(self.TEMPLATE_SUBDIR, self.TEMPLATE_NAME)
        if bundled is None or not bundled.exists():
            raise FileNotFoundError(
                f"Výchozí šablona výpisu nebyla nalezena: {self.TEMPLATE_SUBDIR}/{self.TEMPLATE_NAME}"
            )

        user_path.parent.mkdir(parents=True, exist_ok=True)
        bundled_hash = storage_service._file_sha256(bundled)
        meta_path = storage_service._template_bundle_hash_path(user_path)

        if not user_path.exists():
            shutil.copy2(bundled, user_path)
            storage_service._write_template_bundle_hash(user_path, bundled_hash)
            resolution = VypisTemplateResolution(
                path=user_path,
                bundled_path=bundled,
                sha256=bundled_hash,
                action="copied_default",
            )
            return self._remember_template(resolution)

        user_hash = storage_service._file_sha256(user_path)
        recorded = meta_path.read_text(encoding="utf-8").strip() if meta_path.exists() else ""

        if user_hash == bundled_hash:
            if recorded != bundled_hash:
                storage_service._write_template_bundle_hash(user_path, bundled_hash)
            resolution = VypisTemplateResolution(
                path=user_path,
                bundled_path=bundled,
                sha256=user_hash,
                action="already_current",
            )
            return self._remember_template(resolution)

        unmodified_previous = bool(recorded) and user_hash == recorded
        known_old_default = user_hash in _KNOWN_OLD_DEFAULT_SHA256
        if known_old_default or unmodified_previous:
            backup_path = self._backup_user_template(user_path)
            shutil.copy2(bundled, user_path)
            storage_service._write_template_bundle_hash(user_path, bundled_hash)
            resolution = VypisTemplateResolution(
                path=user_path,
                bundled_path=bundled,
                sha256=bundled_hash,
                action="updated_known_default",
                backup_path=backup_path,
            )
            return self._remember_template(resolution)

        replace = self._should_replace_custom(confirm_replace_custom)
        if replace:
            backup_path = self._backup_user_template(user_path)
            shutil.copy2(bundled, user_path)
            storage_service._write_template_bundle_hash(user_path, bundled_hash)
            resolution = VypisTemplateResolution(
                path=user_path,
                bundled_path=bundled,
                sha256=bundled_hash,
                action="replaced_custom",
                backup_path=backup_path,
                custom=True,
            )
            return self._remember_template(resolution)

        resolution = VypisTemplateResolution(
            path=user_path,
            bundled_path=bundled,
            sha256=user_hash,
            action="kept_custom",
            custom=True,
        )
        return self._remember_template(resolution)

    def generate_for_accident(
        self,
        accident,
        *,
        confirm_replace_custom: ConfirmReplaceCustom | bool | None = None,
    ) -> Path:
        if accident is None or not getattr(accident, "id", None):
            raise ValueError("Není vybraný uložený úraz.")

        resolution = self.prepare_template(confirm_replace_custom=confirm_replace_custom)
        template = resolution.path
        if not template.exists():
            raise FileNotFoundError(f"Šablona výpisu nebyla nalezena: {template}")

        context = accident_export_context_service.build(accident)
        data = context.merged_data()
        values = self._placeholder_values(accident, context, data)

        output_path = storage_service.export_file(self.EXPORT_SUBDIR, self._output_filename(accident))
        return self.engine.render(template, output_path, values)

    def open_for_accident(
        self,
        accident,
        *,
        confirm_replace_custom: ConfirmReplaceCustom | bool | None = None,
    ) -> Path:
        path = self.generate_for_accident(
            accident,
            confirm_replace_custom=confirm_replace_custom,
        )
        open_export_file(path, title="Výpis pracovního úrazu")
        return path

    def _remember_template(self, resolution: VypisTemplateResolution) -> VypisTemplateResolution:
        self.last_template_resolution = resolution
        logger.info(
            "Výpis o pracovním úrazu: šablona path=%s sha256=%s bundled=%s akce=%s",
            resolution.path,
            resolution.sha256,
            resolution.bundled_path,
            resolution.action,
        )
        return resolution

    def _backup_user_template(self, user_path: Path) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = storage_service.backups_dir / self.TEMPLATE_BACKUP_SUBDIR
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"VypisPracovniUraz-{stamp}.odt"
        shutil.copy2(user_path, backup_path)
        return backup_path

    @staticmethod
    def _should_replace_custom(confirm_replace_custom: ConfirmReplaceCustom | bool | None) -> bool:
        if confirm_replace_custom is True:
            return True
        if confirm_replace_custom is False or confirm_replace_custom is None:
            return False
        return bool(confirm_replace_custom())

    def _output_filename(self, accident) -> str:
        number = str(getattr(accident, "number", "") or "bez-cisla").replace("/", "-").replace("\\", "-")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"VypisPracovniUraz-{number}_{stamp}.odt"

    def _fmt_date(self, value) -> str:
        if not value:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y")
        if isinstance(value, date):
            return value.strftime("%d.%m.%Y")
        text = str(value).strip()
        if not text:
            return ""
        try:
            return datetime.fromisoformat(text).strftime("%d.%m.%Y")
        except Exception:
            return text

    def _fmt_datetime_text(self, day, time_text="") -> str:
        day_text = self._fmt_date(day)
        time_text = str(time_text or "").strip()
        if day_text and time_text:
            return f"{day_text} {time_text}"
        return day_text or time_text

    def _accident_attr(self, accident, name, default=""):
        return getattr(accident, name, default) or default

    def _format_mnozstvi_alkohol(self, value) -> str:
        from moduly.kniha_urazu.sluzby.breath_alcohol import format_breath_alcohol_for_export

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            cleaned = str(value)
        else:
            cleaned = self._filled_display_value(value)
        if cleaned is None:
            return ""
        return format_breath_alcohol_for_export(cleaned)

    def _text_block(self, value) -> str:
        text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
        return text.strip()

    def _filled_text(self, value) -> str:
        return self._text_block(value)

    @staticmethod
    def _filled_display_value(value) -> str | None:
        """Vrátí zobrazený text, nebo None pokud je hodnota prázdná / technická mezera."""
        if value is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        text = str(value)
        text = html.unescape(html.unescape(text))
        text = (
            text.replace("\xa0", " ")
            .replace("\u200b", "")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
        )
        text = text.replace("&#x20;", " ").replace("&#32;", " ").replace("&nbsp;", " ")
        text = text.strip()
        if not text:
            return None
        if text.lower() in {"&#x20;", "&#32;", "&nbsp;"}:
            return None
        return text

    def _join_nonempty(self, lines) -> str:
        return "\n".join(str(line).strip() for line in lines if str(line or "").strip())

    def _contact_line(self, accident) -> str:
        combined = self._filled_text(self._accident_attr(accident, "telefon_email"))
        if combined:
            return combined

        telefon = (
            self._filled_text(self._accident_attr(accident, "telefon"))
            or self._filled_text(self._accident_attr(accident, "zamestnanec_telefon"))
        )
        email = (
            self._filled_text(self._accident_attr(accident, "email"))
            or self._filled_text(self._accident_attr(accident, "zamestnanec_email"))
        )

        parts = [part for part in (telefon, email) if part]
        return " / ".join(parts)

    def _delivery_address(self, accident) -> str:
        address = self._text_block(self._accident_attr(accident, "adresa_dorucovani"))
        if not address:
            return ""
        stay = self._text_block(self._accident_attr(accident, "adresa_pobytu"))
        if stay and address == stay:
            return ""
        return address

    def _witness_lines(self, accident) -> str:
        value = self._accident_attr(accident, "svedci")
        if not value:
            return "Nejsou"

        if isinstance(value, (list, tuple, set)):
            lines = [str(item).strip() for item in value if str(item or "").strip()]
            return "\n".join(lines) if lines else "Nejsou"

        text = str(value).strip()
        if not text or text == "Nebyl zjištěn žádný svědek":
            return "Nejsou"

        lines = [part.strip() for part in text.split(";") if part.strip()]
        return "\n".join(lines) if lines else "Nejsou"

    def _additional_employer_fields(self, accident) -> list[tuple[str, str]]:
        filled: list[tuple[str, str]] = []
        for label, attr in _ADDITIONAL_EMPLOYER_FIELDS:
            value = self._filled_text(self._accident_attr(accident, attr))
            if value:
                filled.append((label, value))
        return filled

    def additional_employer_is_present(self, accident) -> bool:
        return bool(self._additional_employer_fields(accident))

    def _additional_employer_section(self, accident) -> OdtRichContent:
        filled = self._additional_employer_fields(accident)
        if not filled:
            return OdtRichContent(paragraphs=[], omit_when_empty=True)
        body = "\n".join(f"{label}: {value}" for label, value in filled)
        return OdtRichContent(
            paragraphs=[
                OdtParagraph.text(_ADDITIONAL_EMPLOYER_HEADING, style="Heading_20_2"),
                OdtParagraph.text(body),
            ]
        )

    def _control_rows(self, accident) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []

        def add(label: str, value) -> None:
            text = self._filled_display_value(value)
            if text is None:
                return
            rows.append((label, text))

        add("Kontrola přítomnosti alkoholu", getattr(accident, "kontrola_alkohol", None))
        add("Výsledek kontroly", getattr(accident, "vysledek_kontroly_alkohol", None))
        alcohol_amount = self._format_mnozstvi_alkohol(getattr(accident, "mnozstvi_alkohol", None))
        if alcohol_amount:
            rows.append(("Množství alkoholu", alcohol_amount))
        add(
            "Důvod neprovedení kontroly alkoholu",
            getattr(accident, "kontrola_alkohol_duvod_neprovedeni", None),
        )
        add("Kontrola návykových látek", getattr(accident, "kontrola_navykove_latky", None))
        add("Výsledek kontroly", getattr(accident, "vysledek_kontroly_navykove_latky", None))
        add("Zjištěné látky", getattr(accident, "navykove_latky_popis", None))
        add(
            "Důvod neprovedení kontroly návykových látek",
            getattr(accident, "kontrola_navykove_latky_duvod_neprovedeni", None),
        )
        return rows

    def _control_section(self, accident) -> OdtRichContent:
        rows = self._control_rows(accident)
        if not rows:
            return OdtRichContent(paragraphs=[], omit_when_empty=True)
        body = "Kontrola\n" + "\n".join(f"{label}: {value}" for label, value in rows)
        return OdtRichContent(paragraphs=[OdtParagraph.text(body)])

    def _measures_text(self, accident) -> str:
        try:
            return self._text_block(
                self._accident_attr(accident, "opatreni")
                or self._accident_attr(accident, "measures_summary")
            )
        except Exception:
            return ""

    def _placeholder_values(self, accident, context: AccidentExportContext, data: dict) -> dict:
        svedci = context.witness_lines(accident)
        if svedci is None:
            svedci = self._witness_lines(accident)

        popis_deje = (
            context.oznameni_value("oznameni_popis")
            or self._accident_attr(accident, "popis_urazoveho_deje")
            or self._accident_attr(accident, "description")
        )

        return {
            "cislo_urazu": self._accident_attr(accident, "number"),
            "podatel_jmeno": self._accident_attr(accident, "podatel_jmeno"),
            "podatel_email": self._accident_attr(accident, "podatel_email"),
            "podatel_telefon": self._accident_attr(accident, "podatel_telefon"),
            "podatel_pracovni_zarazeni": self._accident_attr(accident, "podatel_pracovni_zarazeni"),
            "zamestnavatel_nazev": self._accident_attr(accident, "zamestnavatel_nazev"),
            "zamestnavatel_ico": self._accident_attr(accident, "zamestnavatel_ico"),
            "vrchni_dozor": self._accident_attr(accident, "vrchni_dozor"),
            "zamestnavatel_adresa": self._text_block(self._accident_attr(accident, "zamestnavatel_adresa")),
            "dalsi_zamestnavatel_sekce": self._additional_employer_section(accident),
            "zamestnanec": getattr(accident, "employee_name", "") or self._accident_attr(accident, "jmeno_prijmeni"),
            "pohlavi": self._accident_attr(accident, "pohlavi"),
            "datum_narozeni": self._fmt_date(self._accident_attr(accident, "datum_narozeni")),
            "osobni_cislo": self._accident_attr(accident, "osobni_cislo"),
            "statni_obcanstvi": self._accident_attr(accident, "statni_obcanstvi"),
            "adresa_pobytu": self._text_block(self._accident_attr(accident, "adresa_pobytu")),
            "adresa_dorucovani": self._delivery_address(accident),
            "telefon_email": self._contact_line(accident),
            "zdravotni_pojistovna": self._accident_attr(accident, "zdravotni_pojistovna"),
            "vztah_k_zamestnavateli": self._join_nonempty([self._accident_attr(accident, "vztah_k_zamestnavateli"), self._accident_attr(accident, "vztah_k_zamestnavateli_detail")]),
            "den_vzniku_pravniho_vztahu": self._fmt_date(self._accident_attr(accident, "den_vzniku_pravniho_vztahu")),
            "druh_vykonavane_prace": self._accident_attr(accident, "druh_vykonavane_prace") or self._accident_attr(accident, "cz_isco_nazev"),
            "druh_urazu": self._accident_attr(accident, "druh_urazu"),
            "podezreni_trestny_cin": self._accident_attr(accident, "podezreni_trestny_cin"),
            "datum_a_cas_urazu": self._fmt_datetime_text(self._accident_attr(accident, "accident_date"), self._accident_attr(accident, "accident_time")),
            "druh_zraneni": self._text_block(self._accident_attr(accident, "druh_zraneni") or self._accident_attr(accident, "injury_type")),
            "zranena_cast_tela": self._text_block(self._accident_attr(accident, "zranena_cast_tela") or self._accident_attr(accident, "injured_body_part")),
            "celkovy_pocet_zranenych": self._accident_attr(accident, "celkovy_pocet_zranenych"),
            "hromadny_uraz": self._accident_attr(accident, "hromadny_uraz"),
            "cinnost_pri_urazu": self._accident_attr(accident, "cinnost_pri_urazu"),
            "misto_urazu": self._text_block(self._accident_attr(accident, "misto_urazu")),
            "popis_urazoveho_deje": self._text_block(popis_deje),
            "charakteristika_pracoviste": self._text_block(self._accident_attr(accident, "charakteristika_pracoviste")),
            "zdroj_urazu": self._text_block(self._accident_attr(accident, "zdroj_urazu")),
            "pricina_urazu": self._text_block(self._accident_attr(accident, "pricina_urazu")),
            "uraz_pracoviste_zamestnavatele": self._accident_attr(accident, "uraz_pracoviste_zamestnavatele"),
            "kontrola_sekce": self._control_section(accident),
            "kontrola_alkohol": self._filled_display_value(getattr(accident, "kontrola_alkohol", None)) or "",
            "vysledek_kontroly_alkohol": self._filled_display_value(getattr(accident, "vysledek_kontroly_alkohol", None)) or "",
            "mnozstvi_alkohol": self._format_mnozstvi_alkohol(getattr(accident, "mnozstvi_alkohol", None)),
            "kontrola_alkohol_duvod_neprovedeni": self._filled_display_value(
                getattr(accident, "kontrola_alkohol_duvod_neprovedeni", None)
            )
            or "",
            "kontrola_navykove_latky": self._filled_display_value(
                getattr(accident, "kontrola_navykove_latky", None)
            )
            or "",
            "vysledek_kontroly_navykove_latky": self._filled_display_value(
                getattr(accident, "vysledek_kontroly_navykove_latky", None)
            )
            or "",
            "navykove_latky_popis": self._filled_display_value(getattr(accident, "navykove_latky_popis", None)) or "",
            "kontrola_navykove_latky_duvod_neprovedeni": self._filled_display_value(
                getattr(accident, "kontrola_navykove_latky_duvod_neprovedeni", None)
            )
            or "",
            "porusene_predpisy": self._text_block(self._accident_attr(accident, "porusene_predpisy") or data.get("dodrz_poruseni_predpisu", "")),
            "opatreni": self._measures_text(accident),
            "svedci": svedci,
            "zapsal_jmeno": self._accident_attr(accident, "zapsal_jmeno"),
            "zapsal_pracovni_zarazeni": self._accident_attr(accident, "zapsal_pracovni_zarazeni"),
        }


vypis_urazu_service = VypisUrazuService()
