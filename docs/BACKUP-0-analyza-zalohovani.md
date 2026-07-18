# BACKUP-0 – Analýza zálohování celé instance Manažera BOZP

Stav k 2026-07-19. Pouze podklad pro BACKUP-1+. **Bez změny chování.**

## Shrnutí verdiktu

| Otázka | Odpověď |
|--------|---------|
| Existuje úplná záloha pracovního prostoru? | **Ano** – ZIP „kompletní záloha“ přes `BackupService` (`typ_zalohy=celkova`). |
| Lze po čisté instalaci obnovit celý pracovní stav jen z dnešní zálohy? | **Téměř ano** pro data pod `StorageService.base`. **Ne úplně** – chybí UI téma (`data/nastaveni/`), absolutní cesty k AI/právním souborům mimo workspace, konzistence SQLite bez backup API, a současná obnova není atomická. |
| Existuje formát `*.mbbackup`? | **Ne** – dnes je to běžný `.zip` + `VERSION.json`. |
| Automatické / generační zálohy? | **Ne** – jen ruční a bezpečnostní `pred-obnovou-*` / `pred-importem-*`. |
| SQLite online backup / `PRAGMA integrity_check`? | **Ne**. |

---

## 1. Mapa dat a cest

### 1.1 Kanonický uživatelský workspace

Určuje `StorageService` (`core/services/storage_service.py`):

| Platforma | Kořen |
|-----------|--------|
| Linux (dev, AppImage, PyInstaller) | `~/.local/share/manazer-bozp` |
| Windows | `%LOCALAPPDATA%\manazer-bozp` |

- `APP_NAME = "manazer-bozp"`, DB soubor `manager_bozp.db`.
- **Nečte** `$XDG_DATA_HOME` ani vlastní env override.
- AppImage / Windows build **nemění** uživatelský kořen – liší se jen balíček (`sys._MEIPASS` přes `core/paths.py` → `project_root()`).

### 1.2 Položky workspace (vytváří `ensure_structure()`)

| Relativní cesta | Vytváří | Kategorie | Pro obnovu? | Přenositelná? | Absolutní cesty? |
|-----------------|---------|-----------|-------------|---------------|------------------|
| `databaze/manager_bozp.db` | `session` + `initialize_database()` | A | Ano | Ano (soubor) | Ne (cesta k DB je odvozená) |
| `prilohy/{entity}/{id}/…` | `AttachmentService`, fotky rizik | A/B | Ano | Ano | `stored_path` relativní k `prilohy/`; `original_path` absolutní (jen informace) |
| `prilohy/rizeni_rizik/…/fotografie/` | `HazardIdentificationPhotoService` | B | Ano | Ano | Relativní v DB |
| `control_results/…` | `ControlResultPhotoService` | B | Ano | Ano | Relativní ke kořeni workspace |
| `ciselniky/` | `EditableCatalogService` + metodiky + fotky referencí | A/B | Ano | Ano | Relativní v JSON |
| `templates/` | `ensure_default_templates()` | B | Ano | Ano | Ne |
| `konfigurace/sprava_dat.json` | `DataManagementSettingsService` | A | Ano | Částečně | Obsahuje absolutní cesty k zálohám/exportům |
| `export/` | Exportní služby | D (většinou) | Volitelně | Ano jako soubory | Ne |
| `import/` | Dialogy importů (staging) | D | Ne | — | — |
| `logy/` | Adresář existuje | D | Ne | — | Dnes bez zápisu z app kódu |
| `zalohy/` | `BackupService` | D / provoz | Ne do ZIP (vyloučeno) | Ano jako archivy | Cesty v metadatech absolutní |

Lazy podsložky (fotky audity/prověrky pod `ciselniky/…/fotografie/`) vznikají při ukládání referenčních fotek.

### 1.3 Data mimo workspace

| Položka | Cesta / určení | Vytváří | Pro obnovu? | Přenositelná? | Absolutní cesty? |
|---------|----------------|---------|-------------|---------------|------------------|
| UI téma / maximalizace okna | `data/nastaveni/settings.json` (**CWD-relativní**) | `SettingsManager` (`main.py`) | Ano pro UX, ale **není v ZIP** | Ne (závisí na CWD) | Relativní k CWD |
| Seed číselníků / šablon | `{project_root}/ciselniky/`, `moduly/*/templates/` | Balíček aplikace | Ne (znovu seed) | Ano | — |
| Statické katalogy úrazů | `moduly/kniha_urazu/data/*.json` | Balíček | Ne | Ano | — |
| AI export ZIP | Uživatel volí dialogem | `ai_peer_review_service` | Jen pokud je v DB absolutní `export_file_path` a soubor existuje | **Ne** | **Ano** v DB |
| Lokální soubory předpisů | `legal_documents.local_file_path` | Uživatel | Jen pokud soubor existuje | Často **ne** | Často **ano** |
| Repo `data/` (dev) | CWD při běhu z repa | Legacy | Ne do kompletní zálohy | Ne | — |

