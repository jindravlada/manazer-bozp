from datetime import date, datetime
from pathlib import Path

from core.export import OdtExportEngine, OdtParagraph, OdtRichContent, open_export_file
from core.services.storage_service import storage_service
from moduly.kniha_urazu.sluzby.accident_export_context_service import (
    AccidentExportContext,
    accident_export_context_service,
)

_ADDITIONAL_EMPLOYER_FIELDS = (
    ("Název", "dalsi_zamestnavatel_nazev"),
    ("IČO", "dalsi_zamestnavatel_ico"),
    ("Adresa", "dalsi_zamestnavatel_adresa"),
    ("Hlavní/ekonomická činnost", "dalsi_zamestnavatel_cinnost"),
)
_ADDITIONAL_EMPLOYER_HEADING = (
    "Další zaměstnavatel / subjekt, na jehož pracovišti došlo k úrazu"
)


class VypisUrazuService:
    """Vygenerování interního výpisu o pracovním úrazu podle vybraného úrazu."""

    TEMPLATE_NAME = "VypisPracovniUraz.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "vypisy"

    def __init__(self):
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        """
        Šablona z ~/.local/share/manazer-bozp/templates/exporty/.
        StorageService při startu zkopíruje výchozí šablonu z projektu, pokud v .local chybí.
        """
        storage_service.ensure_structure()
        return storage_service.resolve_editable_template(self.TEMPLATE_SUBDIR, self.TEMPLATE_NAME)

    def generate_for_accident(self, accident) -> Path:
        if accident is None or not getattr(accident, "id", None):
            raise ValueError("Není vybraný uložený úraz.")

        template = self.template_path()
        if not template.exists():
            raise FileNotFoundError(f"Šablona výpisu nebyla nalezena: {template}")

        context = accident_export_context_service.build(accident)
        data = context.merged_data()
        values = self._placeholder_values(accident, context, data)

        output_path = storage_service.export_file(self.EXPORT_SUBDIR, self._output_filename(accident))
        return self.engine.render(template, output_path, values)

    def open_for_accident(self, accident) -> Path:
        path = self.generate_for_accident(accident)
        open_export_file(path, title="Výpis pracovního úrazu")
        return path

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

        return format_breath_alcohol_for_export(str(value or ""))

    def _text_block(self, value) -> str:
        text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
        return text.strip()

    def _filled_text(self, value) -> str:
        return self._text_block(value)

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
            "kontrola_alkohol": self._accident_attr(accident, "kontrola_alkohol"),
            "vysledek_kontroly_alkohol": self._accident_attr(accident, "vysledek_kontroly_alkohol"),
            "mnozstvi_alkohol": self._format_mnozstvi_alkohol(
                self._accident_attr(accident, "mnozstvi_alkohol")
            ),
            "kontrola_alkohol_duvod_neprovedeni": self._text_block(self._accident_attr(accident, "kontrola_alkohol_duvod_neprovedeni")),
            "kontrola_navykove_latky": self._accident_attr(accident, "kontrola_navykove_latky"),
            "vysledek_kontroly_navykove_latky": self._accident_attr(accident, "vysledek_kontroly_navykove_latky"),
            "navykove_latky_popis": self._text_block(self._accident_attr(accident, "navykove_latky_popis")),
            "kontrola_navykove_latky_duvod_neprovedeni": self._text_block(self._accident_attr(accident, "kontrola_navykove_latky_duvod_neprovedeni")),
            "porusene_predpisy": self._text_block(self._accident_attr(accident, "porusene_predpisy") or data.get("dodrz_poruseni_predpisu", "")),
            "opatreni": self._measures_text(accident),
            "svedci": svedci,
            "zapsal_jmeno": self._accident_attr(accident, "zapsal_jmeno"),
            "zapsal_pracovni_zarazeni": self._accident_attr(accident, "zapsal_pracovni_zarazeni"),
        }



vypis_urazu_service = VypisUrazuService()
