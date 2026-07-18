# BACKUP-1b – Vytvoření úplné zálohy `*.mbbackup`

Cíl: vytvořit první úplnou zálohu celé instance Manažera BOZP ve formátu
definovaném v [BACKUP-1a](BACKUP-1a-format-a-metadata.md).

**Bez obnovy, bez UI, bez automatických / generačních záloh.**

Modul: `core/backup/` (`package_create.py`, `package_verify.py`, `sqlite_snapshot.py`).

---

## 1. Veřejné API

```python
from core.backup import create_instance_backup, verify_instance_backup_package

result = create_instance_backup("/cesta/zaloha.mbbackup")
# result.path, result.metadata, result.database_integrity
```

Parametry (volitelné):

| Parametr | Význam |
|----------|--------|
| `workspace_root` | Kořen instance (výchozí `StorageService.base`) |
| `database_path` | Cesta k SQLite (výchozí `…/databaze/manager_bozp.db`) |
| `settings_path` | UI `settings.json` (jinak `SettingsManager` / `data/nastaveni/`) |
| `include_exports` | Pokud `True`, zahrne i `export/` (jinak ne – kategorie D) |
| `verify` | Po zápisu ověřit balíček (výchozí `True`) |
| `interrupt_hook` | Testovací/interní háček po fázích |

Stávající `BackupService` (ZIP + `VERSION.json`) zůstává beze změny.

---

## 2. Obsah balíčku

Mapování podle BACKUP-0 (kategorie A+B) a struktury BACKUP-1a:

```text
archive.mbbackup
├── metadata.json
├── database/
│   └── manager_bozp.db      # konzistentní kopie (SQLite backup API)
├── workspace/
│   ├── prilohy/…
│   ├── control_results/…
│   ├── ciselniky/…
│   ├── templates/…
│   └── konfigurace/…
└── settings/
    └── settings.json          # pokud existuje (UI téma / okno)
```

### Zahrnuto

- SQLite evidence (`database/`)
- `prilohy/`, `control_results/`, `ciselniky/`, `templates/`, `konfigurace/`
- UI nastavení do `settings/` (mezera z BACKUP-0)

### Nezahrnuto (kategorie D / provoz)

- `zalohy/` (prevence rekurze)
- `import/`, `logy/`
- `export/` (volitelně přes `include_exports=True`)
- `databaze/` jako kopie souboru – DB jde výhradně přes backup API

---

## 3. Konzistence databáze

`create_sqlite_snapshot()`:

1. otevře zdrojovou DB v režimu read-only URI,
2. vytvoří cíl přes `sqlite3.Connection.backup` (po stránkách),
3. spustí `PRAGMA integrity_check` na kopii,
4. při neúspěchu snapshot smaže a selže.

Obyčejné `shutil.copy` živého DB souboru se **nepoužívá**.

Do metadat se ukládá `database_integrity` (typicky `"ok"`) a případně
`schema_version` z `PRAGMA user_version` (pokud je nenulová).

---

## 4. Dočasné soubory a atomické dokončení

1. Staging adresář vedle cíle (`mbbackup-staging-*`).
2. Zápis do `cil.mbbackup.partial`.
3. `metadata.json` se stavem `complete`.
4. Ověření partial balíčku.
5. `os.replace(partial, cil.mbbackup)`.

Při chybě / přerušení:

- smaže se `.partial`,
- smaže se staging,
- cílový `*.mbbackup` se **nevydá** jako výsledek této neúspěšné operace.

---

## 5. Kontrola po vytvoření

`verify_instance_backup_package()` kontroluje:

- příponu `.mbbackup`,
- načtení a validaci `metadata.json` (stav `complete`, kind `instance_backup`),
- přítomnost všech souborů z manifestu,
- shodu velikostí a SHA-256,
- přítomnost databázové komponenty,
- bezpečné relativní cesty v ZIP.

Při chybě ověření se partial maže a API vyhodí `InstanceBackupError`.

---

## 6. Testy

`tests/test_backup_1b_create_instance_backup.py` pokrývá mimo jiné:

- platný `*.mbbackup`,
- metadata a manifest,
- kontrolní součty,
- partial + atomické dokončení,
- přerušení vytváření,
- poškozený soubor,
- úplnost balíčku,
- SQLite snapshot bez file-copy.

---

## 7. Co záměrně chybí

- obnova instance,
- napojení na menu / UI Správy dat,
- automatické a generační zálohy,
- změna legacy ZIP workflow.