### 1.4 Rozdíly běhů

| Aspekt | Vývoj | AppImage / PyInstaller | Windows |
|--------|-------|------------------------|---------|
| Workspace | `~/.local/share/manazer-bozp` | Stejně | `%LOCALAPPDATA%\manazer-bozp` |
| Bundle | kořen repo | `sys._MEIPASS` | Stejně jako AppImage |
| Theme settings | `./data/nastaveni/` dle CWD | Dle CWD procesu | Stejné riziko |
| Override dat | Ne | Ne | Ne |

---

## 2. Klasifikace dat

### A) Kritická data – **součást úplné zálohy**

- SQLite `databaze/manager_bozp.db` (evidence, číselníky v DB, zaměstnavatel, vazby, AI metadata, …).
- Editovatelné `ciselniky/` (uživatelské úpravy metodik).
- `konfigurace/` (stav Správy dat, poslední zálohy).
- Přílohy a fotky s relativními cestami v DB (`prilohy/`, `control_results/`, metodické fotky).

Bez A uživatel přijde o evidenci.

### B) Důležitá doprovodná data – **součást úplné zálohy**

- `templates/` (uživatelské kopie ODT/…),
- podepsané / exportované dokumenty uložené **uvnitř** workspace,
- referenční fotografie metodik.

### C) Odvoditelná data – **volitelně / spíše ne**

- Seedované výchozí šablony a katalogy (obnoví se z balíčku při `ensure_*`).
- Regenerovatelné exporty (protokoly, zprávy) – pokud nejsou jediným důkazem.

Doporučení: v úplné záloze **nechat** `templates/` a `ciselniky/` (uživatelské změny); regenerovatelné výstupy v `export/` mohou být volitelné.

### D) Dočasná a provozní data – **ne / mimo balíček instance**

- `zalohy/` (archivy záloh – rekurze),
- `import/` staging,
- `logy/`,
- `tempfile` při obnově,
- CWD `data/nastaveni/` (dnes mimo workspace – mezera).

---

## 3. Současný stav zálohování

### 3.1 Jádro

| Soubor | Role |
|--------|------|
| `core/services/backup_service.py` | `BackupService` – ZIP create/restore |
| `core/services/backup_manifest_service.py` | Manifest / „integrity“ ZIP |
| `core/services/attachment_backup_diagnostic_service.py` | Kontrola příloh vs DB |
| `core/services/storage_service.py` | Kořen workspace |
| `moduly/sprava_dat/sluzby/full_backup_workflow_service.py` | UI workflow + metadata |
| `moduly/sprava_dat/sluzby/data_management_settings_service.py` | `sprava_dat.json` |

### 3.2 UI vstupy

| Místo | Akce |
|-------|------|
| Dashboard – „Záloha“ / „Obnova“ | Kompletní záloha / obnova |
| Správa dat → Zálohování | Totéž + historie / otevření cesty |
| Správa dat → Přenos dat | JSON registr + bezpečnostní ZIP před importem |
| Správa dat → Číselníky | Export/import číselníků; bulk import se safety ZIP |

### 3.3 Co se skutečně zálohuje

**Kompletní záloha (`BACKUP_TYPE_FULL`):** celý strom `storage_service.base` **kromě** `zalohy/` a cílového ZIP. Obsahuje tedy DB, přílohy, control_results, ciselniky, templates, export, konfigurace, import, logy, …

Formát: `.zip` + `VERSION.json` (`program`, `verze`, `typ`, `typ_zalohy`, `vytvoreno`, absolutní `root`, `obsah`, …).

Částečné typy `databaze` a `ciselniky-sablony` existují v kódu, **UI je nenabízí**.

### 3.4 Co se nezálohuje

- `zalohy/` (záměrně),
- `data/nastaveni/settings.json` (mimo workspace),
- soubory mimo workspace (AI export path, `local_file_path` předpisů),
- obsah AppImage / instalace.

### 3.5 Kontrola úspěšnosti

- ZIP `testzip()` (CRC),
- přítomnost `databaze/manager_bozp.db`,
- parse `VERSION.json`,
- diagnostika chybějících příloh → `backup_health` warning/failed,
- po create: při `verified=False` se ZIP maže,
- před obnovou: ověřená bezpečnostní záloha (`restore_backup_with_verified_safety`).

