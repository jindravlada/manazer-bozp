# MIGRATION-0 – Ověření přechodu z 3.1.0 na 3.2.0

Stav k 2026-07-19.

**Cíl:** prokázat, že výměna programu 3.1.0 → 3.2.0 nad stejným datovým
adresářem zachová uživatelská data, doplní Registr rizik a umožní novou
`*.mbbackup`.

**Kód:** `core/database/upgrade_guard.py`, napojení v `main.py`  
**Testy:** `tests/test_migration_0_upgrade_3_1_0_to_3_2_0.py`  
**Verze:** `APP_VERSION = 3.2.0`

---

## Verdikt

### **SAFE_TO_UPGRADE_WITH_LIMITATIONS**

Upgrade je bezpečný při dodržení postupu níže: při prvním startu 3.2.0 nad
daty 3.1.0 aplikace **nejprve** vytvoří ověřenou předmigrační `*.mbbackup`,
teprve poté spustí `initialize_database()`. Původní řádky a workspace soubory
A+B se v testu zachovaly; tabulky Registru rizik vzniknou prázdné a modul je
použitelný.

**Omezení (proto ne SAFE_TO_UPGRADE bez výhrad):**

1. Migrace schématu **nemá automatický rollback** – při pádu uprostřed zůstane
   marker `in_progress` a aplikace **odmítne** další start; obnova je z
   předmigrační zálohy (viz §11).
2. Absolutní cesty (AI export, právní PDF mimo workspace, `original_path`,
   cesty v `sprava_dat.json`) migrace **nemění** – na stejném notebooku zůstanou
   funkční, pokud soubory existují; po přesunu PC platí omezení BACKUP-2d.
3. Starý ZIP formát zálohy v UI **zatím zůstává** (záměrně mimo tuto fázi).

---

## 1. Výchozí scénář uživatele

1. Notebook má AppImage / instalaci **3.1.0** a data v
   `~/.local/share/manazer-bozp` (Windows: `%LOCALAPPDATA%\manazer-bozp`).
2. Uživatel nahradí pouze program za **3.2.0** (stejný datový adresář).
3. První spuštění 3.2.0 → `prepare_database_for_startup()`:
   - detekce legacy DB (chybí `hazard_identifications`),
   - předmigrační záloha do `zalohy/pre-migration-3.1.0-to-3.2.0-….mbbackup`,
   - ověření integrity,
   - migrace schématu,
   - marker dokončení v `konfigurace/migration_state.json`.
4. Data se **nepřesouvají** ani neručně neimportují.

---

## 2. Mapa migrací 3.1.0 → 3.2.0

Žádný Alembic. Vše běží v `initialize_database()`
(`core/database/database_initializer.py`): `Base.metadata.create_all` +
idempotentní `_ensure_*` / `_migrate_*`.

### 2.1 Co 3.1.0 nemělo (čistý release `ca1ade9`)

- celý modul `moduly/rizeni_rizik/` a tabulky `hazard_*`,
- `exposed_groups`,
- hierarchii pracovišť (`workplaces.parent_id`, `workplaces.item_type`),
- AI oponentní tabulky (`ai_peer_reviews`, …).

### 2.2 Pořadí (zjednodušeně)

| # | Krok | Typ |
|---|------|-----|
| 0 | Předmigrační `*.mbbackup` (pouze legacy) | ochrana |
| 1 | Import ORM modelů + `create_all` | nové tabulky |
| 2 | `_ensure_*` sloupce (tasks, accidents, …) | ADD COLUMN |
| 3 | `_ensure_workplace_hierarchy_columns` + backfill `operation` | R00 |
| 4 | `_ensure_exposed_groups_table` + seed | R16 |
| 5 | `_ensure_hazard_source_categories_table` + seed | UX-RISK-3 |
| 6 | Identifikace, inventura, události, posouzení, opatření, fotky | R01–R13 |
| 7 | Drop legacy `identified_hazards` / relations (jen pokud existují) | R12/R14 |
| 8 | Firemní knihovna vzorů + master catalog + legal links | R17–R19 |
| 9 | M:N ohrožené skupiny, drop `consequence` | R20c |
| 10 | AI tabulky | R11/R18/R19 |

### 2.3 Nové tabulky Registru rizik (výběr)

`hazard_identifications`, `hazard_inventory_items`, `hazard_events`,
`hazard_risk_assessments`, `hazard_risk_assessment_exposed_groups`,
`hazard_existing_measures`, `hazard_required_measures`,
`hazard_identification_photos`, `hazard_source_categories`,
`hazard_library_templates` (+ operations, events, assessments,
assessment_exposed_groups, measures, revisions, legal_links),
`exposed_groups`.

### 2.4 Opakovatelnost

`_ensure_*` kontrolují `PRAGMA table_info` / existenci tabulek – druhé spuštění
není destruktivní. Předmigrační záloha se pro stejný dokončený přechod
**nevytváří znovu** (detekce existence `hazard_identifications` + marker).

### 2.5 Datové transformace uživatelských dat 3.1.0

