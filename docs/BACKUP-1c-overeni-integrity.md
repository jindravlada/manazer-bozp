# BACKUP-1c – Ověření integrity záložního balíčku

Cíl: důkladná kontrola `*.mbbackup`, aby bylo možné s vysokou jistotou říci,
že záloha je použitelná pro budoucí obnovu.

**Bez obnovy, bez UI, bez automatických záloh.**

Modul: `core/backup/package_integrity.py` (+ rozšíření SQLite a metadat).

---

## 1. Veřejné API

```python
from core.backup import inspect_backup_integrity, assert_backup_integrity

report = inspect_backup_integrity("/cesta/zaloha.mbbackup")
print(report.status)   # VALID | VALID_WITH_WARNINGS | INVALID
print(report.ok)       # True pro VALID / VALID_WITH_WARNINGS
print(report.issues)   # seznam problémů s kódem a závažností
```

| Funkce | Chování |
|--------|---------|
| `inspect_backup_integrity(path)` | Vždy vrátí `BackupIntegrityReport` (nevyhazuje při INVALID) |
| `assert_backup_integrity(path)` | Při `INVALID` vyhodí `BackupPackageVerificationError` |
| `verify_instance_backup_package(path)` | Přísná obálka pro BACKUP-1b (vrací metadata) |

---

## 2. Souhrnný výsledek

| Status | Význam |
|--------|--------|
| `VALID` | Všechny kontroly OK |
| `VALID_WITH_WARNINGS` | Použitelné, ale s varováními (např. prázdné schéma DB) |
| `INVALID` | Záloha není považována za použitelnou |

Každý problém má:

- `code` (např. `hash_mismatch`, `bad_zip`),
- `message`,
- `severity` (`error` / `warning`).

---

## 3. Co se kontroluje

### Archiv

- čitelnost ZIP,
- přípona `.mbbackup` (u partial během tvorby výjimka),
- přítomnost `metadata.json`,
- `format_version`, `package_kind=instance_backup`, `package_status=complete`,
- povinné komponenty `database` / `workspace` / `settings`.

### Manifest a soubory

- existence všech položek,
- velikost,
- SHA-256,
- duplicitní cesty,
- nebezpečné cesty.

### Databáze (extrakce do temp)

- `PRAGMA integrity_check`,
- `PRAGMA quick_check`,
- shoda velikosti s metadaty / manifestem,
- detekce prázdné DB (`database_empty`).

Výsledky se ukládají do `metadata.json` při tvorbě (BACKUP-1b):

- `database_integrity`
- `database_quick_check`
- `database_size`
- `database_empty`

---

## 4. Vazba na tvorbu zálohy

Po vytvoření (a před atomickým přejmenováním) BACKUP-1b volá ověření přes
`verify_instance_backup_package` → `inspect_backup_integrity`.

Neplatný balíček se nevydá jako dokončený `*.mbbackup`.

---

## 5. Testy

`tests/test_backup_1c_integrity.py` – poškozený ZIP, chybějící metadata,
špatná verze, chybějící/poškozená DB, chybějící soubor, špatný hash,
neplatný stav/typ, úspěšné ověření.

---

## 6. Co záměrně chybí

- obnova instance → [BACKUP-2a](BACKUP-2a-bezpecna-obnova.md),
- UI,
- automatické zálohy,
- kontrola existence příloh vůči DB (attachment gaps → budoucí rozšíření).
