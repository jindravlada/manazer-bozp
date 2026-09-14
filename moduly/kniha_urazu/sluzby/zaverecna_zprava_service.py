import html
import os
import zipfile
from datetime import date, datetime
from pathlib import Path

from core.export import open_export_file
from core.export.odt_engine import (
    _sync_written_file,
    is_active_odt_zip_entry,
    strip_active_odt_manifest_entries,
)

from core.services.attachment_service import attachment_service
from core.services.storage_service import storage_service
from moduly.kniha_urazu.sluzby.accident_export_context_service import (
    AccidentExportContext,
    accident_export_context_service,
)


class ZaverecnaZpravaService:
    """Vygenerování závěrečné zprávy ze šablony ODT podle vybraného úrazu."""

    TEMPLATE_NAME = "ZaverecnaZprava.odt"

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        user_template = storage_service.templates_dir / "setreni" / self.TEMPLATE_NAME
        if user_template.exists():
            return user_template
        return storage_service.bundled_templates_dir() / "setreni" / self.TEMPLATE_NAME

    def generate_for_accident(self, accident) -> Path:
        if accident is None or not getattr(accident, "id", None):
            raise ValueError("Není vybraný uložený úraz.")

        template = self.template_path()
        if not template.exists():
            raise FileNotFoundError(f"Šablona závěrečné zprávy nebyla nalezena: {template}")

        context = accident_export_context_service.build(accident)
        data = context.merged_data()
        values = self._placeholder_values(accident, context, data)

        exports_dir = storage_service.exports_dir / "zaverecne_zpravy"
        exports_dir.mkdir(parents=True, exist_ok=True)
        output_name = self._output_filename(accident)
        tmp_output = exports_dir / output_name

        self._fill_odt_template(template, tmp_output, values)

        attachment = attachment_service.add_file_as("accident", accident.id, str(tmp_output), output_name)
        if attachment is not None:
            attachment_path = attachment_service.resolve_path(attachment)
            return attachment_path.resolve()
        return tmp_output.resolve()

    def open_for_accident(self, accident) -> Path:
        path = self.generate_for_accident(accident)
        open_export_file(path, title="Závěrečná zpráva")
        return path

    def _output_filename(self, accident) -> str:
        number = str(getattr(accident, "number", "") or "bez-cisla").replace("/", "-").replace("\\", "-")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"ZaverecnaZprava-{number}_{stamp}.odt"

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

    def _join_nonempty(self, lines) -> str:
        return "\n".join(str(line).strip() for line in lines if str(line or "").strip())

    def _accident_attr(self, accident, name, default=""):
        return getattr(accident, name, default) or default

    def _task_lines(self, context: AccidentExportContext) -> str:
        try:
            tasks = context.collect_tasks()
        except Exception:
            tasks = []

        if not tasks:
            return ""

        lines = []
        for task in tasks:
            due = self._fmt_date(getattr(task, "due_date", None))
            completed = self._fmt_date(getattr(task, "completed_date", None)) or (
                "NE" if not getattr(task, "completed", False) else ""
            )
            parts = [getattr(task, "title", "") or "Opatření"]
            if getattr(task, "responsible_person", ""):
                parts.append(f"odpovídá: {task.responsible_person}")
            if due:
                parts.append(f"termín: {due}")
            if completed:
                parts.append(f"splněno: {completed}")
            if getattr(task, "note", ""):
                parts.append(f"poznámka: {task.note}")
            lines.append("- " + "; ".join(parts))
        return "\n".join(lines)

    def _placeholder_values(self, accident, context: AccidentExportContext, data: dict) -> dict:
        datum_a_cas_urazu = self._fmt_datetime_text(
            self._accident_attr(accident, "accident_date"),
            self._accident_attr(accident, "accident_time"),
        )
        datum_oznameni = self._fmt_date(context.oznameni_value("oznameni_datum"))
        datum_zahajeni = self._fmt_date(context.investigation_started_at(accident))
        datum_ukonceni = self._fmt_date(context.investigation_closed_at())

        pracoviste = self._accident_attr(accident, "workplace_name") or self._accident_attr(accident, "pracoviste")
        lokalita = self._join_nonempty([
            pracoviste,
            self._accident_attr(accident, "adresa_pracoviste"),
            self._accident_attr(accident, "okres_pracoviste"),
        ])

        vysledky = self._join_nonempty([
            data.get("analyza_shrnuti_skutecneho_stavu"),
            data.get("analyza_zjistene_skutecnosti"),
            data.get("soulad_vyhodnoceni"),
            data.get("soulad_oduvodneni"),
        ])

        dalsi_zjisteni = self._join_nonempty([
            data.get("analyza_prvotni_pricina"),
            data.get("analyza_poznamka_bozp"),
            data.get("ohledani_popis_mista"),
            data.get("dodrz_poruseni_predpisu"),
            data.get("dodrz_ostatni_1"),
            data.get("dodrz_ostatni_2"),
            context.chronologie_summary(),
            context.immediate_measures_summary(),
        ])

        poruseni = self._join_nonempty([
            self._accident_attr(accident, "porusene_predpisy"),
            data.get("dodrz_poruseni_predpisu"),
        ])

        opatreni = (
            self._task_lines(context)
            or self._accident_attr(accident, "opatreni")
            or self._accident_attr(accident, "measures_summary")
        )

        zpracoval = context.investigator_name()

        zaver = self._join_nonempty([
            context.mu_investigation.conclusion if context.has_mu and context.mu_investigation else "",
            data.get("soulad_stanovisko_bozp"),
            data.get("soulad_oduvodneni"),
        ])

        return {
            "cislo_urazu": self._accident_attr(accident, "number"),
            "datum_a_cas_urazu": datum_a_cas_urazu,
            "datum_oznameni": datum_oznameni,
            "datum_zahajeni": datum_zahajeni,
            "datum_ukonceni": datum_ukonceni,
            "vrchni_dozor": self._accident_attr(accident, "vrchni_dozor"),
            "zamestnanec": getattr(accident, "employee_name", "") or self._accident_attr(accident, "jmeno_prijmeni"),
            "datum_narozeni": self._fmt_date(self._accident_attr(accident, "datum_narozeni")),
            "pracovni_zarazeni": self._accident_attr(accident, "druh_vykonavane_prace") or self._accident_attr(accident, "cz_isco_nazev"),
            "pracovnepravni_vztah": self._accident_attr(accident, "vztah_k_zamestnavateli"),
            "delka_zamestnani": self._fmt_date(self._accident_attr(accident, "den_vzniku_pravniho_vztahu")),
            "zdravotni_pojistovna": self._accident_attr(accident, "zdravotni_pojistovna"),
            "lokalita": lokalita,
            "misto_urazu": self._accident_attr(accident, "misto_urazu"),
            "charakteristika_pracoviste": self._accident_attr(accident, "charakteristika_pracoviste"),
            "popis_urazu": (
                context.oznameni_value("oznameni_popis")
                or self._accident_attr(accident, "popis_urazoveho_deje")
                or self._accident_attr(accident, "description")
            ),
            "vysledky_setreni": vysledky,
            "bezprostredni_pricina": data.get("analyza_bezprostredni_pricina", "") or self._accident_attr(accident, "pricina_urazu"),
            "zakladni_pricina": data.get("analyza_korenova_pricina", ""),
            "organizacni_pricina": data.get("analyza_proc_5", ""),
            "dalsi_zjisteni": dalsi_zjisteni,
            "poruseni_predpisu": poruseni,
            "vyhodnoceni_opatreni": opatreni,
            "zaver": zaver,
            "zpracoval": zpracoval,
            "datum_zpracovani": datetime.now().strftime("%d.%m.%Y"),
        }

    def _escape_odt_text(self, value) -> str:
        text = str(value or "")
        escaped = html.escape(text, quote=False)
        return escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<text:line-break/>")

    def _fill_odt_template(self, template_path: Path, output_path: Path, values: dict) -> None:
        with zipfile.ZipFile(template_path, "r") as zin, zipfile.ZipFile(output_path, "w") as zout:
            items = [
                item
                for item in zin.infolist()
                if not is_active_odt_zip_entry(item.filename)
            ]
            stripped_active = len(items) != len(zin.infolist())
            for item in items:
                data = zin.read(item.filename)
                if item.filename == "content.xml":
                    xml = data.decode("utf-8")
                    for key, value in values.items():
                        xml = xml.replace("${" + key + "}", self._escape_odt_text(value))
                    data = xml.encode("utf-8")
                elif item.filename == "META-INF/manifest.xml" and stripped_active:
                    data = strip_active_odt_manifest_entries(
                        data.decode("utf-8")
                    ).encode("utf-8")
                zout.writestr(item, data)
        _sync_written_file(output_path)


zaverecna_zprava_service = ZaverecnaZpravaService()