- stávající řádky evidence se **nemění** hodnotami seedu,
- `workplaces` dostanou `item_type='operation'` a `parent_id=NULL` (R00),
- seed číselníků ohrožených skupin / kategorií zdrojů jen doplní prázdné tabulky.

---

## 3. Předmigrační záloha

| Požadavek | Implementace |
|-----------|--------------|
| Před prvním zápisem schématu | `prepare_database_for_startup` → backup → teprve `initialize_database` |
| SQLite backup API | `create_instance_backup` → `create_sqlite_snapshot` |
| Obsah A+B + settings | stejné komponenty jako úplná instance záloha |
| Název | `zalohy/pre-migration-3.1.0-to-3.2.0-YYYYMMDD-HHMMSS.mbbackup` |
| Bez přepisu | `allocate_pre_migration_backup_path` (+ `-2`, `-3`, …) |
| Po úspěchu nemazat | ano |
| Selhání zálohy / verify | `PreMigrationBackupError` – migrace se nespustí, data beze změny |

---

## 4. Výsledky testů zachování dat

Test `test_upgrade_preserves_data_and_creates_pre_migration_backup`:

- počty řádků legacy tabulek beze změny,
- hodnoty zaměstnavatele / úkolu zachovány,
- přílohy, fotky, číselník, šablona, `sprava_dat.json` zachovány,
- absolutní `legal_documents.local_file_path` a `attachments.original_path`
  beze změny,
- všechny požadované `hazard_*` tabulky existují,
- `workplaces.parent_id` / `item_type` doplněny.

`test_risk_module_usable_after_upgrade`: vytvoření identifikace, položky
analýzy, zdroje rizika a nežádoucí události po migraci.

`test_post_migration_mbbackup_roundtrip`: nová `*.mbbackup` →
`inspect_backup_integrity` VALID → obnova do čistého adresáře zachová legacy
data i struktury rizik.

---

## 5. Opakované spuštění

`test_second_start_is_idempotent_without_new_pre_backup`:

- druhé `prepare_database_for_startup` → `migrated=False`,
- stále právě jedna předmigrační záloha,
- počty legacy řádků shodné.

---

## 6. Selhání

| Scénář | Chování |
|--------|---------|
| Záloha selže | migrace neběží; DB legacy beze změny |
| Pád uprostřed `initialize` | marker `in_progress` + ověřená záloha; další start → `MigrationIncompleteError` |
| Automatický rollback schématu | **není** – nutná obnova z předmigrační `*.mbbackup` |

### Nejmenší bezpečná budoucí oprava (návrh, neimplementováno zde)

Atomický swap: migrovat do kopie DB / staging workspace → teprve po úspěchu
přejmenovat (podobně jako BACKUP-2a). Do té doby stačí fail-closed + ruční
obnova z předmigrační zálohy.

---

## 7. Absolutní cesty (BACKUP-2d)

Migrace je **nepoškodí ani nepřepisuje**. Na stejném notebooku po výměně
AppImage zůstávají funkční, pokud cílové soubory existují.

---

## 8. Starý ZIP formát

Od BACKUP-2e již **není** v běžném UI. Zůstává jen interní kompatibilita
(`BackupService`, bezpečnostní ZIP před importy, testy).

---

## 9. Praktický postup na ostrý notebook (3.1.0)

1. **Doporučeno navíc:** ručně vytvořit zálohu ve 3.1.0 (ZIP / export), dokud
   běží stará verze.
2. Ukončit Manažer BOZP.
3. Nahradit AppImage / instalaci verzí **3.2.0** (datový adresář neměnit).
4. Spustit 3.2.0 a vyčkat dokončení prvního startu.
5. Ověřit v `zalohy/` soubor `pre-migration-3.1.0-to-3.2.0-….mbbackup`.
6. Spot-check: úkoly, úrazy, audity, právní požadavky, přílohy.
7. Otevřít Registr rizik – prázdný, bez chyby.
8. Ve Správě dat → Zálohování a obnova vytvořit novou `*.mbbackup`
   (jediný běžný formát úplné zálohy).

**Při chybě upgrade / nedokončené migraci:** nepokračovat v práci; obnovit z
`pre-migration-….mbbackup` (nebo ruční zálohy z kroku 1) a nahlásit problém.

---

## 10. Opravy provedené v MIGRATION-0

| Změna | Důvod |
|-------|-------|
| `core/database/upgrade_guard.py` | předmigrační záloha, markery, fail-closed |
| `main.py` | spouští `prepare_database_for_startup` místo holého `initialize_database` |
| `APP_VERSION` → 3.2.0 (+ `version_info.txt`, `installer.iss`) | cílová verze přechodu |
| E2E testy migrace | důkaz zachování dat a omezení |
| Tento dokument | mapa + verdikt + postup |

---

## 11. Závěr

Přechod 3.1.0 → 3.2.0 je **SAFE_TO_UPGRADE_WITH_LIMITATIONS**: automatická
předmigrační záloha a idempotentní migrace pokrývají hlavní riziko ztráty dat;
zbývá vědomé omezení absence automatického rollbacku schématu a známá omezení
absolutních cest / starého ZIP UI.
