# UX-BUTTON-AUDIT-001 – inventura tlačítek a stavových akcí

**Datum:** 2026-08-06  
**Rozsah:** pouze dokumentace – žádná změna chování ani UX standardů.  
**Metoda:** průchod zdrojového kódu (`moduly/`, `core/`), kombinace hledání `QPushButton` / `QAction` / `setEnabled` / `selectionChanged` / `customContextMenuRequested` / dynamických `setText` / dialogů „Vyberte…“.  
**Pořadí modulů:** podle levého menu v `core/windows/main_window.py` (`_sidebar`).

### Legenda sloupců

| Zkratka | Význam |
|---|---|
| **Sel** | Požadavek na výběr: `0` = bez výběru, `1` = právě jeden, `N` = více (pokud existuje) |
| **Stav** | Závislost na stavu záznamu (`active`, Dokončeno, archivováno…) |
| **En** | `setEnabled` podle výběru / stavu |
| **Ctx** | Položka v kontextovém menu |
| **Dbl** | Dvojklik spouští tuto akci |
| **Vyberte** | Dialog / hláška typu „Vyberte…“ při akci bez výběru |

Stavy tlačítek: **ON** = aktivní, **OFF** = neaktivní, **dyn** = text se mění.

---

## Společné komponenty

| Komponenta | Soubor | Tlačítka | Poznámka |
|---|---|---|---|
| `TableToolbar` | `core/widgets/table_toolbar.py` | Přidat, Upravit, **Aktivovat / Deaktivovat** | Exportována z `core/widgets`; **v aktivních modulech se nepoužívá** (legacy) |
| `FindingTaskActions` | `core/widgets/finding_task_actions.py` | dynamicky **Vytvořit úkol** / **Otevřít úkol** | Jedno tlačítko, `setText` podle vazby na úkol |
| `EntityLinksWidget` | `core/shared/widgets/entity_links_widget.py` | Přidat vazbu, Upravit, **Deaktivovat↔Obnovit** (`setText`) | Dbl→Upravit; „Vyberte vazbu.“ |
| `AttachmentWidget` | `core/widgets/attachment_widget.py` | Přidat přílohu, Otevřít, Odebrat | Sdílené přílohy |
| Multi-selectory | `core/widgets/multi_*_selector.py` | Přidat, Odebrat | Osoby, role, ohrožené skupiny, předpisy… |
| Editor footer | `core/widgets/editor_dialog_controller.py`, `dialog_utils.py` | Uložit, Zrušit/Zavřít | Typický spodní pás editorů |
| Knowledge footer | `core/widgets/knowledge_editor_actions.py` | Použít, Uložit a zavřít, Zavřít | Editory metodiky |

---

## 1. Pracovní plocha

**Soubory:** `moduly/dashboard/ui/dashboard_page.py`, `core/dashboard/widget_*.py`  
**Záložky:** žádné (widgety na ploše).

### Rychlé akce (`_create_quick_actions`)

| Text | Proměnná / callback | Handler | Sel | En | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|
| + Úraz | `open_accidents_callback` | otevření Knihy úrazů | 0 | vždy* | ne | ne | ne |
| Nový úkol | `open_tasks_callback` | otevření úkolů | 0 | vždy* | ne | ne | ne |
| Nová událost | `open_new_meeting_callback` | nová událost | 0 | vždy* | ne | ne | ne |
| 💾 Záloha | — | `_show_backup_dialog` | 0 | ano | ne | ne | ne |
| ♻ Obnova | — | `_show_restore_dialog` | 0 | ano | ne | ne | ne |

\*Aktivní, pokud je callback nastaven.

### Widget – nadcházející úkoly (`widget_upcoming_tasks.py`)

| Text | Proměnná | Handler | Sel | En | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|
| Otevřít | `open_button` | `_open_selected` | 1 | ano (výběr) | ne | ano → Otevřít | ne |
| Agenda | `agenda_button` | navigace | 0 | ano | ne | ne | ne |

### Widget – úrazy / kontroly

| Text | Soubor | Handler | Sel | Poznámka |
|---|---|---|---|---|
| Otevřít Knihu úrazů | `widget_accidents.py` | navigace | 0 | bez výběru řádku |
| Otevřít Kontroly | `widget_controls.py` | navigace | 0 | bez výběru řádku |

**Globální lišta okna:** `Globální vyhledávání` (`main_window.py`).

**Potvrzení úplnosti:** projity quick actions + dashboard widgety. Kontextové menu na ploše není.

---

## 2. Agenda

**Soubor:** `moduly/agenda/ui/agenda_page.py`  
**Konstanty:** `moduly/agenda/constants.py`  
**Záložky:** žádné (jeden seznam).

| Text | Proměnná | Handler | Sel | Stav | En | Bez výběru | 1 výběr | Více | Ctx | Dbl | Vyberte | Obdobné jinde |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Nový úkol | `new_task_btn` | `new_task` | 0 | — | ne | ON | ON | ON | ne | ne | ne | Dashboard, Úkoly |
| Nová událost | `new_meeting_btn` | `new_meeting` | 0 | — | ne | ON | ON | ON | ne | ne | ne | Dashboard, Události |
| Nová událost ze šablony... | `new_from_template_btn` | `new_meeting_from_template` | 0 | — | ne | ON | ON | ON | ne | ne | ne | Události |
| Šablony... | `templates_btn` | `open_templates` | 0 | — | ne | ON | ON | ON | ne | ne | ne | Události |
| Upravit | `edit_btn` | `edit_selected` | 1 | — | ano | OFF | ON | OFF | ano | ano | ne (early return) | většina seznamů |