**Není:** `PRAGMA integrity_check`, `sqlite3.backup()`, kontrola místa na disku, path-traversal ochrana při `extractall`.

### 3.6 Ověřená obnova

- UI: `FullBackupWorkflowService.restore_full_backup` → restart aplikace.
- Testy: `test_attachment_backup_phase_92a.py` (obnova chybějící přílohy), dashboard/správa dat suite.
- Algoritmus: extract do temp → `_replace_item` (smazat cíl + `copytree`/`copy2`) – **ne atomický swap celého kořene**.

### 3.7 Související export/import (ne havarijní záloha)

| Mechanismus | Formát | Účel |
|-------------|--------|------|
| Registr právních požadavků | JSON | Přenos registru |
| Číselníky | JSON / ZIP + MANIFEST | Přenos číselníků |
| AI proposal packages | ZIP schémat | Import návrhů |
| Hazard catalog importy | vlastní | Katalog |

---

## 4. Test obnovitelnosti

### Otázka

> Lze po čisté instalaci Manažera BOZP obnovit celý pracovní stav pouze z dnešní kompletní zálohy?

### Odpověď

**Ano pro jádro evidence** (DB + relativní soubory ve workspace), pokud:

1. uživatel obnoví kompletní ZIP do stejného typu OS / očekávaného workspace,
2. po obnově proběhne start + `initialize_database()` (migrace),
3. přílohy v ZIP odpovídají DB (jinak warning už při záloze).

**Selže nebo bude neúplné:**

| Oblast | Problém |
|--------|---------|
| UI theme / window | `settings.json` mimo ZIP |
| AI export soubory | Absolutní `export_file_path` – na jiném PC soubor chybí |
| Lokální PDF předpisů | Absolutní `local_file_path` |
| Metadata Správy dat | Absolutní cesty k starým ZIP v `sprava_dat.json` (funkčnost evidence OK, odkazy „Otevřít“ ne) |
| Konzistence DB | ZIP za běhu bez SQLite backup API → riziko poškozené kopie |
| Obnova mid-failure | `_replace_item` po položkách – napůl obnovený stav možný |
| Linux ↔ Windows | Workspace cesty se liší; relativní obsah OK, absolutní metadata ne; konce řádků v textech obvykle OK |
| Linux → Linux / Win → Win | Relativní obsah přenositelný; `VERSION.json.root` je jen metadata |

---

## 5. Konzistence SQLite

| Téma | Stav |
|------|------|
| Journal mode | Explicitně nenastaveno → typicky **DELETE**, ne WAL (pokud uživatel/OS nezměnil) |
| `-wal` / `-shm` | V kódu neřešeno; při WAL by se musely zálohovat spolu / použít API |
| Session | Globální SQLAlchemy `engine` + `SessionLocal` (`core/database/session.py`) |
| Kopírování za běhu | ZIP bere soubor(y) z disku **bez** `sqlite3.Connection.backup()` |
| Integrity | Žádný `PRAGMA integrity_check` v záloze |
| Schéma | Imperativní migrace v `database_initializer.py` – **bez tabulky schema_version** |

### Doporučený bezpečný postup (pro BACKUP-1+)

1. Uzavřít / pozastavit zápisy (ideálně před ukončením, nebo short exclusive lock).
2. Vytvořit konzistentní kopii přes **`sqlite3.backup()`** (nebo `VACUUM INTO` na cílový soubor).
3. Do balíčku vložit jen hotovou kopii DB.
4. Spustit `PRAGMA integrity_check` na kopii; výsledek do metadat.
5. Teprve potom hashovat a uzavřít archiv.

---

## 6. Cílový balíček úplné zálohy (`*.mbbackup`)

### 6.1 Požadavky

- Jeden přenositelný soubor = havarijní obnova instance.
- Oddělený od budoucích knowledge balíčků (`*.mbcatalog`, …).
- Vnitřně ZIP (nebo zip-compatible) s pevnou strukturou a validací.

### 6.2 Navrhovaná vnitřní struktura

```text
archive.mbbackup          # prakticky ZIP s příponou .mbbackup
├── metadata.json         # formát, verze, checksumy, integrity
├── database/
│   └── manager_bozp.db   # konzistentní kopie (backup API)
├── files/
│   ├── prilohy/…
│   ├── control_results/…
│   ├── ciselniky/…
│   ├── templates/…
│   └── konfigurace/…     # bez zbytečných absolutních cest, nebo s remap poznámkou
└── optional/             # volitelné
    └── export/…          # jen pokud uživatel zvolí „včetně exportů“
```

