import json
import subprocess
from datetime import date, datetime
from pathlib import Path

from core.export import OdtExportEngine
from core.services.storage_service import storage_service
from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
from moduly.ukoly.sluzby.task_service import task_service


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
        return storage_service.template_file(self.TEMPLATE_SUBDIR, self.TEMPLATE_NAME)

    def generate_for_accident(self, accident) -> Path:
        if accident is None or not getattr(accident, "id", None):
            raise ValueError("Není vybraný uložený úraz.")

        template = self.template_path()
        if not template.exists():
            raise FileNotFoundError(f"Šablona výpisu nebyla nalezena: {template}")

        investigation = investigation_service.get_or_create(accident.id)
        data = self._investigation_json(investigation)
        values = self._placeholder_values(accident, investigation, data)

        output_path = storage_service.export_file(self.EXPORT_SUBDIR, self._output_filename(accident))
        return self.engine.render(template, output_path, values)

    def open_for_accident(self, accident) -> Path:
        path = self.generate_for_accident(accident)
        subprocess.Popen(["xdg-open", str(path)])
        return path

    def _investigation_json(self, investigation) -> dict:
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or "{}"
        try:
            return json.loads(raw)
        except Exception:
            return {}

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

    def _task_lines(self, accident_id: int) -> str:
        try:
            tasks = [
                task for task in task_service.get_all_tasks()
                if getattr(task, "source_module", "") == "accident" and getattr(task, "source_record_id", None) == accident_id
            ]
        except Exception:
            tasks = []

        if not tasks:
            return ""

        lines = []
        for task in tasks:
            due = self._fmt_date(getattr(task, "due_date", None))
            done = self._fmt_date(getattr(task, "completed_date", None)) or ("ANO" if getattr(task, "completed", False) else "NE")
            parts = [getattr(task, "title", "") or "Opatření"]
            if getattr(task, "responsible_person", ""):
                parts.append(f"odpovídá: {task.responsible_person}")
            if due:
                parts.append(f"termín: {due}")
            parts.append(f"splněno: {done}")
            if getattr(task, "note", ""):
                parts.append(f"poznámka: {task.note}")
            lines.append("• " + "; ".join(parts))
        return "\n".join(lines)

    def _join_nonempty(self, lines) -> str:
        return "\n".join(str(line).strip() for line in lines if str(line or "").strip())

    def _contact_line(self, accident) -> str:
        existing = self._accident_attr(accident, "telefon_email")
        if existing:
            return existing

        parts = [
            self._accident_attr(accident, "telefon"),
            self._accident_attr(accident, "email"),
            self._accident_attr(accident, "zamestnanec_telefon"),
            self._accident_attr(accident, "zamestnanec_email"),
        ]
        return " / ".join(str(part).strip() for part in parts if str(part or "").strip())

    def _delivery_address(self, accident) -> str:
        address = self._accident_attr(accident, "adresa_dorucovani")
        stay = self._accident_attr(accident, "adresa_pobytu")
        if address and stay and address.strip() == stay.strip():
            return ""
        return address

    def _witness_lines(self, accident) -> str:
        value = self._accident_attr(accident, "svedci")
        if not value:
            return "Nejsou"
        if isinstance(value, (list, tuple, set)):
            return self._join_nonempty(value) or "Nejsou"
        return str(value).strip() or "Nejsou"

    def _placeholder_values(self, accident, investigation, data: dict) -> dict:
        svedci = self._witness_lines(accident)
        opatreni = self._task_lines(accident.id) or self._accident_attr(accident, "opatreni") or self._accident_attr(accident, "measures_summary")
        if not opatreni:
            opatreni = "Nejsou evidována."

        stav_setreni = "Zahájeno"
        stanovisko = data.get("soulad_stanovisko_bozp", "")

        return {
            "cislo_urazu": self._accident_attr(accident, "number"),
            "podatel_jmeno": self._accident_attr(accident, "podatel_jmeno"),
            "podatel_email": self._accident_attr(accident, "podatel_email"),
            "podatel_telefon": self._accident_attr(accident, "podatel_telefon"),
            "podatel_pracovni_zarazeni": self._accident_attr(accident, "podatel_pracovni_zarazeni"),
            "zamestnavatel_nazev": self._accident_attr(accident, "zamestnavatel_nazev"),
            "zamestnavatel_ico": self._accident_attr(accident, "zamestnavatel_ico"),
            "vrchni_dozor": self._accident_attr(accident, "vrchni_dozor"),
            "zamestnavatel_adresa": self._accident_attr(accident, "zamestnavatel_adresa"),
            "hlavni_cinnost_zamestnavatele": self._accident_attr(accident, "hlavni_cinnost_zamestnavatele"),
            "dalsi_zamestnavatel_nazev": self._accident_attr(accident, "dalsi_zamestnavatel_nazev"),
            "dalsi_zamestnavatel_ico": self._accident_attr(accident, "dalsi_zamestnavatel_ico"),
            "dalsi_zamestnavatel_adresa": self._accident_attr(accident, "dalsi_zamestnavatel_adresa"),
            "dalsi_zamestnavatel_cinnost": self._accident_attr(accident, "dalsi_zamestnavatel_cinnost"),
            "zamestnanec": getattr(accident, "employee_name", "") or self._accident_attr(accident, "jmeno_prijmeni"),
            "pohlavi": self._accident_attr(accident, "pohlavi"),
            "datum_narozeni": self._fmt_date(self._accident_attr(accident, "datum_narozeni")),
            "osobni_cislo": self._accident_attr(accident, "osobni_cislo"),
            "statni_obcanstvi": self._accident_attr(accident, "statni_obcanstvi"),
            "adresa_pobytu": self._accident_attr(accident, "adresa_pobytu"),
            "adresa_dorucovani": self._delivery_address(accident),
            "telefon_email": self._contact_line(accident),
            "zdravotni_pojistovna": self._accident_attr(accident, "zdravotni_pojistovna"),
            "vztah_k_zamestnavateli": self._join_nonempty([self._accident_attr(accident, "vztah_k_zamestnavateli"), self._accident_attr(accident, "vztah_k_zamestnavateli_detail")]),
            "den_vzniku_pravniho_vztahu": self._fmt_date(self._accident_attr(accident, "den_vzniku_pravniho_vztahu")),
            "druh_vykonavane_prace": self._accident_attr(accident, "druh_vykonavane_prace") or self._accident_attr(accident, "cz_isco_nazev"),
            "druh_urazu": self._accident_attr(accident, "druh_urazu"),
            "podezreni_trestny_cin": self._accident_attr(accident, "podezreni_trestny_cin"),
            "datum_a_cas_urazu": self._fmt_datetime_text(self._accident_attr(accident, "accident_date"), self._accident_attr(accident, "accident_time")),
            "druh_zraneni": self._accident_attr(accident, "druh_zraneni") or self._accident_attr(accident, "injury_type"),
            "zranena_cast_tela": self._accident_attr(accident, "zranena_cast_tela") or self._accident_attr(accident, "injured_body_part"),
            "celkovy_pocet_zranenych": self._accident_attr(accident, "celkovy_pocet_zranenych"),
            "hromadny_uraz": self._accident_attr(accident, "hromadny_uraz"),
            "cinnost_pri_urazu": self._accident_attr(accident, "cinnost_pri_urazu"),
            "misto_urazu": self._accident_attr(accident, "misto_urazu"),
            "popis_urazoveho_deje": self._accident_attr(accident, "popis_urazoveho_deje") or self._accident_attr(accident, "description"),
            "charakteristika_pracoviste": self._accident_attr(accident, "charakteristika_pracoviste"),
            "zdroj_urazu": self._accident_attr(accident, "zdroj_urazu"),
            "pricina_urazu": self._accident_attr(accident, "pricina_urazu"),
            "uraz_pracoviste_zamestnavatele": self._accident_attr(accident, "uraz_pracoviste_zamestnavatele"),
            "subjekt_registrovan": self._accident_attr(accident, "subjekt_registrovan"),
            "adresa_sidla_subjektu": self._accident_attr(accident, "adresa_sidla_subjektu"),
            "ico_subjektu": self._accident_attr(accident, "ico_subjektu"),
            "ekonomicka_cinnost_subjektu": self._accident_attr(accident, "ekonomicka_cinnost_subjektu"),
            "ekonomicka_cinnost_pracoviste": self._accident_attr(accident, "ekonomicka_cinnost_pracoviste"),
            "adresa_pracoviste": self._accident_attr(accident, "adresa_pracoviste"),
            "okres_pracoviste": self._accident_attr(accident, "okres_pracoviste"),
            "stav_setreni": stav_setreni,
            "pripad_uzavren": "ANO" if getattr(accident, "closed", False) else "NE",
            "datum_zahajeni": self._fmt_date(getattr(accident, "investigation_started_at", None)),
            "datum_oznameni": self._fmt_date(getattr(investigation, "oznameni_datum", None)),
            "stanovisko_bozp": stanovisko,
            "kontrola_alkohol": self._accident_attr(accident, "kontrola_alkohol"),
            "vysledek_kontroly_alkohol": self._accident_attr(accident, "vysledek_kontroly_alkohol"),
            "mnozstvi_alkohol": self._accident_attr(accident, "mnozstvi_alkohol"),
            "kontrola_alkohol_duvod_neprovedeni": self._accident_attr(accident, "kontrola_alkohol_duvod_neprovedeni"),
            "kontrola_navykove_latky": self._accident_attr(accident, "kontrola_navykove_latky"),
            "vysledek_kontroly_navykove_latky": self._accident_attr(accident, "vysledek_kontroly_navykove_latky"),
            "navykove_latky_popis": self._accident_attr(accident, "navykove_latky_popis"),
            "kontrola_navykove_latky_duvod_neprovedeni": self._accident_attr(accident, "kontrola_navykove_latky_duvod_neprovedeni"),
            "porusene_predpisy": self._accident_attr(accident, "porusene_predpisy") or data.get("dodrz_poruseni_predpisu", ""),
            "opatreni": opatreni,
            "svedci": svedci,
            "zapsal_jmeno": self._accident_attr(accident, "zapsal_jmeno"),
            "zapsal_pracovni_zarazeni": self._accident_attr(accident, "zapsal_pracovni_zarazeni"),
            "datum_vytvoreni": datetime.now().strftime("%d.%m.%Y"),
        }



vypis_urazu_service = VypisUrazuService()