**Dvojklik:** Upravit (úkol nebo událost podle typu řádku).  
**Kontextové menu:** Upravit (stejná pravidla jako lišta).  
**Selection:** ExtendedSelection + `_selected_row_count() == 1`.

### Související (mimo sidebar, otevírané z Agendy)

#### Šablony událostí – `meeting_templates_page.py`

| Text | Proměnná | Handler | Sel | En | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|
| Nová šablona | `new_btn` | `new_template` | 0 | ne | ne | ne | ne |
| Otevřít | `open_btn` | `open_selected` | 1 | **ne** | ne | ano | „Vyberte šablonu.“ |
| Upravit | `edit_btn` | `open_selected` | 1 | **ne** | ne | — | stejný dialog |
| Odebrat | `remove_btn` | `remove_selected` | 1 | **ne** | ne | ne | stejný |

**Nález:** Otevřít i Upravit volají stejný handler (duplicita Otevřít/Upravit). Bez `setEnabled`. Bez kontextového menu.

#### Legacy Události – `schuzky_page.py`

Stejný vzor jako Agenda (Nová událost / šablona / Šablony… / Upravit + ctx + dbl + `setEnabled`).

#### Legacy Úkoly – `ukoly_page.py` (není v sidebaru)

| Text | Proměnná | Handler | Sel | En | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|
| Nové opatření | `new_btn` | `new_task` | 0 | ne | ne | ne | ne |
| Upravit | `edit_btn` | `edit_selected_task` | 1 | **ne** | ne | ano | „Vyberte opatření.“ |
| Splněno | `completed_btn` | `mark_completed` | 1 | **ne** | ne | ne | stejný |
| Vrátit do aktivních | `reopen_btn` | `reopen_selected_task` | 1 | **ne** | ne | ne | stejný |
| Zrušit / netrvá | `cancel_btn` | `cancel_selected_task` | 1 | **ne** | ne | ne | stejný |

**Potvrzení úplnosti Agenda:** hlavní seznam + šablony + legacy stránky.

---

## 3. Kniha úrazů

**Soubor:** `moduly/kniha_urazu/ui/kniha_urazu_page.py`  
**Záložky:** žádné.

| Text | Proměnná | Handler | Sel | Stav | En | Bez / 1 / Více | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|---|---|
| Nový úraz | `new_btn` | `new_accident` | 0 | — | ne | ON / ON / ON | ne | ne | ne |
| Upravit | `edit_btn` | `edit_selected_accident` | 1 | — | ano | OFF / ON / OFF | ano | ano | ne |
| Ohláška OO | `notice_btn` | `open_union_notice` | 1 | — | ano | OFF / ON / OFF | ano | ne | ne |
| Ohlašovací povinnosti | `investigation_btn` | `open_investigation` | 1 | — | ano | OFF / ON / OFF | ano | ne | ne |
| Vyšetřování MU | `mu_investigation_btn` | `open_mu_investigation` | 1 | — | ano | OFF / ON / OFF | ano | ne | ne |
| Výpis o pracovním úrazu | `vypis_btn` | `generate_accident_report` | 1 | — | ano | OFF / ON / OFF | ano | ne | ne |
| Závěrečná zpráva | `final_report_btn` | `generate_final_report` | 1 | — | ano | OFF / ON / OFF | ano | ne | ne |

**Editor (šetření):** mnoho vnořených akcí (fotografie, zařízení, OOPP, opatření…) – typicky Přidat / Upravit / Odebrat; zjištění: Přidat / Upravit / Smazat + „Vyberte zjištění.“ (`accident_findings_widget.py`).  
**Ohláška OO dialog:** Náhled, Tisk, Uložit jako PDF, Zavřít; průvodce: Vrátit se k doplnění / Pracovní náhled / Pokračovat…

**Potvrzení úplnosti:** hlavní seznam + klíčové nested listy v šetření a ohlášce.

---

## 4. Vyšetřování MU

**Soubor:** `moduly/vysetrovani_mu/ui/vysetrovani_mu_page.py`

| Text | Proměnná | Handler | Sel | En | Bez / 1 / Více | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|---|
| Nové vyšetřování | `new_btn` | `new_investigation` | 0 | ne | ON | ne | ne | ne |
| Upravit | `edit_btn` | `edit_selected_investigation` | 1 | ano | OFF/ON/OFF | ano | ano | ne |
| Smazat | `delete_btn` | `delete_selected_investigation` | 1 | ano | OFF/ON/OFF | ano | ne | ne |
| Sedmero | `sedmero_btn` | `show_sedmero` | 0 | ne | ON | ne | ne | ne |

### Editor – vybrané seznamy