`zalohy/`, `import/`, `logy/` defaultně **nezahrnovat**.

Legacy kompatibilita: BACKUP-1b může umět **číst** dnešní `manager-bozp-backup-celkova-*.zip` jako importní zdroj.

### 6.3 Oddělení od knowledge exportu

Magic / `package_kind` v metadata:

- `instance_backup` → `*.mbbackup`
- budoucí `knowledge_catalog` → `*.mbcatalog` (jiný kind, jiný importer)

Stejný ZIP kontejner je OK; **nesmí** se zaměnit při obnově instance.

---

## 7. Metadata (`metadata.json`)

### Doporučené pole

| Pole | Účel | Citlivost |
|------|------|-----------|
| `format_version` | Verze formátu balíčku | Nízká |
| `package_kind` | `instance_backup` | Nízká |
| `created_at` | ISO čas | Nízká |
| `app_version` | `APP_VERSION` | Nízká |
| `platform` | `Linux` / `Windows` | Nízká |
| `schema_fingerprint` | Hash názvů tabulek/sloupců nebo budoucí schema_version | Nízká |
| `components[]` | Co je uvnitř | Nízká |
| `counts` | Počty hlavních entit (úrazy, úkoly, …) | Střední (ne jména) |
| `file_sizes` | Velikosti komponent | Nízká |
| `checksums` | SHA-256 souborů / celku | Nízká |
| `db_integrity` | Výsledek `integrity_check` | Nízká |
| `instance_id` | Náhodné UUID instance (ne IČO/jméno firmy) | Nízká |

### Neukládat bez důvodu

- Název firmy, IČO, jména osob,
- absolutní `root` cesty (dnes v `VERSION.json` – nahradit),
- obsah poznámek / exportů v metadatech.

---

## 8. Návrh bezpečné obnovy

1. Výběr `*.mbbackup` (a dočasně legacy ZIP).
2. Validace přípony / `package_kind` / `format_version`.
3. Kontrola checksumů + ZIP CRC.
4. Náhled: app verze, datum, counts, velikost, platforma.
5. Explicitní varování: současná data budou nahrazena.
6. Automatická bezpečnostní záloha současného stavu (ověřená).
7. Rozbalení do temp **s ochranou proti path traversal** (žádné `..`, žádné absolutní cesty v ZIP).
8. Ověření DB (`integrity_check`) a existence klíčových souborů dle DB.
9. **Atomická výměna:** připravit nový workspace vedle → rename swap (nebo výměna jednoho staging kořene); při chybě rollback na safety.
10. Restart aplikace.
11. Při chybě: ponechat safety + původní stav; nikdy napůl přepsaný kořen.

Obnova musí běžet bez paralelních zápisů do DB (ideálně modal + quit writers / restart-first).

---

## 9. Bezpečnost

| Riziko | Dnes | Cíl |
|--------|------|-----|
| ZIP path traversal | `extractall` bez filtru | Whitelist relativních cest pod temp |
| Přepis mimo workspace | `_replace_item` jen pod `base`, ale extract může obsahovat `..` | Validace členů ZIP před extract |
| Poškozený balíček | CRC + DB presence | + checksums + integrity_check |
| Absolutní cesty v ZIP | Relativní zápis OK | Odmítnout absolutní členy |
| Záměna s importem | Různé dialogy | `package_kind` + oddělené přípony |
| Málo místa | Neřešeno | Preflight free space ≥ 2× velikost |
| Obnova za zápisu | Možná | Lock / quit DB sessions |
| Šifrování | Ne | Budoucí volitelná funkce (heslo / OS keychain); zatím neblokuje formát |

Šifrování: vhodné jako **volitelné** (citlivá evidence úrazů/osob); základní formát má zůstat čitelný pro support.

---

## 10. Automatické zálohy (návrh, neimplementovat)

### Spouštěče

- při ukončení aplikace (best-effort, timeout),
- jednou denně při prvním startu dne,
- před migrací schématu,
- před obnovou (už dnes safety),
- před rizikovým hromadným importem (částečně dnes).

### Generační politika (návrh)

| Generace | Retence |
|----------|---------|
| Denní | posledních 7 |
| Týdenní | posledních 4 |
| Měsíční | posledních 6 |
| Safety (`pred-*`) | posledních 10 nebo max 2 GB ve `zalohy/` |

Ukládat do `zalohy/` mimo `*.mbbackup` uživatelské „uložit jako“.

---

## 11. Budoucí exportní balíčky

