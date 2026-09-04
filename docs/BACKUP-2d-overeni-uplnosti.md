# BACKUP-2d – Ověření úplnosti zálohy celé aplikace

Stav k 2026-07-19. Audit datových úložišť oproti aktuálnímu `*.mbbackup` (formát v1),
end-to-end čistá obnova a verdikt úplnosti.

**Kód:** `core/backup/completeness.py`  
**Testy:** `tests/test_backup_2d_completeness_e2e.py`

---

## Verdikt

### **COMPLETE_WITH_LIMITATIONS**

Kritická a důležitá uživatelská data (kategorie A+B) se v defaultní úplné záloze
`*.mbbackup` obnoví do čisté instance včetně relativních příloh, číselníků, šablon
a UI `settings.json`. Po přesunu mezi různými kořenovými cestami zůstávají
souborové odkazy v DB funkční, pokud jsou relativní vůči workspace.

Záloha **není** verdikt COMPLETE, protože:

1. AI export ZIP a lokální právní PDF mimo workspace se zálohují jen jako absolutní
   text v DB – soubory na cílovém PC chybí.
2. `attachments.original_path` zůstává absolutní (historie importu).
3. `konfigurace/sprava_dat.json` může obsahovat absolutní cesty k minulým zálohám.
4. `export/`, `zalohy/`, `import/`, `logy/` nejsou v defaultní záloze (záměr).

Produkční seznam `BACKUP_WORKSPACE_ROOTS` musí obsahovat `snapshot_support_photos`.
Neznámý kořen první úrovně workspace → verdikt `INCOMPLETE` (kořen se do archivu nevkládá).
Starší `*.mbbackup` bez deklarovaného pokrytí tohoto kořene lze obnovit; kontrola
vrátí `VALID_WITH_WARNINGS` / `COMPLETE_WITH_LIMITATIONS`, nikoli poškození archivu.

---

## 1. Mapa nalezených datových úložišť

Audit prošel aktuální kód (`StorageService`, služby příloh/fotek, AI, právní
předpisy, Správa dat, `SettingsManager`, cesty AppImage/`project_root`), nejen BACKUP-0.

### 1.1 Workspace (`StorageService.base`)

| Relativní cesta | Zápis / čtení | Kategorie | V `*.mbbackup`? | Forma | Po přesunu PC |
|-----------------|---------------|-----------|-----------------|-------|---------------|
| `databaze/manager_bozp.db` | SQLAlchemy session | A | Ano (`database/`) | Soubor (SQLite backup API) | Ano |
| `prilohy/{entity}/{id}/…` | `AttachmentService` | A | Ano | Soubor + relativní `stored_path` | Ano |
| `prilohy/rizeni_rizik/…/fotografie/` | `HazardIdentificationPhotoService` | B | Ano | Soubor + `relative_path` | Ano |
| `control_results/…` | `ControlResultPhotoService` | B | Ano | Soubor + relativní `photo_path` | Ano |
| `ciselniky/` | `EditableCatalogService`, metodiky, referenční fotky | A/B | Ano | Soubory JSON/JPG | Ano |
| `templates/` | uživatelské ODT + `ensure_default_templates` | B | Ano | Soubory | Ano |
| `konfigurace/sprava_dat.json` | `DataManagementSettingsService` | A | Ano | JSON (často absolutní cesty k ZIP) | Evidence OK; odkazy „Otevřít“ ne |
| `snapshot_support_photos/` | zmrazené fotky metodické podpory auditů | A | Ano | Soubor SHA-adresovaný | Ano |
| `export/` | exportní služby | D | Ne (volitelně `include_exports`) | Soubory | — |
| `import/` | staging dialogů | D | Ne | Dočasné | — |
| `logy/` | provoz | D | Ne | — | — |
| `zalohy/` | `BackupService` / mbbackup | D | Ne (rekurze) | Archivy | — |

### 1.2 Mimo workspace

| Položka | Umístění | Kategorie | V `*.mbbackup`? | Forma | Po přesunu |
|---------|----------|-----------|-----------------|-------|------------|
| UI téma / okno | `data/nastaveni/settings.json` (CWD) | A (UX) | Ano (`settings/`) | Soubor | Ano, pokud obnova cílí na nový settings path |
| AI export ZIP | dialog uživatele | B (doprovod) | **Jen odkaz** v `ai_peer_reviews.export_file_path` | Absolutní cesta | **Ne** (soubor chybí) |
| Lokální PDF předpisů | `legal_documents*.local_file_path` | B | **Jen odkaz** | Absolutní cesta | **Ne** |
| Seed číselníků / šablon | `{project_root}/…`, `moduly/*/templates/` | C | Ne | Balíček app | Obnoví se ze seedu |
| Statické katalogy | `moduly/*/data/*.json` | C | Ne | Balíček | — |

### 1.3 Platformní kořeny

| Běh | Workspace | Bundle (`project_root`) | Settings |
|-----|-----------|-------------------------|----------|
| Vývoj (Linux) | `~/.local/share/manazer-bozp` | kořen repo | `./data/nastaveni/` dle CWD |
| AppImage / PyInstaller | stejný XDG base | `sys._MEIPASS` | stejné riziko CWD |
| Windows | `%LOCALAPPDATA%\manazer-bozp` | `_MEIPASS` / instalace | stejné |

Testy používají dočasné `workspace_root` / `settings_path` a **nezávisí** na
skutečném domácím adresáři.

---

## 2. Porovnání s obsahem `*.mbbackup`

### Zahrnuto správně

- SQLite evidence (včetně metadat AI/právních záznamů, úkolů, úrazů, auditů, …)
- `prilohy/`, `control_results/`, `ciselniky/`, `templates/`, `konfigurace/`, `snapshot_support_photos/`
- `settings/settings.json`