| Místo | Tlačítka | Vyberte | Poznámka |
|---|---|---|---|
| `mu_findings_widget.py` | Přidat, Upravit, Smazat | „Vyberte zjištění.“ | + FindingTaskActions |
| `mu_ishikawa_widget.py` | (úpravy příčin) | „Vyberte příčinu.“ | |
| Footer editoru | Kontrola spisu | — | `check_spis_btn` |

**Potvrzení úplnosti:** hlavní seznam + zjištění / Ishikawa v editoru.

---

## 5. Kontroly

**Soubor:** `moduly/kontroly/ui/kontroly_page.py`  
**Záložky:** žádné.

| Prvek | Popis |
|---|---|
| `QComboBox` rok | filtr roku – **žádné** `QPushButton` na hlavní stránce |
| Matice `ControlYearMatrixTable` | `cellClicked` → `_on_cell_clicked` (otevření detailu buňky) |
| Kontextové menu | **není** |
| Dvojklik | ne (klik na buňku) |

**Potvrzení úplnosti:** celá stránka Kontroly (matice, ne klasický seznam).

---

## 6. Audity systémů řízení

**Soubor:** `moduly/audity/ui/audity_page.py`  
**Konstanty:** `moduly/audity/constants.py`

| Text | Proměnná | Handler | Sel | Stav | En | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|---|
| Nový audit | `new_btn` | `new_audit` | 0 | — | ne | ne | ne | ne |
| Manažer auditů | `program_btn` | `open_program_manager` | 0 | — | ne | ne | ne | ne |
| Upravit | `edit_btn` | `open_selected_audit` | 1 | — | ano | ano | ano | ne |
| Smazat | `delete_btn` | `delete_selected_audit` | 1 | — | ano | ano | ne | ne |
| Protokol z interního auditu... | `protocol_btn` | `export_selected_protocol` | 1 | Dokončeno | ano | ano* | ne | ne |
| Podrobná zpráva z interního auditu... | `detailed_report_btn` | `export_selected_detailed_report` | 1 | Dokončeno | ano | ano* | ne | ne |
| Editor metodiky | `knowledge_editor_btn` | `open_knowledge_editor` | 0 | — | ne | ne | ne | ne |
| Roční zpráva | `report_btn` | `open_annual_report` | 0 | — | ne | ne | ne | ne |

\*V ctx menu jen pokud je akce enabled.

### Manažer auditů (`audit_program_manager_dialog.py`)

| Text | Proměnná | Sel / stav | Ctx stromu |
|---|---|---|---|
| + Nový program | `_new_program_btn` | 0 | ne |
| Upravit | `_edit_program_btn` | výběr programu | ne |
| Obnovit | `_refresh_programs_btn` | 0 | ne |
| Generovat návštěvy | `_generate_visits_btn` | program | ne |
| Doplnit pracoviště | `_supplement_workplaces_btn` | program | ne |
| Rozdělit procesy / Doplnit nové procesy | `_distribute_processes_btn` | **dyn `setText`** | ne |
| Přepočítat přehled | `_refresh_overview_btn` | 0 | ne |
| Závěrečná zpráva programu | `_final_report_btn` | program | ne |
| + Nová návštěva | `_add_visit_btn` | výběr | ano |
| Upravit návštěvu | `_edit_visit_btn` | výběr | ano |
| Zrušit návštěvu | `_skip_visit_btn` | výběr | ano |
| Přesunout... | `_move_process_btn` | proces | ano |
| Zahájit audit... | `_start_audit_btn` | návštěva | ano |
| Otevřít audit | `_open_audit_btn` | návštěva s auditem | ano |
| Protokol… / Podrobná zpráva… | `_protocol_btn`, `_detailed_report_btn` | dokončený audit | ano |
| Zavřít | `_close_btn` | 0 | ne |

### Editor auditu – zjištění / úkoly

| Widget | Tlačítka | Vyberte |
|---|---|---|
| `audit_findings_widget.py` | Přidat / Upravit / … | „Vyberte zjištění.“ |
| `audit_tasks_widget.py` | … | „Vyberte úkol.“ |
| Dynamické zjištění | ➕ Založit zjištění / Otevřít zjištění | stav zjištění |
| `FindingTaskActions` | Vytvořit úkol / Otevřít úkol | dyn |

### Editor metodiky – referenční fotografie

| Text | Soubor | Typ |
|---|---|---|
| Přidat, Upravit, Deaktivovat, Obnovit | `audity_knowledge_reference_photo_editor_widget.py` | **dvě** samostatná Deaktivovat + Obnovit |

**Potvrzení úplnosti:** hlavní seznam + Manažer auditů + znalosti/fotky + findings/tasks.

---

## 7. Prověrky BOZP

**Soubor:** `moduly/proverky/ui/proverky_page.py`