### A) Úplná záloha instance – `*.mbbackup`

- Havarijní obnova / stěhování stejné instance.
- Obsahuje provozní a potenciálně citlivá data.
- Cíl: pokračovat ve stejné evidenci.

### B) Export znalostí – např. `*.mbcatalog`

- Přenos vybrané odborné databáze (např. Katalog zdrojů rizik).
- **Neobsahuje** běžná provozní data firmy (úrazy, úkoly, osoby…).
- Cíl: import do jiné instance.

`metadata.package_kind` a oddělené přípony zajistí, že obnovovač instance **odmítne** knowledge balíček a naopak.

Detail Katalogu se v BACKUP-0 nenavrhuje.

---

## 12. Mezery dnešního řešení (shrnutí)

1. Formát není dedikovaný (`zip` vs `mbbackup`) a metadata obsahují absolutní `root`.
2. DB se nekopíruje přes SQLite backup API; chybí `integrity_check`.
3. Obnova není atomická; riziko napůl obnoveného stavu.
4. Path traversal při `extractall` neřešen.
5. Theme settings mimo workspace.
6. Absolutní cesty k externím souborům se „obnoví“ jen jako text v DB.
7. Žádná rotace / automatické zálohy.
8. Částečné typy zálohy bez UI; naming „integrity“ ≠ SQLite integrity.
9. Není schema_version – kompatibilita jen přes app version + migrace při startu.

---

## 13. Doporučené implementační fáze

| Fáze | Obsah | Stav |
|------|--------|------|
| **BACKUP-1a** | Společný formát balíčku + `metadata.json` (`package_kind`, checksumy). | Hotovo (`core/backup/`, docs BACKUP-1a) |
| **BACKUP-1b** | Vytvoření úplné zálohy `*.mbbackup` (SQLite backup API + komponenty A/B). | Hotovo (`create_instance_backup`, docs BACKUP-1b) |
| **BACKUP-1c** | Kontrola integrity (CRC, checksums, `PRAGMA integrity_check`, attachment gaps). | Hotovo (`inspect_backup_integrity`, docs BACKUP-1c; attachment gaps později) |
| **BACKUP-2a** | Bezpečná obnova: náhled, varování, path-safe extract, staging + atomický swap, restart. | Hotovo (API `restore_instance_backup`, docs BACKUP-2a; UI/náhled později) |
| **BACKUP-2b** | Rollback při chybě na ověřenou safety zálohu; preflight disk space. | Hotovo (auto-rollback + recovery marker, docs BACKUP-2b) |
| **BACKUP-2c** | UI ruční zálohy / ověření / obnovy `*.mbbackup` + marker při startu. | Hotovo (docs BACKUP-2c) |
| **BACKUP-3** | Automatické + generační zálohy; limity velikosti `zalohy/`. | Plán |
| **BACKUP-4** (volitelně) | Přesun `SettingsManager` do workspace; remap/varování absolutních cest; volitelné šifrování. | Plán |

Paralelně nesmí vzniknout kolize s budoucím `*.mbcatalog`.

---

## 14. Testy / odkazy na existující pokrytí

| Oblast | Soubory |
|--------|---------|
| Formát / metadata `*.mbbackup` | `tests/test_backup_1a_format_metadata.py` |
| Vytvoření úplné zálohy `*.mbbackup` | `tests/test_backup_1b_create_instance_backup.py` |
| Ověření integrity `*.mbbackup` | `tests/test_backup_1c_integrity.py` |
| Bezpečná obnova `*.mbbackup` | `tests/test_backup_2a_restore_instance_backup.py` |
| Rollback při selhání obnovy | `tests/test_backup_2b_restore_rollback.py` |
| UI zálohy a obnovy `*.mbbackup` | `tests/test_backup_2c_ui.py` |
| Kompletní záloha UI (legacy ZIP) | `tests/test_sprava_dat_backup.py`, `tests/test_dashboard_backup_restore_phase_88.py` |
| Přílohy v ZIP / obnova | `tests/test_attachment_backup_phase_92a.py`, `92b` |
| Workspace init | `tests/test_workspace_init_phase_95a.py` |

---

## 15. Závěr

Manažer už má funkční **kompletní ZIP zálohu workspace** a ověřenou obnovu s bezpečnostní kopií. Pro prohlášení „úplná přenositelná záloha celé instance“ chybí zejména: konzistentní SQLite snapshot, atomická obnova, bezpečný formát s metadaty bez citlivostí, pokrytí UI nastavení mimo workspace a politika automatických generací.

Tento dokument je vstupem pro BACKUP-1a bez změny produkčního kódu.