### Zahrnuto částečně

| Zdroj | Co je v balíčku | Co chybí |
|-------|-----------------|----------|
| AI peer review | řádek DB + absolutní `export_file_path` | samotný ZIP mimo workspace |
| Právní dokumenty | řádek DB + `local_file_path` | PDF/soubor mimo workspace |
| Správa dat | `sprava_dat.json` | funkční absolutní odkazy na staré zálohy |

### Nezahrnuto (záměrně / není potřeba)

- `export/`, `zalohy/`, `import/`, `logy/`
- seed balíčku aplikace (C)
- obsah AppImage / Windows instalace

### Klasifikace (shrnutí)

| Stav | Položky |
|------|---------|
| Zahrnuto správně | DB A, přílohy/fotky s relativními cestami, číselníky, šablony, konfigurace, settings |
| Zahrnuto částečně | AI export path, legal `local_file_path`, absolutní cesty v `sprava_dat.json` |
| Nezahrnuto | provozní `export/`/`zalohy/`/`import/`/`logy/` |
| Není potřeba | seed C, cache/temp |

---

## 3. Výsledky čisté obnovy (E2E)

Scénář `test_e2e_clean_restore_between_different_roots`:

1. Zdrojová instance pod `machine-A/…` s reprezentativními daty (firma, úkoly,
   úrazy, přílohy s českým názvem, fotky rizik/auditů, číselník, šablona,
   procesy, AI + legal absolutní cesty, settings).
2. `create_instance_backup` → `*.mbbackup`.
3. Cíl `machine-B-clean/…` jako prázdná instalace.
4. `restore_instance_backup` do nového workspace + settings.
5. `compare_instances()`:

| Kontrola | Výsledek |
|----------|----------|
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA user_version` | shoda |
| Seznam tabulek + počty řádků | shoda |
| Inventář A+B (cesta, size, SHA-256) | shoda |
| Souborové odkazy z DB (relativní) | existují |
| Settings SHA-256 | shoda |
| České názvy souborů | OK |
| Přesun mezi kořeny | OK |
| `export/` po obnově | chybí (očekáváno) |
| Verdikt srovnání | `COMPLETE_WITH_LIMITATIONS` |

Negativní kontrola: smazání přílohy po obnově → `INCOMPLETE`.

---

## 4. Absolutní cesty

| Tabulka.sloupec | Klasifikace | Rozhodnutí |
|-----------------|-------------|------------|
| `attachments.original_path` | `history` | Nezálohovat zdroj; text v DB stačí |
| `attachments.stored_path` (absolutní) | `architecture_issue` | Má být relativní k `prilohy/`; diagnostika už existuje |
| `ai_peer_reviews.export_file_path` | `external` | Soubor mimo workspace – v defaultní záloze ne |
| `legal_documents.local_file_path` | `external` | Totéž |
| `legal_document_versions.local_file_path` | `external` | Totéž |
| `konfigurace/sprava_dat.json` → last backup path | provozní metadata | Text v JSON; odkaz po přesunu neplatí |

API: `scan_absolute_paths()`, `classify_absolute_path()`.

---

## 5. Známá omezení

1. Externí AI/právní soubory nejsou v balíčku – po stěhování PC zůstane jen DB odkaz.
2. Historie `original_path` a cesty v `sprava_dat.json` nejsou remapované.
3. Defaultní záloha nekopíruje `export/` (regenerovatelné / D).
4. Aplikace stále nemá jednotnou tabulku `schema_version`; porovnává se
   `PRAGMA user_version` (často 0) + shoda schématu přes tabulky/řádky.
5. Budoucí zlepšení (mimo 2d): kopírování externích souborů do workspace,
   remap cest, případně formát v2 – jen pokud produkt vyžaduje přenos AI/PDF.

---

## 6. Opravy v této fázi

| Změna | Důvod |
|-------|-------|
| Nový modul `core/backup/completeness.py` | Inventář, porovnání instance, sken absolutních cest |
| Export API v `core/backup/__init__.py` | Veřejné `compare_instances`, verdikty |
| E2E testy `tests/test_backup_2d_completeness_e2e.py` | Důkaz čisté obnovy a detekce mezer |
| Tento dokument | Audit + verdikt |

**Poznámka (FULL-BACKUP-SNAPSHOT-PHOTOS-1):** `DEFAULT_WORKSPACE_INCLUDE_DIRS`
nyní zahrnuje `snapshot_support_photos`. Metadata v1 zůstávají zpětně čitelná;
přibyla volitelná pole `included_workspace_roots` a `unknown_workspace_roots`.

---

## 7. Testovací pokrytí

| Požadavek | Test |
|-----------|------|
| E2E create → restore do prázdné instance | `test_e2e_clean_restore_between_different_roots` |
| Počty uživatelských záznamů | totéž (`row_counts_*`) |
| Soubory + SHA-256 | `inventory_workspace_files` + compare |
| Odkazy z DB | `check_db_file_references` |
| Settings | hash match + JSON `language` |
| Číselníky + šablony | assert existence po obnově |
| Český název souboru | `Protokol úrazu.pdf` |
| Dva různé kořeny | `machine-A` → `machine-B-clean` |
| Detekce INCOMPLETE | `test_missing_attachment_file_marks_incomplete` |

---

## 8. Závěr

Defaultní `*.mbbackup` je **obnovitelná úplná záloha evidence a workspace A+B**
včetně UI settings, s přesně popsanými omezeními u externích absolutních cest
a provozních adresářů. Verdikt: **COMPLETE_WITH_LIMITATIONS**.