| Text | Proměnná | Handler | Sel | Stav | En | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|---|
| Nová prověrka | `new_btn` | `new_inspection` | 0 | — | ne | ne | ne | ne |
| Upravit | `edit_btn` | `open_selected_inspection` | 1 | — | ano | ano | ano | ne |
| Smazat | `delete_btn` | `delete_selected_inspection` | 1 | — | ano | ano | ne | ne |
| Roční plán | `plan_btn` | `show_annual_plan` | 0 | — | ne | ne | ne | ne |
| Generovat prověrky | `generate_btn` | `generate_inspections` | 0 | — | ne | ne | ne | ne |
| Zpráva z prověrky BOZP | `protocol_btn` | `export_selected_protocol` | 1 | Dokončeno | ano | ano* | ne | ne |
| Podrobná zpráva z prověrky BOZP | `detailed_report_btn` | `export_…` | 1 | Dokončeno | ano | ano* | ne | ne |
| Roční zpráva | `report_btn` | `show_annual_report` | 0 | — | ne | ne | ne | ne |
| Editor znalostí | `knowledge_editor_btn` | `open_knowledge_editor` | 0 | — | ne | ne | ne | ne |

### Editor znalostí – sekce (`proverky_knowledge_section_edit_dialog.py`)

| Text | Typ stavové akce | Vyberte |
|---|---|---|
| Přidat fotografii / Přidat | 0 | — |
| Upravit, Odebrat, Posun nahoru/dolů | 1 | ano („Vyberte fotografii/položku…“) |
| **Aktivní / neaktivní** | **jedno kombinované** tlačítko | ano |

Obdobné: findings/tasks v editoru prověrky („Vyberte zjištění.“ / „Vyberte úkol.“).  
Roční plán: „Vyberte prověrku.“

**Potvrzení úplnosti:** hlavní seznam + znalostní editor + findings/tasks + roční plán.

---

## 8. Řízení rizik

**Shell:** `rizeni_rizik_page.py` – záložky: **Identifikace** | **Katalog zdrojů rizik** | **Revize posouzení rizik**

### 8.1 Identifikace (`HazardIdentificationsTab`)

| Text | Proměnná | Handler | Sel | Stav | En | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|---|
| Nová identifikace | `new_btn` | `new_identification` | 0 | — | ne | ne | ne | ne |
| Upravit | `edit_btn` | `edit_selected_identification` | 1 | — | ano | ano | ano | ne |
| Aktivovat | `activate_btn` | `activate_selected_…` | 1 | neaktivní | ano | ano | ne | ne |
| Deaktivovat | `deactivate_btn` | `deactivate_selected_…` | 1 | aktivní | ano | ano | ne | ne |
| Pravidla bezpečné práce | `pravidla_btn` | `open_pravidla_…` | 0 | — | ne | ne | ne | ne |

**Typ:** dvě samostatná tlačítka Aktivovat / Deaktivovat.

### 8.2 Katalog (`hazard_library_page.py`)

| Text | Proměnná | Sel | Stav | En | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|
| Nový zdroj rizika* | `new_btn` | 0 | — | ne | ne | ne | ne |
| Upravit | `edit_btn` | 1 | — | ano | ano | ano | ne |
| Aktivovat | `activate_btn` | 1 | neaktivní | ano | ano | ne | ne |
| Deaktivovat | `deactivate_btn` | 1 | aktivní | ano | ano | ne | ne |
| Spravovat kategorie… | `manage_categories_btn` | 0 | — | ne | ne | ne | ne |

\*Text z `HAZARD_LIBRARY_NEW_BUTTON`.

### 8.3 Revize posouzení rizik (`risk_measure_reviews_tab.py`)

| Text | Proměnná | Sel | Stav | En | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|
| Nová revize | `new_btn` | 0 | — | ne | ne | ne | ne |
| Upravit | `edit_btn` | 1 | — | ano | ano | ano | ne |
| Provést revizi | `execute_btn` | 1 | ne archiv | ano | ano | ne | ne |
| Archivovat | `archive_btn` | 1 | ne archiv | ano | ano | ne | ne |
| Obnovit | `restore_btn` | 1 | archiv | ano | ano | ne | ne |

**Typ:** dvě samostatná Archivovat / Obnovit (ne `setText`).

### 8.4 Nested widgety (editor identifikace / katalog)

| Místo | Tlačítka | Stavový vzor | Vyberte |
|---|---|---|---|
| `hazard_inventory_widget.py` | Upravit, Aktivovat, Deaktivovat; Přidat událost… | 2 tlačítka | dle handlerů |
| `hazard_existing_measures_widget.py` | Přidat, Upravit, Aktivovat, Deaktivovat | 2 tlačítka | „Vyberte existující opatření.“ |
| `hazard_required_measures_widget.py` | stejně | 2 tlačítka | „Vyberte potřebné opatření.“ |
| `hazard_identification_photos_widget.py` | Přidat fotografii, Otevřít, Upravit, Aktivovat, Deaktivovat | 2 tlačítka | „Vyberte fotografii.“ |
| `risk_measure_review_tasks_widget.py` | Nový úkol, Otevřít úkol, Obnovit | Obnovit = refresh seznamu | „Vyberte úkol.“ |
| `hazard_source_categories_management_dialog.py` | správa kategorií | — | „Vyberte kategorii.“ |
| `professions_management_dialog.py` | správa profesí | — | „Vyberte profesi.“ |

**Potvrzení úplnosti:** všechny 3 záložky + hlavní nested listy editorů.

---

## 9. Koordinace BOZP

### 9.1 Hlavní seznam (`koordinace_bozp_page.py`)

