# UX-TABLE – Přehled pokrytí typovaného řazení tabulek

Stav k 2026-07-18. Infrastruktura: `core/widgets/typed_table_sort.py` (UX-TABLE-1a).

Cíl pro pozdější fáze: *„Každá pracovní tabulka v Manažeru BOZP se řadí kliknutím na hlavičku.“*

---

## Migrace UX-TABLE-1b (Registr rizik)

| Tabulka | Soubor |
|---------|--------|
| Identifikace rizik | `moduly/rizeni_rizik/ui/hazard_identification_table.py` |
| Katalog zdrojů rizik | `moduly/rizeni_rizik/ui/hazard_library_page.py` |
| Zdroje na pracovišti (+ události) | `moduly/rizeni_rizik/ui/hazard_inventory_widget.py` |
| Posouzení rizik | `moduly/rizeni_rizik/ui/hazard_risk_assessments_widget.py` |

---

## Migrace UX-TABLE-1c (Audity a Prověrky)

| Tabulka | Soubor |
|---------|--------|
| Seznam auditů | `moduly/audity/ui/audit_table.py` |
| Zjištění auditu | `moduly/audity/ui/audit_findings_widget.py` |
| Úkoly auditu | `moduly/audity/ui/audit_tasks_widget.py` |
| Program auditů – dashboard (zjištění, úkoly) | `moduly/audity/ui/audit_program_dashboard_widget.py` |
| Plánované návštěvy programu | `moduly/audity/ui/audit_program_planned_visits_widget.py` |
| Seznam prověrek | `moduly/proverky/ui/bozp_inspection_table.py` |
| Zjištění prověrky | `moduly/proverky/ui/bozp_inspection_findings_widget.py` |
| Úkoly prověrky | `moduly/proverky/ui/bozp_inspection_tasks_widget.py` |

---

## Migrace UX-TABLE-1d (Úkoly, úrazy, MU, právní požadavky)

| Tabulka | Soubor |
|---------|--------|
| Centrální seznam úkolů | `moduly/ukoly/ui/task_table.py` |
| Kniha úrazů | `moduly/kniha_urazu/ui/accident_table.py` |
| Zjištění šetření úrazu | `moduly/kniha_urazu/ui/setreni/accident_findings_widget.py` |
| Vyšetřování MU | `moduly/vysetrovani_mu/ui/mu_investigation_table.py` |
| Zjištění vyšetřování MU | `moduly/vysetrovani_mu/ui/mu_findings_widget.py` |
| Právní požadavky (procesy) | `moduly/pravni_pozadavky/ui/legal_requirement_table.py` |
| Právní předpisy | `moduly/pravni_pozadavky/ui/legal_document_table.py` |
| Kontroly legislativy | `moduly/pravni_pozadavky/ui/legal_check_run_table.py` |
| Změny předpisů | `moduly/pravni_pozadavky/ui/legal_change_table.py` |
| Sankce požadavku | `moduly/pravni_pozadavky/ui/legal_requirement_sanction_table.py` |
| Verze předpisu | `moduly/pravni_pozadavky/ui/legal_document_version_table.py` |
| Podřízené požadavky | `moduly/pravni_pozadavky/ui/legal_requirement_children_table.py` |

---

## Zatím bez typovaného řazení (a proč)

| Oblast | Příklady | Důvod |
|--------|----------|-------|
| Matice / formulářové mřížky | `control_year_matrix_table.py`, editorové mřížky | Nejsou běžné seznamy záznamů; řazení by rozbilo matici. |
| Nepoužívané / pomocné tabulky | `control_table.py`, `legal_section_table.py` | Není hlavní pracovní seznam, nebo se nepoužívá. |
| Dopady změn (detail) | `legal_change_impacted_assertions_table.py`, `legal_change_sections_table.py` | Detailové / pomocné tabulky v dialogu změny; nižší priorita. |
| Chronologie / Ishikawa | časová osa úrazu / MU, Ishikawa | Speciální UI, ne klasický seznam. |
| Nastavení / číselníky | seznamy osob, pracovišť, rolí | Malé pomocné seznamy; často už předřazené službou. |
| Znalostní editor | tabulky v editoru kontrolních bodů | Formulářové / stromové UI. |
| Globální hledání | výsledky hledání | Není modulová pracovní tabulka. |

Persistence sloupce/směru řazení, šířek a třetího kliku na výchozí pořadí se v 1a–1d **neřeší**.

---

## Testy

| Fáze | Soubor |
|------|--------|
| 1a | `tests/test_ux_table_1a_typed_table_sort.py` |
| 1b | `tests/test_ux_table_1b_risk_register_sort.py` |
| 1c | `tests/test_ux_table_1c_audity_proverky_sort.py` |
| 1d | `tests/test_ux_table_1d_modules_sort.py` |
