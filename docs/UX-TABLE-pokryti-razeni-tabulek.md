# UX-TABLE – Přehled pokrytí typovaného řazení tabulek

Stav k 2026-07-18. Infrastruktura: `core/widgets/typed_table_sort.py` (UX-TABLE-1a).

**Cíl dosažen pro pracovní seznamy:** každá hlavní pracovní / přehledová tabulka v Manažeru BOZP se řadí kliknutím na hlavičku (typovaný klíč). Persistence sloupce/směru, šířek a třetího kliku se neřeší.

---

## Řaditelné pracovní tabulky – hotovo

### UX-TABLE-1b (Registr rizik)

| Tabulka | Soubor |
|---------|--------|
| Identifikace rizik | `moduly/rizeni_rizik/ui/hazard_identification_table.py` |
| Katalog zdrojů rizik | `moduly/rizeni_rizik/ui/hazard_library_page.py` |
| Zdroje na pracovišti (+ události) | `moduly/rizeni_rizik/ui/hazard_inventory_widget.py` |
| Posouzení rizik | `moduly/rizeni_rizik/ui/hazard_risk_assessments_widget.py` |

### UX-TABLE-1c (Audity a Prověrky)

| Tabulka | Soubor |
|---------|--------|
| Seznam auditů | `moduly/audity/ui/audit_table.py` |
| Zjištění auditu | `moduly/audity/ui/audit_findings_widget.py` |
| Úkoly auditu | `moduly/audity/ui/audit_tasks_widget.py` |
| Program auditů – dashboard | `moduly/audity/ui/audit_program_dashboard_widget.py` |
| Plánované návštěvy programu | `moduly/audity/ui/audit_program_planned_visits_widget.py` |
| Seznam prověrek | `moduly/proverky/ui/bozp_inspection_table.py` |
| Zjištění prověrky | `moduly/proverky/ui/bozp_inspection_findings_widget.py` |
| Úkoly prověrky | `moduly/proverky/ui/bozp_inspection_tasks_widget.py` |

### UX-TABLE-1d (Úkoly, úrazy, MU, právní požadavky)

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

### UX-TABLE-1e (dokončení pokrytí)

| Tabulka | Soubor |
|---------|--------|
| Nastavení – THP pracovníci | `moduly/nastaveni/ui/nastaveni_page.py` (`worker_table`) |
| Nastavení – osoby | `moduly/nastaveni/ui/nastaveni_page.py` (`person_table`) |
| Nastavení – role odpovědnosti | `moduly/nastaveni/ui/nastaveni_page.py` (`responsibility_role_table`) |
| Nastavení – ohrožené skupiny | `moduly/nastaveni/ui/nastaveni_page.py` (`exposed_group_table`) |
| Správa ohrožených skupin (dialog) | `moduly/nastaveni/ui/exposed_groups_management_dialog.py` |
| Roční plán prověrek | `moduly/proverky/ui/rocni_plan_dialog.py` |
| Dashboard – Vyžaduje pozornost | `core/dashboard/widget_upcoming_tasks.py` |
| Historie pracoviště (zjištění + úkoly) | `moduly/audity/ui/audit_workplace_history_widget.py` |
| AI oponentní – historie konzultací (+ návrhy) | `core/ai_oponentni/ui/ai_peer_review_widget.py` |
| Zdroje rizik u právního požadavku | `moduly/pravni_pozadavky/ui/legal_requirement_hazard_catalog_sources_widget.py` |
| Vazby entity | `core/shared/widgets/entity_links_widget.py` |

---

## Úmyslně neřaditelné tabulky

| Klasifikace | Příklady | Důvod |
|-------------|----------|-------|
| **Pevné významové pořadí (Nahoru/Dolů)** | `audit_commission_widget.py`, `bozp_inspection_commission_widget.py` | Pořadí členů komise spravují tlačítka Nahoru/Dolů. |
| **Pevné pořadí editoru (Pořadí / kroky)** | `audity_knowledge_*_editor_widget.py`, `audity_knowledge_assertions_widget.py`, `audity_knowledge_reference_photo_editor_widget.py` | Kapitoly, kroky postupu a tvrzení mají sémantické pořadí. |
| **Chronologie** | `mu_casova_osa_widget.py`, `hazard_library_template_revision_history_widget.py` | Časová osa / historie revizí – pořadí je součástí významu. |
| **Ishikawa / strukturované příčiny** | `mu_ishikawa_widget.py` | Speciální model příčin, ne klasický přehled záznamů. |
| **Formulářová mřížka** | `control_year_matrix_table.py`, `legal_requirement_process_index_widget.py` | Matice / index s pevným významem buněk. |
| **Detail změny (read-only pořadí)** | `legal_change_sections_table.py`, `legal_change_impacted_assertions_table.py` | Ustanovení a tvrzení v pořadí změny / služby. |
| **Malé pomocné / child seznamy** | opatření k posouzení, fotodokumentace, šablony (události/vazby), import preview dialogy, manifest importu, checklist kontroly MU, souhrn dopadů změny | Málo řádků nebo jednorázový dialog; řazení bez přínosu. |
| **Nepoužívaný kód** | `control_table.py`, `legal_section_table.py`, `setreni_dialog._tab_opatreni()` | Třídy / záložka nejsou zapojené do UI. |

---

## Stromy a netabulkové prvky

| Prvek | Soubor / oblast | Poznámka |
|-------|-----------------|----------|
| Strom pracovišť | `nastaveni_page.py` (`QTreeWidget`) | Hierarchie, ne tabulka. |
| Stromy znalostí (audity / prověrky) | `audit_knowledge_tree_widget.py`, `bozp_knowledge_tree_widget.py` | Stromová struktura metodiky. |
| Strom zdrojů předpisů u požadavku | `legal_requirement_sources_widget.py` (`QTreeWidget`) | Hierarchie předpisů. |
| Globální hledání | výsledky hledání | Není modulová pracovní tabulka. |

---

## Známé výjimky / audit starého řazení

- Jediné produkční `setSortingEnabled(True)` je uvnitř `enable_typed_sorting()` v `core/widgets/typed_table_sort.py`.
- V `moduly/` a `core/` není vlastní `__lt__` u položek tabulek mimo `TypedSortTableWidgetItem`.
- Není lokální `sectionClicked` handler pro řazení.
- Kontrola: `tests/test_ux_table_1e_coverage_and_sort.py` (statická kontrola `setSortingEnabled(True)`).

---

## Testy

| Fáze | Soubor |
|------|--------|
| 1a | `tests/test_ux_table_1a_typed_table_sort.py` |
| 1b | `tests/test_ux_table_1b_risk_register_sort.py` |
| 1c | `tests/test_ux_table_1c_audity_proverky_sort.py` |
| 1d | `tests/test_ux_table_1d_modules_sort.py` |
| 1e | `tests/test_ux_table_1e_coverage_and_sort.py` |