| Text | Proměnná | Handler | Sel | Stav | En | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|---|
| Nová koordinace | `new_btn` | `new_coordination` | 0 | — | ne | **ne** | ne | ne |
| Otevřít | `open_btn` | `open_selected_coordination` | 1* | — | ano | **ne** | ano | „Vyberte koordinaci.“ |
| Tisk protokolu | `print_btn` | `print_selected_protocol` | 1* | — | ano | ne | ne | stejný |
| Aktivovat | `activate_btn` | `activate_selected_…` | 1* | neaktivní | ano | ne | ne | stejný |
| Deaktivovat | `deactivate_btn` | `deactivate_selected_…` | 1* | aktivní | ano | ne | ne | stejný |
| *(dyn)* Vrátit k dopracování… | lifecycle `QPushButton(action.label)` | `_run_lifecycle_action` | 1 | Closed | vytváří se | ne | ne | — |

\*Enable podle `has_selection` (ne striktní `selectedRows()==1` jako v APPLY modulech).  
**Keyboard:** `install_table_row_actions` – Enter→Otevřít, Delete→Deaktivovat.  
**Nález:** tlačítka se disableují, ale handlery stále obsahují dialog „Vyberte koordinaci.“

### 9.2 Editor – záložky

| Záložka | Soubor | Lišta | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|
| Zaměstnavatelé | `coordination_employers_tab.py` | Přidat, Upravit, Aktivovat, Deaktivovat | ne | Upravit | „Vyberte zaměstnavatele.“ |
| Účastníci | `coordination_participants_tab.py` | stejně | ne | Upravit | „Vyberte účastníka.“ |
| Místa | `coordination_workplaces_tab.py` | stejně | ne | Upravit | „Vyberte místo.“ |
| Kontakty | `coordination_contacts_tab.py` | + Nahoru / Dolů | ne | Upravit | „Vyberte kontakt.“ |
| Opatření | `coordination_measures_tab.py` | + Nahoru / Dolů | ne | Upravit | „Vyberte opatření.“ |
| Činnosti | `coordination_employer_activities_tab.py` | Přidat… | ne | Upravit | „Vyberte činnost.“ |
| Předání rizik | `coordination_risk_submissions_tab.py` | Uložit předání, Přidat přílohu, Otevřít, Deaktivovat | ne | Otevřít přílohu | „Vyberte přílohu.“ |
| PBP příloha | `coordination_pbp_attachment_tab.py` | Generovat, Aktualizovat, Náhled, Export ODT, Historie | ne | — | dle existence přílohy |

**Footer editoru** (`bozp_coordination_dialog.py`): **Náhled protokolu**, **Uzavřít** (lifecycle) + Uložit/Zavřít z controlleru.

**Potvrzení úplnosti:** hlavní seznam + všechny coordination_*_tab.

---

## 10. Právní požadavky

**Shell:** `pravni_pozadavky_page.py` – záložky: **Řídicí procesy** | **Právní předpisy** | **Kontroly změn** | **Zjištěné změny**

### 10.1 Řídicí procesy (`pravni_pozadavky_requirements_tab.py`)

| Text | Proměnná | Sel | Stav | En | Typ stavové akce | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|---|
| Nový proces | `new_btn` | 0 | — | ne | — | ne | ne | ne |
| Upravit | `edit_btn` | 1 | — | ano | — | ano | ano | ne |
| Archivovat / Obnovit | `archive_btn` | 1 | active | ano | **dyn `setText`** | ano | ne | ne |
| Import procesů | `import_json_btn` | 0 | — | ne | — | ne | ne | ne |
| Sloučit proces | `merge_btn` | 0* | — | — | — | ne | ne | dialog sloučení |
| Ověřit plnění | `verify_btn` | 1 | — | ano | — | ano | ne | ne |
| Vytvořit úkol | `task_btn` | 1 | can_create_task | ano | — | ano | ne | ne |
| Diagnostika registru | `diagnostic_registry_btn` | 0 | — | ne | — | ne | ne | ne |

### 10.2 Právní předpisy (`pravni_predpisy_tab.py`)

| Text | Proměnná | Sel | En | Typ | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|
| Nový | `new_btn` | 0 | ne | — | ne | ne | ne |
| Upravit | `edit_btn` | 1 | ano | — | ano | ano | ne |
| Platné znění | `valid_text_btn` | 1 | ano | — | ano | ne | ne |
| Import z internetu / TXT / JSON | import_* | 0 | ne | — | ne | ne | ne |
| Export JSON | `export_btn` | 1 | ano | — | ano | ne | ne |
| Deaktivovat ↔ Obnovit | `toggle_btn` | 1 | ano | **dyn `setText`** | ano | ne | ne |

### 10.3 Kontroly změn (`kontroly_legislativy_tab.py`)

| Text | Proměnná | Sel | En | Typ | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|
| Provést kontrolu | `perform_check_btn` | 0 | ne | — | ne | ne | ne |
| Otevřít | `open_btn` | 1 | ano | — | ano | ano | ne |

`LegalCheckRun.active` se v tomto UI neovládá (RPP-CHECK-ACTIVE-2).

### 10.4 Zjištěné změny (`zmeny_legislativy_tab.py`)

| Text | Proměnná | Sel | Stav | En | Typ | Ctx | Dbl | Vyberte |
|---|---|---|---|---|---|---|---|---|
| Otevřít | `open_btn` | 1 | — | ano | — | ano | ano | ne |
| Deaktivovat ↔ Obnovit | `toggle_btn` | 1 | active | ano | **dyn `setText`** | ano | ne | ne |
| Označit jako vyhodnocené | `evaluate_btn` | 1 | nevyhodnoceno | ano | — | ano | ne | ne |

### 10.5 Editor předpisu / procesu – subzáložky

| Místo | Tlačítka | Typ toggle | Vyberte |
|---|---|---|---|
| `legal_document_sections_tab.py` | Přidat, Vytvořit právní požadavek, Upravit, Deaktivovat↔Obnovit | dyn `setText` | „Vyberte část/ustanovení…“ |
| `legal_document_versions_tab.py` | Přidat, Upravit, Deaktivovat↔Obnovit | dyn | „Vyberte verzi.“ |
| `legal_requirement_sanctions_tab.py` | Přidat, Upravit, Deaktivovat↔Obnovit | dyn | „Vyberte sankci.“ |
| `EntityLinksWidget` (vazby) | Přidat vazbu, Upravit, Deaktivovat↔Obnovit | dyn | „Vyberte vazbu.“ |
| `legal_requirement_children_tab.py` | (otevření podřízených) | — | „Vyberte podřízený proces.“ |

**Poznámka k enablementu subzáložek:** často se mění jen text toggle; edit/toggle nemají vždy plné STANDARD-001 disable jako hlavní seznamy.

**Potvrzení úplnosti:** všechny 4 záložky + klíčové editor subzáložky.

---

## 11. Správa dat

**Shell:** `sprava_dat_page.py` – záložky dle `tab_constants.py`.

### 11.1 Souhrn (`summary_tab.py`)

| Text | Účel | Sel |
|---|---|---|
| Otevřít umístění (× více) | složky záloh / registru / číselníků | 0 |
| Navigační tlačítka na ostatní záložky | přepnutí | 0 |

### 11.2 Zálohování a obnova (`backup_tab.py`)

| Text | Proměnná | Sel |
|---|---|---|
| Vytvořit zálohu | `create_mbbackup_button` | 0 |
| Ověřit zálohu | `verify_mbbackup_button` | 0 |
| Obnovit ze zálohy | `restore_mbbackup_button` | 0 |
| Diagnostika obnovy | `recovery_diag_button` | 0 |

### 11.3 Přenos dat (`legal_registry_transfer_tab.py`)

| Text | Proměnná |
|---|---|
| Exportovat registr | `export_button` |
| Otevřít umístění | `open_export_button` |
| Importovat registr | `import_button` |
| Otevřít bezpečnostní zálohu před importem | `open_safety_backup_button` |

### 11.4 Číselníky (`codebooks_tab.py`)

| Text | Proměnná | Enablement | Ctx stromu |
|---|---|---|---|
| Export / Import | `export_button`, `import_button` | podle výběru stromu / capabilities | ano (strom) |
| Exportovat / Importovat skupinu | `export_group_button`, `import_group_button` | skupina | ano |
| Otevřít umístění | `open_single_export_button`, `open_bulk_export_button` | cesta | — |
| Exportovat / Importovat všechny číselníky | bulk_* | 0 | — |

Prázdný stav: label „Vyberte skupinu nebo číselník“ (informační, ne QMessageBox při akci).

### 11.5 Diagnostika (`legal_registry_diagnostics_tab.py`)

| Text | Proměnná |
|---|---|
| Diagnostika registru | `run_button` |
| Kontrola příloh | `run_attachment_button` |
| Smazat všechny řídicí procesy | `delete_processes_button` |

### 11.6 Kvalita dat (`data_quality_tab.py`)

| Text | → dialog podobností |
|---|---|
| Spustit analýzu | `similarity_analysis_dialog.py`: Označit vybrané…, Otevřít první/druhou/obě, Označit jako zkontrolované |

**Potvrzení úplnosti:** všech 6 záložek Správy dat.

---

## 12. Nastavení

**Soubor:** `moduly/nastaveni/ui/nastaveni_page.py`  
**Záložky:** THP | Osoby | Provozy a pracoviště | Funkce / role | Ohrožené skupiny | Zaměstnavatel

Společný vzor číselníků (po APPLY-010):

| Akce | Sel | Stav | En | Ctx | Dbl | Vyberte | Typ |
|---|---|---|---|---|---|---|---|
| Přidat / Nový… | 0 | — | vždy ON | ne | ne | ne | — |
| Upravit | 1 | — | OFF bez výběru | ano | ano | ne | — |
| Aktivovat | 1 | neaktivní | OFF jinak | ano | ne | ne | **samostatné** |
| Deaktivovat | 1 | aktivní | OFF jinak | ano | ne | ne | **samostatné** |

| Záložka | Přidat text | Proměnné edit/activate/deactivate |
|---|---|---|
| THP pracovníci | Přidat THP pracovníka | `worker_edit/activate/deactivate_button` |
| Osoby | Nová osoba | `person_*` |
| Provozy… | Nový provoz / Nové pracoviště / Nová část… | `workplace_*` (strom, SingleSelection) |
| Funkce / role | Přidat roli | `responsibility_role_*` |
| Ohrožené skupiny | Přidat | `exposed_group_*` |
| Zaměstnavatel | Načíst z ARES, Uložit zaměstnavatele | formulář, bez seznamu |

**Dialogy:** `responsibility_roles_management_dialog.py`, `exposed_groups_management_dialog.py` – stejný vzor Přidat / Upravit / Aktivovat / Deaktivovat.

**Potvrzení úplnosti:** všech 6 záložek + management dialogy.

---

## 13. O programu

**Soubor:** `core/windows/about_dialog.py`  
**Akce:** pouze **OK** (`QDialogButtonBox`). Bez seznamu, bez ctx menu.

---

## Souhrn variant

### A. Různé názvy tlačítek (hlavní seznamy + typické akce)

| Název | Kde (výběr) |
|---|---|
| Nový… / Nová… / Přidat… | téměř všude |
| Upravit | většina seznamů |
| Otevřít | Koordinace, Kontroly změn, Změny, Šablony, fotky, dashboard |
| Smazat | MU, Audity, Prověrky (+ nested findings) |
| Odebrat | Šablony, přílohy, poznámky, knowledge |
| Aktivovat / Deaktivovat | Nastavení, Rizika, Koordinace (+ nested) |
| Archivovat / Obnovit | Právní procesy (dyn); Přezkoumání (2 tlačítka) |
| Deaktivovat / Obnovit | Právní předpisy/změny + editor subzáložky (dyn); **ne** Kontroly změn |
| Splněno / Vrátit do aktivních / Zrušit / netrvá | Úkoly (legacy) |
| Označit jako vyhodnocené | Zjištěné změny |
| Označit jako zkontrolované | Kvalita dat / podobnosti |
| Uzavřít | Koordinace editor (lifecycle) + běžné dialogy |
| Protokol / Zpráva / Roční zpráva | Audity, Prověrky |
| Manažer auditů / Editor metodiky / Editor znalostí | Audity, Prověrky |
| Aktivní / neaktivní | Prověrky knowledge section |
| Vytvořit úkol / Otevřít úkol | FindingTaskActions (dyn) |
| Vrátit k dopracování | Koordinace lifecycle (dyn label) |

### B. Varianty aktivace / deaktivace / archivu

| Varianta | Kde | Popis |
|---|---|---|
| **Dvě samostatná** Aktivovat + Deaktivovat | Nastavení, Identifikace, Katalog, Koordinace (+ většina nested tabů), hazard measures/photos/inventory | Enable podle `active` |
| **Dyn `setText`** Deaktivovat ↔ Obnovit | Předpisy, Změny; sections/versions/sanctions; EntityLinks | Jedno tlačítko |
| **Dyn `setText`** Archivovat ↔ Obnovit | Řídicí procesy | Jedno tlačítko |
| **Dvě samostatná** Archivovat + Obnovit | Revize posouzení rizik | Podle archived |
| **Dvě samostatná** Deaktivovat + Obnovit | Audity knowledge reference photos | |
| **Jedno kombinované** Aktivovat / Deaktivovat | `TableToolbar` (nepoužito v live modulech) | Legacy label |
| **Jedno kombinované** Aktivní / neaktivní | Prověrky knowledge editor | |
| **Dyn label** FindingTaskActions | Vytvořit úkol / Otevřít úkol | Podle existence úkolu |
| **Dyn lifecycle** | Koordinace seznam | např. Vrátit k dopracování |
| **Dyn `setText`** Rozdělit/Doplnit procesy | Manažer auditů | |

### C. Kombinovaná / dynamická stavová tlačítka (seznam)

1. Právní – `archive_btn` (Archivovat/Obnovit)  
2. Právní – `toggle_btn` předpisy / změny (ne Kontroly změn)  
3. Právní editor – sections / versions / sanctions toggles  
4. `EntityLinksWidget.toggle_btn`  
5. Prověrky knowledge – Aktivní / neaktivní  
6. `FindingTaskActions.button`  
7. Manažer auditů – distribute/supplement processes  
8. Koordinace – lifecycle buttons  
9. Legacy `TableToolbar.btn_toggle` (nepoužito)

### D. Duplicity Otevřít / Upravit

| Místo | Otevřít | Upravit | Stejný handler? | Dvojklik |
|---|---|---|---|---|
| Šablony událostí | ano | ano | **ano** (`open_selected`) | Otevřít |
| Koordinace seznam | Otevřít | — | — | Otevřít |
| Audity / Prověrky / MU / Agenda / … | — | Upravit | Upravit = otevření editoru | Upravit |
| Právní kontroly/změny | Otevřít | — | — | Otevřít |
| Fotky identifikace | Otevřít + Upravit | oddělené | ne | Upravit |
| Dashboard úkoly | Otevřít | — | — | Otevřít |
| Detail / Zobrazit | **nenalezeno** jako list action label | — | — | — |

### E. Dialogy „Vyberte…“ (QMessageBox u list akcí)

| Oblast | Příklady textů | Poznámka |
|---|---|---|
| Koordinace hlavní | Vyberte koordinaci. | residual při disabled tlačítkách |
| Koordinace nested | zaměstnavatele / účastníka / místo / kontakt / opatření / činnost / přílohu | běžné |
| Úkoly legacy | Vyberte opatření. | bez setEnabled |
| Šablony | Vyberte šablonu. | bez setEnabled |
| Právní editor tabs | část / verzi / sankci / ustanovení / vazbu | |
| MU / Audity / Prověrky nested | zjištění / úkol / příčinu | |
| Rizika nested | fotografii / opatření / kategorii / profesi / úkol | |
| Codebooks | „Vyberte skupinu…“ | empty-state label, ne QMessageBox akce |

Hlavní seznamy po APPLY-001…010: dialogy „Vyberte audit/prověrku/úraz/…“ **odstraněny**.

### F. Místa bez kontextového menu (hlavní / významné seznamy)

| Místo |
|---|
| Pracovní plocha (widgety) |
| Kontroly (matice) |
| Koordinace BOZP – hlavní seznam |
| Koordinace – všechny editor záložky |
| Úkoly (legacy) |
| Šablony událostí |
| Správa dat – většina záložek (kromě stromu číselníků) |
| Zaměstnavatel (Nastavení) |
| O programu |

### G. Lišta vs. kontextové menu – rozdílná pravidla

| Místo | Rozdíl |
|---|---|
| Audity / Prověrky | Ctx obsahuje Upravit/Smazat/protokoly; protokoly v ctx jen pokud enabled (stejně jako lišta) |
| Agenda / Kniha / MU / Rizika / Právní / Nastavení | Ctx zrcadlí selection akce lišty |
| Koordinace | Lišta ano, **ctx vůbec ne** (jen klávesnice) |
| Manažer auditů | Ctx na stromu návštěv; lišta programů odděleně |
| Šablony / Úkoly | Ani enable, ani ctx |

### H. Hromadné akce (multi-select)

Na **hlavních seznamech modulů** nebyly nalezeny akce aktivní při více řádcích (`N`).  
ExtendedSelection se používá (disable při >1), ale bulk akce chybí.  
Výjimky blízké bulk: Kvalita dat – „Označit vybrané jako zkontrolované“; AI import – Označit vše.

---

## Nálezy vyžadující rozhodnutí

*(Bez automatického rozhodnutí v tomto sprintu.)*

1. **Jednotný vzor Aktivovat/Deaktivovat:** všude dvě tlačítka (Nastavení/Rizika/Koordinace), nebo dyn Deaktivovat/Obnovit (Právní), nebo Archivovat/Obnovit – sjednotit terminologii Obnovit vs Aktivovat.
2. **Kdy dyn tlačítko:** FindingTaskActions a lifecycle Koordinace dávají smysl; u Archivovat/Deaktivovat spíš sporné.
3. **Smazat vs Deaktivovat:** MU/Audity/Prověrky mažou; číselníky deaktivují – potvrdit záměr.
4. **Otevřít vs Upravit:** Šablony mají obě se stejným handlerm; Koordinace má jen Otevřít; ostatní Upravit = editor. Sjednotit podle UX STANDARD § 6a.
5. **Hromadné akce:** zda vůbec zavést (STANDARD 001 § 3) – dnes prakticky neexistují na hlavních seznamech.
6. **Kontextové menu u Koordinace:** doplnit, nebo ponechat jen klávesnici + lištu.
7. **Residual „Vyberte…“** tam, kde už je `setEnabled` (Koordinace, nested listy) – odstranit vs. ponechat jako pojistku.
8. **Legacy Úkoly / Šablony:** do sidebaru nepatří, ale Agendou se otevírají – APPLY STANDARD 001/002?
9. **TableToolbar** s „Aktivovat / Deaktivovat“: smazat / aktualizovat / nechat legacy.
10. **Kontroly:** matice bez list toolbaru – zda vůbec spadají pod STANDARD 001.
11. **Aktivní / neaktivní** v editoru znalostí Prověrek vs dvě tlačítka jinde.
12. **Multi-select enablement:** Koordinace používá `has_selection`, APPLY moduly `== 1` – sjednotit.

---

## Metodická poznámka k úplnosti

Pro každý modul v sidebaru (1–13) byly projity:

- hlavní stránka / všechny top-level záložky,
- konstrukce toolbarů (`QPushButton`),
- `_refresh_action_buttons` / `_update_action_buttons` / `setEnabled`,
- kontextová menu (`customContextMenuRequested`),
- dvojklik,
- dynamické `setText` u stavových akcí,
- výskyt QMessageBox „Vyberte…“.

Vnořené editory (šetření úrazu, znalostní editory, AI dialogy, PhotoPicker) jsou zachyceny **výběrově** u list-akcí a stavových vzorů; kompletní inventura každého formulářového tlačítka (Uložit/Zavřít/Vybrat soubor…) není cílem tohoto sprintu – typické footer vzory jsou v kapitole Společné komponenty.

**Zdroj menu:** `core/windows/main_window.py` – preferred_order + Správa dat / Nastavení / O programu.
